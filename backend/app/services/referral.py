"""Ядро рефералки: кто получает награду и как она доходит до обоих.

Друг платит впервые, и обоим полагается по дню за каждый оплаченный.
Само начисление идёт в два отдельных прыжка (панель для друга, панель
или бот продаж для пригласившего), и каждый прыжок сразу помечается
сделанным: сбой одного из них при повторной попытке не должен продлить
того, кому уже продлили.

Хранилище спрятано за протоколом ``RewardStore``: тестам рефералки база
не нужна, у проекта нет тестовой Postgres (модели держат перечисления и
``PGUUID``), и вся логика проверяется поддельным хранилищем в памяти.
Оба внешних шлюза приходят фабриками, нулевыми вызываемыми, отдающими
асинхронный контекстный менеджер, чтобы тесты подсовывали подделки, а
прод собирал настоящие ``RemnawaveGateway``/``BedolagaGateway``.
"""

import logging
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.bedolaga.client import BedolagaUserNotFoundError
from app.integrations.remnawave.client import RemnawaveUserNotFoundError
from app.models.billing import Payment, PaymentStatus, ReferralReward
from app.services.panel import read_panel_user

logger = logging.getLogger(__name__)

__all__ = [
    "CODE_RE",
    "ReferralService",
    "RewardStore",
    "SqlRewardStore",
    "normalize_code",
]

# Код приглашения это имя учётки в панели: буквы, цифры и то, что
# панель разрешает в username. Ограничение длины совпадает с колонкой
# `referral_code`/`inviter_username` (String(64)).
CODE_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")

# Учётки интеграции, которые не должны получать награду за приглашение.
_SINERGIYA_RE = re.compile(r"^OOO_SINERGIYA_", re.IGNORECASE)

# После десятой неудачной попытки выдачи запись перестаёт повторяться
# сама: дальше ей нужны глаза человека, а не фоновая задача.
_MAX_ATTEMPTS = 10
# Окно, за которое считается потолок наград одному пригласившему.
_CAP_WINDOW_DAYS = 30
# Совпадает с длиной колонки `last_error` (String(500)).
_MAX_ERROR_LENGTH = 500

GatewayFactory = Callable[[], AbstractAsyncContextManager[Any]]


def normalize_code(raw: str | None) -> str | None:
    """Привести код приглашения к пригодному для поиска в панели виду.

    Обрезает только пробелы по краям: панель ищет учётку по точному
    имени, и лишняя нормализация регистра увела бы поиск от настоящего
    пользователя (Alyona_Tutina и alyona_tutina это разные запросы).

    Returns:
        Код без краевых пробелов либо None, если кода нет или он не
        похож на имя учётки.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped or not CODE_RE.match(stripped):
        return None
    return stripped


class RewardStore(Protocol):
    """То, что нужно ядру рефералки от хранилища наград.

    Логика начисления живёт по эту сторону протокола и не знает про
    SQLAlchemy: тесты дают хранилище в памяти, а прод даёт
    ``SqlRewardStore``.
    """

    async def has_earlier_paid(self, email: str, payment_id: UUID) -> bool:
        """У этой почты уже была другая успешная оплата."""
        ...

    async def reward_exists(self, payment_id: UUID, email: str) -> bool:
        """Награда по этому платежу или почте уже заведена."""
        ...

    async def add(self, reward: ReferralReward) -> None:
        """Завести новую запись награды."""
        ...

    async def granted_in_last_days(
        self, inviter_username: str, days: int
    ) -> int:
        """Сколько раз пригласившему уже выдали награду за окно дней."""
        ...

    async def due(self, limit: int) -> list[ReferralReward]:
        """Записи, ожидающие выдачи, самые старые первыми."""
        ...

    async def save(self) -> None:
        """Сохранить то, что изменилось в записях наград."""
        ...


class SqlRewardStore(RewardStore):
    """Хранилище наград поверх обычной сессии SQLAlchemy.

    Тонкий слой без бизнес-правил: у проекта нет тестовой базы, а логика
    рефералки проверяется хранилищем в памяти, а не этим классом.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_earlier_paid(self, email: str, payment_id: UUID) -> bool:
        stmt = (
            select(Payment.id)
            .where(
                func.lower(Payment.contact_email) == email.lower(),
                Payment.status == PaymentStatus.SUCCEEDED,
                Payment.id != payment_id,
            )
            .limit(1)
        )
        return await self._session.scalar(stmt) is not None

    async def reward_exists(self, payment_id: UUID, email: str) -> bool:
        stmt = (
            select(ReferralReward.id)
            .where(
                or_(
                    ReferralReward.payment_id == payment_id,
                    func.lower(ReferralReward.friend_email) == email.lower(),
                )
            )
            .limit(1)
        )
        return await self._session.scalar(stmt) is not None

    async def add(self, reward: ReferralReward) -> None:
        self._session.add(reward)

    async def granted_in_last_days(
        self, inviter_username: str, days: int
    ) -> int:
        threshold = datetime.now(UTC) - timedelta(days=days)
        stmt = select(func.count()).where(
            ReferralReward.inviter_username == inviter_username,
            ReferralReward.inviter_granted_at.is_not(None),
            ReferralReward.inviter_granted_at >= threshold,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def due(self, limit: int) -> list[ReferralReward]:
        stmt = (
            select(ReferralReward)
            .where(ReferralReward.status == "pending")
            .order_by(ReferralReward.created_at)
            .limit(limit)
        )
        return list(await self._session.scalars(stmt))

    async def save(self) -> None:
        await self._session.commit()


def _inviter_days(raw: Mapping[str, Any], settings: Settings) -> int | None:
    """Сколько дней причитается пригласившему, либо None, если не принят.

    Порядок проверок важен: учётки интеграции отсекаются раньше тега и
    статуса, а мёртвая подписка отсекается раньше тега, потому что дни
    не могут лечь на то, чего больше нет.
    """
    username = str(raw.get("username") or "")
    if _SINERGIYA_RE.match(username):
        return None

    status = str(raw.get("status") or "").upper()
    if status != "ACTIVE":
        return None

    tag = str(raw.get("tag") or "").upper()
    if tag == "SVOI":
        # Вечный срок дней не просит, но друг всё равно на бонусе.
        return 0
    if tag == "PAID":
        return settings.referral_inviter_days
    return None


def _read_telegram_id(raw: Mapping[str, Any]) -> int | None:
    value = raw.get("telegramId")
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


class ReferralService:
    """Правила начисления и обработчик наград за приглашение."""

    def __init__(
        self,
        settings: Settings,
        store: RewardStore,
        panel_factory: GatewayFactory,
        bedolaga_factory: GatewayFactory,
    ) -> None:
        self._settings = settings
        self._store = store
        self._panel_factory = panel_factory
        self._bedolaga_factory = bedolaga_factory

    async def register(
        self,
        *,
        payment: Payment,
        friend_panel_user_id: int | None,
        friend_was_paid: bool,
    ) -> ReferralReward | None:
        """Завести награду за первую оплату друга, если она положена.

        Ничего не выдаёт сама, только заводит запись. Выдачу делает
        ``process``, отдельно от ответа вебхуку: сбой панели или бота
        продаж здесь не должен помешать подтвердить платёж.
        """
        try:
            if not self._settings.referral_enabled:
                return None

            code = normalize_code(payment.referral_code)
            if code is None:
                return None

            email = (payment.contact_email or "").strip().lower()
            if not email:
                return None

            if friend_was_paid:
                return None
            if await self._store.has_earlier_paid(email, payment.id):
                return None
            if await self._store.reward_exists(payment.id, email):
                return None

            async with self._panel_factory() as panel:
                try:
                    inviter_raw = await panel.get_user_by_username(code)
                except RemnawaveUserNotFoundError:
                    return None

                inviter_user = read_panel_user(inviter_raw)

                if friend_panel_user_id is not None:
                    if inviter_user.id == friend_panel_user_id:
                        # Код совпал с собственной учёткой: это
                        # приглашение самого себя.
                        return None
                    try:
                        friend_raw = await panel.get_user_by_id(
                            friend_panel_user_id
                        )
                    except RemnawaveUserNotFoundError:
                        friend_raw = None
                    if friend_raw is not None:
                        friend_username = str(friend_raw.get("username") or "")
                        if friend_username and (
                            friend_username.casefold() == code.casefold()
                        ):
                            return None

            inviter_days = _inviter_days(inviter_raw, self._settings)
            if inviter_days is None:
                return None

            status = "pending"
            if inviter_days > 0:
                granted = await self._store.granted_in_last_days(
                    inviter_user.username or code, _CAP_WINDOW_DAYS
                )
                if granted >= self._settings.referral_monthly_cap:
                    # Шестая и дальше ждут одобрения, но другу дни
                    # всё равно причитаются: process выдаст их сразу.
                    status = "held"

            reward = ReferralReward(
                payment_id=payment.id,
                friend_email=email,
                friend_panel_user_id=friend_panel_user_id,
                inviter_username=inviter_user.username or code,
                inviter_panel_user_id=inviter_user.id,
                inviter_telegram_id=_read_telegram_id(inviter_raw),
                friend_days=self._settings.referral_friend_days,
                inviter_days=inviter_days,
                status=status,
                friend_granted_at=None,
                inviter_granted_at=None,
                attempts=0,
                last_error=None,
            )

            await self._store.add(reward)
            await self._store.save()
            return reward
        except Exception:
            logger.exception("Рефералка: не удалось завести награду")
            return None

    async def process(self, reward: ReferralReward) -> None:
        """Выдать то, что причитается по записи и ещё не выдано.

        Каждая удачная выдача сохраняется сразу же, до следующего
        сетевого вызова: повтор после сбоя должен продлить только то,
        что не продлилось в прошлый раз.
        """
        try:
            if reward.status not in ("pending", "held"):
                return

            if reward.friend_granted_at is None:
                granted = await self._grant_friend(reward)
                if not granted:
                    return

            if reward.status == "held":
                # Другу выдано, а снятие потолка пригласившему
                # дожидается человека, а не фоновой задачи.
                return

            if reward.inviter_days == 0:
                if reward.status != "granted":
                    reward.status = "granted"
                    await self._store.save()
                return

            if reward.inviter_granted_at is None:
                granted = await self._grant_inviter(reward)
                if not granted:
                    return

            reward.status = "granted"
            await self._store.save()
        except Exception:
            logger.exception(
                "Рефералка: сбой обработки награды %s", reward.id
            )

    async def retry_due(self, limit: int = 20) -> int:
        """Повторить зависшие выдачи. Возвращает число обработанных.

        Не сообщает, сколько из них выдались успешно, только сколько
        попыток сделано за этот обход.
        """
        try:
            rewards = await self._store.due(limit)
        except Exception:
            logger.exception("Рефералка: не удалось получить список наград")
            return 0

        for reward in rewards:
            await self.process(reward)
        return len(rewards)

    async def _grant_friend(self, reward: ReferralReward) -> bool:
        """Продлить подписку друга в панели. True значит: выдано или уже было.

        Друг всегда клиент сайта: подписка у него только в панели, ни
        Bedolaga тут ни при чём.
        """
        if reward.friend_panel_user_id is None:
            # Идентификатор учётки друга обязан прийти с самого начала
            # (Task 4 передаёт его всегда); выводить имя из почты здесь
            # означало бы завести циклический импорт с checkout и, хуже
            # того, продлить не ту учётку, если имя из почты кому-то
            # уже принадлежит.
            self._record_failure(
                reward, "у награды нет id учётки друга в панели"
            )
            await self._store.save()
            return False

        try:
            async with self._panel_factory() as panel:
                friend_raw = await panel.get_user_by_id(
                    reward.friend_panel_user_id
                )
                friend = read_panel_user(friend_raw)
                base = max(friend.expires_at, date.today())
                expires_at = base + timedelta(days=reward.friend_days)
                await panel.set_expiry(
                    friend.id,
                    datetime.combine(
                        expires_at, datetime.min.time(), tzinfo=UTC
                    ),
                )
        except Exception as error:
            logger.exception(
                "Рефералка: не удалось выдать дни другу по награде %s",
                reward.id,
            )
            self._record_failure(reward, f"не выдано другу: {error}")
            await self._store.save()
            return False

        reward.friend_granted_at = datetime.now(UTC)
        await self._store.save()
        return True

    async def _grant_inviter(self, reward: ReferralReward) -> bool:
        """Продлить подписку пригласившего. True: выдано или уже было."""
        try:
            if reward.inviter_telegram_id is not None:
                async with self._bedolaga_factory() as bedolaga:
                    try:
                        subscription_id = (
                            await bedolaga.subscription_id_by_telegram_id(
                                reward.inviter_telegram_id
                            )
                        )
                    except BedolagaUserNotFoundError as error:
                        # У бота нашёлся только триал, продлевать
                        # нечего, а падать в панель нельзя: бот
                        # перезапишет срок своим при следующей сверке.
                        logger.warning(
                            "Рефералка: у пригласившего по награде %s в "
                            "боте только триал",
                            reward.id,
                        )
                        self._record_failure(
                            reward,
                            f"у пригласившего в боте только триал: {error}",
                        )
                        await self._store.save()
                        return False
                    await bedolaga.extend(subscription_id, reward.inviter_days)
            else:
                async with self._panel_factory() as panel:
                    inviter_raw = await panel.get_user_by_id(
                        reward.inviter_panel_user_id
                    )
                    inviter = read_panel_user(inviter_raw)
                    base = max(inviter.expires_at, date.today())
                    expires_at = base + timedelta(days=reward.inviter_days)
                    await panel.set_expiry(
                        inviter.id,
                        datetime.combine(
                            expires_at, datetime.min.time(), tzinfo=UTC
                        ),
                    )
        except Exception as error:
            logger.exception(
                "Рефералка: не удалось выдать дни пригласившему по "
                "награде %s",
                reward.id,
            )
            self._record_failure(reward, f"не выдано пригласившему: {error}")
            await self._store.save()
            return False

        reward.inviter_granted_at = datetime.now(UTC)
        await self._store.save()
        return True

    def _record_failure(self, reward: ReferralReward, message: str) -> None:
        """Отметить неудачную попытку, а после многих сдаться."""
        reward.attempts += 1
        reward.last_error = message[:_MAX_ERROR_LENGTH]
        if reward.attempts >= _MAX_ATTEMPTS:
            reward.status = "failed"
