"""Административные операции над пользователями и их подписками."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveNotConfiguredError,
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)
from app.models.billing import ReferralReward
from app.models.user import User
from app.schemas.admin import AdminOverviewResponse, AdminUserResponse
from app.services.panel import read_panel_user
from app.services.referral import RewardStore
from app.services.subscription import (
    PanelUnavailableError,
    SubscriptionNotFoundError,
)

__all__ = [
    "AdminService",
    "ReferralRewardNotFoundError",
    "ReferralRewardStatusError",
    "UsernameAlreadyTakenError",
    "list_referral_rewards",
    "reject_referral_reward",
    "release_referral_reward",
]

RECENT_WINDOW_DAYS = 30
USERS_PAGE_SIZE = 50

# Из held можно только освободить награду в обработку: любой другой
# статус означает, что решение по ней уже принято (автоматикой или
# человеком), и повторный перевод в pending исказил бы историю.
_RELEASABLE_STATUSES = frozenset({"held"})
# Отклонить можно то, что ещё не выдано целиком и не отклонено уже:
# granted и rejected это конечные состояния, трогать их незачем.
_REJECTABLE_STATUSES = frozenset({"held", "pending", "failed"})
# Продление того же друга каскадом отклоняется вместе с первой
# покупкой только из этих статусов: если оно уже granted, дни другу
# выдал не он сам, а пригласивший, и назад их эта функция не забирает
# (см. docstring reject_referral_reward).
_CASCADE_REJECTABLE_STATUSES = frozenset({"held", "pending", "failed"})


class ReferralRewardNotFoundError(LookupError):
    """Награда за приглашение с таким id не найдена."""


class ReferralRewardStatusError(ValueError):
    """Награда сейчас не в статусе, из которого разрешено это действие."""


class UsernameAlreadyTakenError(ValueError):
    """Такое имя уже занято в панели."""


class AdminService:
    """Операции, доступные только администратору сервиса.

    Продление и выдача доступа живут здесь, а не в пользовательской
    части: без подключённого платёжного провайдера самообслуживание
    означало бы бесплатный доступ для любого желающего.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def _gateway(self) -> RemnawaveGateway:
        try:
            return RemnawaveGateway(self._settings)
        except RemnawaveNotConfiguredError as error:
            raise PanelUnavailableError("Панель пока не подключена") from error

    async def overview(self) -> AdminOverviewResponse:
        """Показатели сервиса по локальной базе."""
        since = datetime.now(UTC) - timedelta(days=RECENT_WINDOW_DAYS)

        total = await self._count(select(func.count()).select_from(User))
        linked = await self._count(
            select(func.count())
            .select_from(User)
            .where(User.remnawave_user_id.is_not(None))
        )
        admins = await self._count(
            select(func.count()).select_from(User).where(User.is_admin)
        )
        recent = await self._count(
            select(func.count())
            .select_from(User)
            .where(User.created_at >= since)
        )

        return AdminOverviewResponse(
            total_users=total,
            linked_users=linked,
            admins=admins,
            registered_last_30_days=recent,
        )

    async def list_users(
        self,
        *,
        search: str | None = None,
        limit: int = USERS_PAGE_SIZE,
    ) -> list[AdminUserResponse]:
        """Последние зарегистрированные пользователи кабинета."""
        statement = (
            select(User)
            .options(selectinload(User.identities))
            .order_by(User.created_at.desc())
            .limit(limit)
        )

        if search:
            pattern = f"%{search.strip().lower()}%"
            statement = statement.where(
                func.lower(User.email).like(pattern)
                | func.lower(User.display_name).like(pattern)
            )

        users = (await self._session.scalars(statement)).all()
        return [self._describe(user) for user in users]

    async def extend_subscription(
        self,
        user_id: UUID,
        days: int,
    ) -> AdminUserResponse:
        """Продлить подписку пользователя в панели.

        Raises:
            SubscriptionNotFoundError: У пользователя нет привязки.
            PanelUnavailableError: Панель недоступна.
        """
        user = await self._require_user(user_id)
        if user.remnawave_user_id is None:
            raise SubscriptionNotFoundError("no linked subscription")

        async with self._gateway() as gateway:
            try:
                payload = await gateway.get_user_by_id(
                    user.remnawave_user_id
                )
                panel_user = read_panel_user(payload)

                # Отсчитываем от текущей даты окончания, если она ещё не
                # прошла: иначе продление съедало бы остаток срока.
                today = datetime.now(UTC).date()
                base = max(panel_user.expires_at, today)
                expires_at = datetime.combine(
                    base + timedelta(days=days),
                    datetime.min.time(),
                    tzinfo=UTC,
                )

                updated = await gateway.set_expiry(
                    user.remnawave_user_id, expires_at
                )
            except RemnawaveUserNotFoundError as error:
                raise SubscriptionNotFoundError(str(user_id)) from error
            except RemnawaveUnavailableError as error:
                raise PanelUnavailableError(str(error)) from error

        return self._describe(user, panel_payload=updated)

    async def grant_trial(
        self,
        user_id: UUID,
        *,
        username: str,
        days: int,
    ) -> AdminUserResponse:
        """Завести пользователя в панели и привязать его к аккаунту.

        Raises:
            UsernameAlreadyTakenError: Имя занято в панели.
            PanelUnavailableError: Панель недоступна.
        """
        user = await self._require_user(user_id)
        expires_at = datetime.now(UTC) + timedelta(days=days)

        async with self._gateway() as gateway:
            try:
                await gateway.get_user_by_username(username)
            except RemnawaveUserNotFoundError:
                pass
            except RemnawaveUnavailableError as error:
                raise PanelUnavailableError(str(error)) from error
            else:
                raise UsernameAlreadyTakenError(username)

            try:
                created = await gateway.create_user(
                    username=username,
                    expire_at=expires_at,
                    email=user.email,
                )
            except RemnawaveUnavailableError as error:
                raise PanelUnavailableError(str(error)) from error

        panel_user = read_panel_user(created)
        user.remnawave_user_id = panel_user.id
        user.remnawave_username = panel_user.username or username
        await self._session.commit()

        return self._describe(user, panel_payload=created)

    async def _require_user(self, user_id: UUID) -> User:
        statement = (
            select(User)
            .options(selectinload(User.identities))
            .where(User.id == user_id)
        )
        user = await self._session.scalar(statement)
        if user is None:
            raise SubscriptionNotFoundError(str(user_id))
        return user

    async def _count(self, statement) -> int:
        return int(await self._session.scalar(statement) or 0)

    @staticmethod
    def _describe(
        user: User,
        *,
        panel_payload=None,
    ) -> AdminUserResponse:
        expires_at = None
        days_left = None

        if panel_payload is not None:
            panel_user = read_panel_user(panel_payload)
            expires_at = panel_user.expires_at
            days_left = max(0, (expires_at - datetime.now(UTC).date()).days)

        return AdminUserResponse(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            created_at=user.created_at,
            is_active=user.is_active,
            is_admin=user.is_admin,
            panel_username=user.remnawave_username,
            subscription_linked=user.remnawave_user_id is not None,
            expires_at=expires_at,
            days_left=days_left,
        )


async def list_referral_rewards(
    store: RewardStore, *, status: str | None, limit: int
) -> list[ReferralReward]:
    """Последние награды за приглашение, при нужде только одного статуса.

    Свободная функция, а не метод ``AdminService``: ей нужно только
    хранилище наград, которое приходит своей же зависимостью
    (``get_reward_store``), и заводить для неё сессию и настройки
    ``AdminService`` было бы лишним.
    """
    return await store.list_recent(status, limit)


async def release_referral_reward(
    store: RewardStore, reward_id: UUID
) -> ReferralReward:
    """Перевести придержанную (``held``) награду в обработку.

    Сама выдача сюда не входит: обработку в фон ставит вызывающий
    (маршрут) сразу после того, как эта функция сохранит новый статус.
    Запрос администратора не должен ждать похода в панель и в бота
    продаж.

    Raises:
        ReferralRewardNotFoundError: Нет записи с таким id.
        ReferralRewardStatusError: Награда не в статусе ``held``.
    """
    reward = await store.get(reward_id)
    if reward is None:
        raise ReferralRewardNotFoundError(str(reward_id))
    if reward.status not in _RELEASABLE_STATUSES:
        raise ReferralRewardStatusError(reward.status)
    reward.status = "pending"
    await store.save()
    return reward


async def reject_referral_reward(
    store: RewardStore, reward_id: UUID
) -> ReferralReward:
    """Отклонить награду за приглашение.

    Разрешено из ``held``, ``pending`` и ``failed``. Дни, которые уже
    выданы, назад не забираются: это ручное действие в панели, а не
    то, что делает эта функция.

    Отклонение награды вида ``first`` тянет за собой и продление того
    же друга (``renewal_for``): если первой покупки как приглашения не
    было, то и продлевать нечего было в принципе, а не только
    приостановить до выяснения. Каскад трогает только ``pending``,
    ``held`` и ``failed`` у продления: уже выданный (``granted``)
    оставляем как есть, те дни отдал пригласивший, и забирать их назад
    здесь всё так же не наше дело. Отклонение самой награды за
    продление на first, наоборот, никак не влияет: у друга остаётся
    его честно засчитанная первая покупка.

    Raises:
        ReferralRewardNotFoundError: Нет записи с таким id.
        ReferralRewardStatusError: Награда уже ``granted`` или
            ``rejected``.
    """
    reward = await store.get(reward_id)
    if reward is None:
        raise ReferralRewardNotFoundError(str(reward_id))
    if reward.status not in _REJECTABLE_STATUSES:
        raise ReferralRewardStatusError(reward.status)
    reward.status = "rejected"
    if reward.kind == "first":
        renewal = await store.renewal_for(reward.friend_email)
        if (
            renewal is not None
            and renewal.status in _CASCADE_REJECTABLE_STATUSES
        ):
            renewal.status = "rejected"
    await store.save()
    return reward
