"""Покупка: создать платёж, дождаться оплаты, выдать подписку.

Платёж записывается в базу до похода в Platega. Если Platega не ответит, у
нас всё равно останется след с суммой и почтой — иначе деньги могли бы уйти
по ссылке, о существовании которой сайт ничего не знает.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
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
from app.schemas.cabinet import PaymentStatusResponse
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
    ) -> StartedCheckout:
        """Создать платёж и вернуть ссылку на оплату."""
        if not self._settings.is_platega_configured:
            raise CheckoutNotConfiguredError("Platega is not configured")

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

        try:
            async with RemnawaveGateway(self._settings) as panel:
                try:
                    existing = await panel.get_user_by_username(username)
                except RemnawaveUserNotFoundError:
                    created = await panel.create_user(
                        username=username,
                        expire_at=datetime.now(UTC) + timedelta(days=days),
                        email=payment.contact_email,
                    )
                    payment.subscription_url = (
                        str(created.get("subscriptionUrl") or "") or None
                    )
                    await self._session.commit()
                    return

                panel_user = read_panel_user(existing)
                # Продлеваем от даты окончания, если она ещё не прошла:
                # иначе покупка съедала бы остаток оплаченного срока.
                today = datetime.now(UTC).date()
                base = max(panel_user.expires_at, today)
                await panel.set_expiry(
                    panel_user.id,
                    datetime.combine(
                        base + timedelta(days=days),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                )
                payment.subscription_url = panel_user.subscription_url
                await self._session.commit()
        except RemnawaveUnavailableError:
            logger.exception(
                "Оплата получена, но подписка не выдана: платёж %s",
                payment.id,
            )

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
