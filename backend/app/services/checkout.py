"""Покупка: создать платёж, дождаться оплаты, выдать подписку.

Платёж записывается в базу до похода в Platega. Если Platega не ответит, у
нас всё равно останется след с суммой и почтой — иначе деньги могли бы уйти
по ссылке, о существовании которой сайт ничего не знает.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.platega.client import (
    PlategaGateway,
    PlategaNotConfiguredError,
    PlategaUnavailableError,
)
from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)
from app.models.billing import Payment, PaymentPurpose, PaymentStatus
from app.models.user import User
from app.schemas.cabinet import PaymentStatusResponse
from app.services.letters import subscription_ready_letter
from app.services.mail import Mailer
from app.services.notify import (
    TelegramNotifier,
    pokupka_soobshchenie,
    sboj_vydachi_soobshchenie,
)
from app.services.panel import read_panel_user
from app.services.shop import (
    ShopCatalogue,
    ShopUnavailableError,
    UnknownTariffError,
)

logger = logging.getLogger(__name__)

KOPECKS_IN_RUBLE = 100
PROVIDER = "platega"
# Успех в терминах Platega. Остальные состояния оплатой не считаются.
SUCCESS_STATUS = "CONFIRMED"
USERNAME_LIMIT = 64


def panel_username(email: str) -> str:
    """Имя пользователя панели, выведенное из почты.

    Чистая функция: одна почта всегда даёт одно имя. На это опирается
    продление — по имени покупателя ищут в панели, и если имя «поплывёт»,
    человек получит вторую подписку вместо продления своей.
    """
    normalised = email.strip().lower()
    local = normalised.split("@", 1)[0]
    safe = re.sub(r"[^a-z0-9]+", "_", local).strip("_") or "user"
    # Хвост хеша разводит одинаковые логины на разных почтовых доменах.
    tail = hashlib.sha256(normalised.encode()).hexdigest()[:8]
    return f"{safe}_{tail}"[:USERNAME_LIMIT]


class CheckoutNotConfiguredError(RuntimeError):
    """Касса не настроена."""


class CheckoutUnavailableError(RuntimeError):
    """Платёжная система или витрина недоступны."""


class UnknownPaymentMethodError(ValueError):
    """Способ оплаты не входит в число включённых."""


@dataclass(frozen=True)
class StartedCheckout:
    """Начатая покупка: наш платёж и ссылка, куда идти платить."""

    payment_id: UUID
    redirect_url: str


class CheckoutService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def start(
        self,
        *,
        email: str,
        tariff_id: int,
        period_days: int,
        payment_method: int | None = None,
    ) -> StartedCheckout:
        """Создать платёж и вернуть ссылку на оплату.

        Способ оплаты сверяем со списком включённых. Присланный кем
        угодно код ушёл бы в Platega как есть, и покупатель уехал бы
        платить способом, которого у мерчанта нет: отказ он увидел бы
        уже на чужой странице и решил бы, что сломались мы.
        """
        if not self._settings.is_platega_configured:
            raise CheckoutNotConfiguredError("Platega is not configured")

        allowed = self._settings.payment_method_codes
        if payment_method is not None and payment_method not in allowed:
            raise UnknownPaymentMethodError(str(payment_method))

        async with ShopCatalogue(self._settings) as shop:
            try:
                amount_kopecks = await shop.price_kopecks(
                    tariff_id, period_days
                )
                name = await shop.tariff_name(tariff_id)
            except ShopUnavailableError as error:
                raise CheckoutUnavailableError(str(error)) from error

        payment = Payment(
            user_id=None,
            contact_email=email,
            amount_kopecks=amount_kopecks,
            status=PaymentStatus.PENDING,
            purpose=PaymentPurpose.SUBSCRIPTION,
            provider=PROVIDER,
            description=f"{name}, {period_days} дн.",
            tariff_id=tariff_id,
            period_days=period_days,
        )
        self._session.add(payment)
        await self._session.flush()

        origin = (
            self._settings.allowed_origins[0]
            if self._settings.allowed_origins
            else ""
        ).rstrip("/")

        try:
            async with PlategaGateway(self._settings) as platega:
                created = await platega.create_payment(
                    amount_rubles=amount_kopecks / KOPECKS_IN_RUBLE,
                    description=payment.description,
                    payload=str(payment.id),
                    # Возврат ведёт на страницу покупки с токеном: она
                    # умеет показывать состояние оплаты. Отдельной
                    # страницы /pay на сайте нет, и человек упирался бы
                    # в 404 сразу после того, как заплатил.
                    return_url=f"{origin}/buy?token={payment.id}",
                    failed_url=f"{origin}/buy?token={payment.id}&failed=1",
                    payment_method=payment_method,
                )
        except PlategaNotConfiguredError as error:
            raise CheckoutNotConfiguredError(str(error)) from error
        except PlategaUnavailableError as error:
            # Платёж помечаем несостоявшимся: висящий pending без
            # идентификатора у Platega никогда не подтвердится.
            payment.status = PaymentStatus.FAILED
            await self._session.commit()
            raise CheckoutUnavailableError(str(error)) from error

        payment.provider_payment_id = created.id
        await self._session.commit()

        return StartedCheckout(
            payment_id=payment.id,
            redirect_url=created.redirect_url,
        )

    async def confirm(
        self,
        *,
        provider_payment_id: str,
        status_name: str,
    ) -> bool:
        """Отметить платёж оплаченным. True — только первому, кто это сделал.

        Platega повторяет вебхук, пока не получит 200, поэтому один и тот же
        платёж приходит несколько раз. Подписку продлевает только переход
        pending → succeeded, иначе человек получил бы лишние дни за одни и
        те же деньги.
        """
        payment = await self._by_provider_id(provider_payment_id)
        if payment is None:
            logger.warning("Вебхук про неизвестный платёж")
            return False

        if status_name.upper() != SUCCESS_STATUS:
            if payment.status is PaymentStatus.PENDING:
                payment.status = PaymentStatus.FAILED
                await self._session.commit()
            return False

        if payment.status is not PaymentStatus.PENDING:
            return False

        payment.status = PaymentStatus.SUCCEEDED
        await self._session.commit()
        return True

    async def needs_delivery(self, *, provider_payment_id: str) -> bool:
        """Оплачен, а ссылки нет: выдача в прошлый раз сорвалась.

        Ссылка на подписку появляется у платежа только после ответа
        панели. Если панель молчала, платёж остался оплаченным без ссылки,
        и человек с деньгами на нашей стороне сидит без доступа. Повторный
        вебхук от Platega это второй шанс довыдать, а не повод ждать письма
        в поддержку.
        """
        payment = await self._by_provider_id(provider_payment_id)
        if payment is None or payment.contact_email is None:
            return False
        return (
            payment.status is PaymentStatus.SUCCEEDED
            and payment.subscription_url is None
        )

    async def deliver(self, *, provider_payment_id: str) -> None:
        """Выдать оплаченную подписку в панели.

        Вызывается только после успешного перехода платежа в succeeded.
        Ошибку панели наверх не поднимаем: деньги уже получены, и вебхуку
        надо ответить 200, иначе Platega будет слать его снова. Невыданная
        подписка видна в логе и в статусе платежа.
        """
        payment = await self._by_provider_id(provider_payment_id)
        if payment is None or payment.contact_email is None:
            return

        username = panel_username(payment.contact_email)
        days = payment.period_days or 30
        # Учётка, уже привязанная к кабинету этой почты. Искать только
        # по имени, выведенному из почты, недостаточно: у перенесённых
        # и заведённых вручную людей имя другое (Alyona_Tutina,
        # user_369990765), и покупка завела бы им вторую учётку, а
        # оплаченный срок остался бы на первой. На 01.09.2026 таких
        # восемь из шестнадцати.
        privyazannaya = await self._privyazannaya_uchyotka(payment)

        try:
            async with RemnawaveGateway(self._settings) as panel:
                try:
                    if privyazannaya is not None:
                        existing = await panel.get_user_by_id(privyazannaya)
                    else:
                        existing = await panel.get_user_by_username(username)
                except RemnawaveUserNotFoundError:
                    expires_at = datetime.now(UTC) + timedelta(days=days)
                    squad = self._settings.remnawave_squad_uuid
                    if not squad:
                        # Молча выдать учётку без сквада хуже, чем не
                        # выдать вовсе: деньги приняты, человек ждёт, а
                        # подключиться не может и не понимает почему.
                        raise CheckoutNotConfiguredError(
                            "REMNAWAVE_SQUAD_UUID is required to create users"
                        ) from None
                    created = await panel.create_user(
                        username=username,
                        expire_at=expires_at,
                        email=payment.contact_email,
                        hwid_device_limit=await self._device_limit(payment),
                        active_internal_squads=[squad],
                        tag="PAID",
                    )
                    payment.subscription_url = (
                        str(created.get("subscriptionUrl") or "") or None
                    )
                    await self._session.commit()
                    kabinet = await self._kabinet_bezopasno(
                        payment, created.get("id"), username
                    )
                    await self._notify(
                        payment, expires_at.date(), kabinet_zavedyon=kabinet
                    )
                    self._soobshchit_o_pokupke(
                        payment, expires_at.date(), is_new=True
                    )
                    return

                panel_user = read_panel_user(existing)
                # Продлеваем от даты окончания, если она ещё не прошла:
                # иначе покупка съедала бы остаток оплаченного срока.
                today = datetime.now(UTC).date()
                base = max(panel_user.expires_at, today)
                expires_at = base + timedelta(days=days)
                await panel.set_expiry(
                    panel_user.id,
                    datetime.combine(
                        expires_at,
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                )
                payment.subscription_url = panel_user.subscription_url
                await self._session.commit()
                kabinet = await self._kabinet_bezopasno(
                    payment, panel_user.id, panel_user.username or username
                )
                await self._notify(
                    payment, expires_at, kabinet_zavedyon=kabinet
                )
                self._soobshchit_o_pokupke(payment, expires_at, is_new=False)
        except CheckoutNotConfiguredError:
            # Сквад не задан: деньги приняты, а выдать нечего.
            self._soobshchit_o_sboe(payment, "не задан сквад в настройках")
            raise
        except RemnawaveUnavailableError:
            logger.exception(
                "Оплата получена, но подписка не выдана: платёж %s",
                payment.id,
            )
            self._soobshchit_o_sboe(payment, "панель не отвечает")

    async def _privyazannaya_uchyotka(self, payment: Payment) -> int | None:
        """Учётка панели, уже привязанная к кабинету покупателя.

        Ищем сначала по владельцу платежа, потом по почте: покупка
        с сайта бывает и без входа в кабинет, и тогда владельца нет,
        а кабинет с такой почтой существовать может.
        """
        user: User | None = None
        if payment.user_id is not None:
            user = await self._session.scalar(
                select(User).where(User.id == payment.user_id)
            )
        if user is None and payment.contact_email:
            user = await self._session.scalar(
                select(User).where(
                    func.lower(User.email)
                    == payment.contact_email.strip().lower()
                )
            )
        return user.remnawave_user_id if user is not None else None

    async def _zavesti_kabinet(
        self, payment: Payment, panel_user_id: int, panel_user_name: str
    ) -> bool:
        """Завести покупателю кабинет, если он покупал без регистрации.

        Возвращает True, если кабинет создан прямо сейчас.

        Напоминания об окончании срока рассылаются по владельцам
        кабинетов, и купивший в один шаг не получал их вовсе. 01.09.2026
        так купила Алёна Тутина на три месяца: предупредить её было
        нечем до самого конца оплаченного срока.

        Раньше заводить кабинет молча было нельзя, и в модели платежа
        это записано: почта в users уникальна, а восстановления пароля
        не существовало — человек навсегда терял возможность
        зарегистрироваться сам. Восстановление появилось 03.09.2026,
        и запрет снялся. Пароль не придумываем и не шлём почтой:
        учётка заводится без пароля, а человек ставит свой через
        обычное восстановление.
        """
        if not payment.contact_email:
            return False

        pochta = payment.contact_email.strip().lower()
        user = await self._session.scalar(
            select(User).where(func.lower(User.email) == pochta)
        )
        novyj = user is None
        if user is None:
            user = User(
                email=pochta,
                display_name=pochta.split("@")[0][:80] or "Покупатель",
                password_digest=None,
                is_active=True,
            )
            self._session.add(user)

        # Связь с панелью и делает напоминания возможными: обход ищет
        # только тех, у кого она есть. Чужую связь не трогаем — один
        # и тот же id панели не может принадлежать двоим, и попытка
        # разошлась бы об ограничение уникальности.
        if user.remnawave_user_id is None:
            zanyato = await self._session.scalar(
                select(User.id).where(
                    User.remnawave_user_id == panel_user_id,
                    User.email != pochta,
                )
            )
            if zanyato is None:
                user.remnawave_user_id = panel_user_id
                user.remnawave_username = panel_user_name
            else:
                logger.warning(
                    "Учётка панели %s уже привязана к другому кабинету: "
                    "напоминания по платежу %s не пойдут",
                    panel_user_id,
                    payment.id,
                )

        await self._session.flush()
        if payment.user_id is None:
            payment.user_id = user.id
        await self._session.commit()
        return novyj

    def _cabinet_url(self) -> str:
        origin = (
            self._settings.allowed_origins[0]
            if self._settings.allowed_origins
            else ""
        ).rstrip("/")
        return origin or "https://vpanfi.su"

    async def _kabinet_bezopasno(
        self, payment: Payment, panel_user_id: int | None, panel_user_name: str
    ) -> bool:
        """То же, но без права уронить выдачу: деньги уже приняты.

        Кабинет это удобство, а подписка — то, за что заплатили. Если
        завести кабинет не вышло, человек всё равно получает ссылку,
        а разбираться идём по журналу.
        """
        if panel_user_id is None:
            return False
        try:
            return await self._zavesti_kabinet(
                payment, panel_user_id, panel_user_name
            )
        except Exception:
            logger.exception(
                "Кабинет покупателю не заведён, платёж %s", payment.id
            )
            await self._session.rollback()
            return False

    async def _device_limit(self, payment: Payment) -> int | None:
        """Сколько устройств положено по оплаченному тарифу.

        Витрина недоступна — отдаём None и заводим пользователя без
        лимита: панель подставит свой запасной. Это лучше, чем ронять
        выдачу из-за необязательного поля.
        """
        if payment.tariff_id is None:
            return None
        try:
            async with ShopCatalogue(self._settings) as shop:
                return await shop.device_limit(payment.tariff_id)
        except (ShopUnavailableError, UnknownTariffError):
            logger.warning(
                "Лимит устройств не выяснен, платёж %s", payment.id
            )
            return None

    def _soobshchit_o_pokupke(
        self, payment: Payment, expires_at: date, *, is_new: bool
    ) -> None:
        """Рассказать владельцу об оплате."""
        if "payment" not in self._settings.alert_events:
            return
        TelegramNotifier(self._settings).send_later(
            pokupka_soobshchenie(
                email=payment.contact_email or "",
                amount_kopecks=payment.amount_kopecks,
                description=payment.description,
                expires_at=expires_at,
                is_new=is_new,
                subscription_url=payment.subscription_url,
            )
        )

    def _soobshchit_o_sboe(self, payment: Payment, prichina: str) -> None:
        """Рассказать о том, что деньги взяли, а доступ не выдали.

        Такое сообщение уходит независимо от настройки событий:
        выключать его нельзя, человек остался без того, за что заплатил.
        """
        TelegramNotifier(self._settings).send_later(
            sboj_vydachi_soobshchenie(
                email=payment.contact_email or "",
                amount_kopecks=payment.amount_kopecks,
                prichina=prichina,
            )
        )

    async def _notify(
        self,
        payment: Payment,
        expires_at: date,
        *,
        kabinet_zavedyon: bool = False,
    ) -> None:
        """Отправить покупателю письмо со ссылкой — один раз.

        Письмо здесь не роскошь, а основной канал: оплата по СБП
        заканчивается в приложении банка, и вкладку с результатом человек
        чаще всего теряет. Уведомление от Platega приходит несколько раз,
        поэтому отметка о письме ставится сразу и повторов не будет.
        """
        if payment.notified_at is not None:
            return
        if not payment.contact_email or not payment.subscription_url:
            return
        if not self._settings.is_mail_configured:
            logger.warning(
                "Почта не настроена: покупатель останется без ссылки, "
                "если потеряет страницу"
            )
            return

        letter = subscription_ready_letter(
            subscription_url=payment.subscription_url,
            expires_at=expires_at,
            support_url=str(self._settings.telegram_support_url),
            support_email=self._settings.support_email,
            max_url=self._settings.max_support_url,
            cabinet_url=self._cabinet_url() if kabinet_zavedyon else None,
        )
        sent = await Mailer(self._settings).send(
            to_email=payment.contact_email,
            letter=letter,
        )
        if sent:
            payment.notified_at = datetime.now(UTC)
            await self._session.commit()

    async def state(self, payment_id: UUID) -> PaymentStatusResponse | None:
        """Состояние платежа для страницы результата."""
        payment = await self._session.get(Payment, payment_id)
        if payment is None:
            return None
        return PaymentStatusResponse(
            status=payment.status.value,
            paid=payment.status is PaymentStatus.SUCCEEDED,
            subscription_url=payment.subscription_url,
        )

    async def _by_provider_id(
        self,
        provider_payment_id: str,
    ) -> Payment | None:
        statement = select(Payment).where(
            Payment.provider == PROVIDER,
            Payment.provider_payment_id == provider_payment_id,
        )
        return await self._session.scalar(statement)


__all__ = [
    "CheckoutNotConfiguredError",
    "panel_username",
    "CheckoutService",
    "CheckoutUnavailableError",
    "StartedCheckout",
    "UnknownTariffError",
]
