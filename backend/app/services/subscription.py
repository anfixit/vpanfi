"""Привязка подписки панели к аккаунту кабинета."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveNotConfiguredError,
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
    extract_short_uuid,
)
from app.models.user import User
from app.schemas.cabinet import DeviceResponse, SubscriptionLinkResponse
from app.services.panel import (
    UnreadablePanelUserError,
    read_panel_user,
    to_device,
    to_subscription,
)

__all__ = [
    "PanelUnavailableError",
    "SubscriptionAlreadyClaimedError",
    "SubscriptionLinkInvalidError",
    "SubscriptionNotFoundError",
    "SubscriptionService",
]


class SubscriptionLinkInvalidError(ValueError):
    """Из введённого текста не удалось получить идентификатор подписки."""


class SubscriptionNotFoundError(LookupError):
    """Панель не знает такой подписки."""


class SubscriptionAlreadyClaimedError(ValueError):
    """Эта подписка уже привязана к другому аккаунту кабинета."""


class PanelUnavailableError(RuntimeError):
    """Панель не настроена или недоступна."""


class SubscriptionService:
    """Связывает аккаунт кабинета с пользователем панели.

    Панель остаётся единственным источником правды: кабинет хранит у себя
    только ссылку на пользователя панели, но не состояние его подписки.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    def _gateway(self) -> RemnawaveGateway:
        try:
            return RemnawaveGateway(self._settings)
        except RemnawaveNotConfiguredError as error:
            raise PanelUnavailableError(
                "Панель пока не подключена"
            ) from error

    async def describe(self, user: User) -> SubscriptionLinkResponse:
        """Показать текущее состояние привязки."""
        if user.remnawave_user_id is None:
            return SubscriptionLinkResponse(linked=False)

        async with self._gateway() as gateway:
            try:
                payload = await gateway.get_user_by_id(
                    user.remnawave_user_id
                )
                devices = await gateway.list_devices(
                    user.remnawave_user_id
                )
            except RemnawaveUserNotFoundError:
                # Пользователя удалили из панели: привязка больше не
                # значит ничего, поэтому честно показываем её отсутствие.
                return SubscriptionLinkResponse(linked=False)
            except RemnawaveUnavailableError as error:
                raise PanelUnavailableError(str(error)) from error

        return self._describe_payload(payload, devices_used=len(devices))

    async def link(
        self,
        user: User,
        subscription_link: str,
    ) -> SubscriptionLinkResponse:
        """Привязать подписку по ссылке из бота.

        Raises:
            SubscriptionLinkInvalidError: Ссылку не удалось разобрать.
            SubscriptionNotFoundError: Панель не нашла такую подписку.
            SubscriptionAlreadyClaimedError: Подписка занята другим
                аккаунтом.
            PanelUnavailableError: Панель не настроена или недоступна.
        """
        short_uuid = extract_short_uuid(subscription_link)
        if short_uuid is None:
            raise SubscriptionLinkInvalidError(
                "Не похоже на ссылку подписки"
            )

        async with self._gateway() as gateway:
            try:
                payload = await gateway.get_user_by_short_uuid(short_uuid)
            except RemnawaveUserNotFoundError as error:
                raise SubscriptionNotFoundError(short_uuid) from error
            except RemnawaveUnavailableError as error:
                raise PanelUnavailableError(str(error)) from error

            try:
                panel_user = read_panel_user(payload)
            except UnreadablePanelUserError as error:
                raise PanelUnavailableError(str(error)) from error

            await self._ensure_not_claimed(user, panel_user.id)

            user.remnawave_user_id = panel_user.id
            user.remnawave_username = panel_user.username or None
            await self._session.commit()

            try:
                devices = await gateway.list_devices(panel_user.id)
            except RemnawaveUnavailableError:
                devices = []

        return self._describe_payload(payload, devices_used=len(devices))

    async def list_devices(self, user: User) -> list[DeviceResponse]:
        """Устройства пользователя из панели.

        Пока подписка не привязана, показывать нечего — это не ошибка,
        а пустой список.
        """
        if user.remnawave_user_id is None:
            return []

        async with self._gateway() as gateway:
            try:
                devices = await gateway.list_devices(
                    user.remnawave_user_id
                )
            except RemnawaveUserNotFoundError:
                return []
            except RemnawaveUnavailableError as error:
                raise PanelUnavailableError(str(error)) from error

        return [to_device(device) for device in devices]

    async def forget_device(self, user: User, device_id: str) -> None:
        """Отвязать устройство в панели.

        Raises:
            SubscriptionNotFoundError: К аккаунту не привязана подписка.
            PanelUnavailableError: Панель недоступна.
        """
        if user.remnawave_user_id is None:
            raise SubscriptionNotFoundError("no linked subscription")

        async with self._gateway() as gateway:
            try:
                await gateway.delete_device(
                    user.remnawave_user_id, device_id
                )
            except RemnawaveUserNotFoundError as error:
                raise SubscriptionNotFoundError(device_id) from error
            except RemnawaveUnavailableError as error:
                raise PanelUnavailableError(str(error)) from error

    async def unlink(self, user: User) -> None:
        """Отвязать подписку от аккаунта, ничего не трогая в панели."""
        user.remnawave_user_id = None
        user.remnawave_username = None
        await self._session.commit()

    async def _ensure_not_claimed(
        self,
        user: User,
        panel_user_id: int,
    ) -> None:
        statement = select(User).where(
            User.remnawave_user_id == panel_user_id,
            User.id != user.id,
        )
        if await self._session.scalar(statement) is not None:
            raise SubscriptionAlreadyClaimedError(str(panel_user_id))

    @staticmethod
    def _describe_payload(payload, *, devices_used: int):
        panel_user = read_panel_user(payload)
        return SubscriptionLinkResponse(
            linked=True,
            panel_username=panel_user.username or None,
            subscription_url=panel_user.subscription_url,
            subscription=to_subscription(
                panel_user,
                devices_used=devices_used,
            ),
        )
