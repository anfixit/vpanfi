from collections.abc import Mapping
from typing import Any

from remnawave import RemnawaveSDK

from app.core.config import Settings


class RemnawaveNotConfiguredError(RuntimeError):
    pass


class RemnawaveUserNotFoundError(LookupError):
    pass


class RemnawaveGateway:
    """Small boundary around the community Remnawave SDK.

    The rest of VPaNfi does not import SDK DTOs directly. This keeps panel-version
    changes isolated in one module and makes the cabinet easy to test without a
    live panel.
    """

    def __init__(self, settings: Settings) -> None:
        if settings.remnawave_base_url is None or settings.remnawave_api_token is None:
            raise RemnawaveNotConfiguredError(
                "Remnawave URL and API token are required outside demo mode"
            )

        self._sdk = RemnawaveSDK(
            base_url=str(settings.remnawave_base_url).rstrip("/"),
            token=settings.remnawave_api_token.get_secret_value(),
        )

    async def list_users(self) -> list[Mapping[str, Any]]:
        response = await self._sdk.users.get_all_users()
        return [self._to_mapping(user) for user in response.users]

    async def find_user_by_username(self, username: str) -> Mapping[str, Any]:
        normalized = username.casefold()
        for user in await self.list_users():
            if str(user.get("username", "")).casefold() == normalized:
                return user
        raise RemnawaveUserNotFoundError(username)

    @staticmethod
    def _to_mapping(value: object) -> Mapping[str, Any]:
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            dumped = model_dump(mode="json", by_alias=True)
            if isinstance(dumped, Mapping):
                return dumped
        if isinstance(value, Mapping):
            return value
        raise TypeError(f"Unsupported Remnawave response type: {type(value)!r}")
