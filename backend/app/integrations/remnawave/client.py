"""Изолированный адаптер над HTTP API панели Remnawave."""

from collections.abc import Mapping
from types import TracebackType
from typing import Any, Self

import httpx

from app.core.config import Settings

__all__ = [
    "RemnawaveError",
    "RemnawaveGateway",
    "RemnawaveNotConfiguredError",
    "RemnawaveUnavailableError",
    "RemnawaveUserNotFoundError",
]

USERS_PATH = "/api/users"


class RemnawaveError(RuntimeError):
    """Базовая ошибка интеграции с Remnawave."""


class RemnawaveNotConfiguredError(RemnawaveError):
    """URL панели или токен доступа не заданы."""


class RemnawaveUnavailableError(RemnawaveError):
    """Панель недоступна или ответила ошибкой."""


class RemnawaveUserNotFoundError(LookupError):
    """Пользователь с таким именем не найден в панели."""


class RemnawaveGateway:
    """Единственная точка входа VPaNfi в API панели Remnawave.

    Остальные модули не знают ни про URL панели, ни про формат её
    ответов: наружу отдаются обычные словари. Такая изоляция
    позволяет пережить смену версии панели правкой одного файла и
    тестировать кабинет без живой инсталляции.
    """

    def __init__(self, settings: Settings) -> None:
        if (
            settings.remnawave_base_url is None
            or settings.remnawave_api_token is None
        ):
            raise RemnawaveNotConfiguredError(
                "Remnawave URL and API token are required outside demo mode"
            )

        token = settings.remnawave_api_token.get_secret_value()
        self._client = httpx.AsyncClient(
            base_url=str(settings.remnawave_base_url).rstrip("/"),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=settings.remnawave_timeout_seconds,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Закрыть HTTP-соединения с панелью."""
        await self._client.aclose()

    async def list_users(self) -> list[Mapping[str, Any]]:
        """Вернуть всех пользователей панели.

        Returns:
            Список словарей с полями пользователя панели.

        Raises:
            RemnawaveUnavailableError: Панель недоступна или вернула
                неожиданный ответ.
        """
        return _extract_users(await self._get(USERS_PATH))

    async def find_user_by_username(
        self,
        username: str,
    ) -> Mapping[str, Any]:
        """Найти пользователя панели по имени без учёта регистра.

        Args:
            username: Имя пользователя в панели.

        Returns:
            Словарь с полями найденного пользователя.

        Raises:
            RemnawaveUserNotFoundError: Пользователь не найден.
            RemnawaveUnavailableError: Панель недоступна.
        """
        normalized = username.casefold()
        for user in await self.list_users():
            if str(user.get("username", "")).casefold() == normalized:
                return user
        raise RemnawaveUserNotFoundError(username)

    async def _get(self, path: str) -> Any:
        try:
            response = await self._client.get(path)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise RemnawaveUnavailableError(
                f"Remnawave responded with {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RemnawaveUnavailableError(
                "Remnawave panel is unreachable"
            ) from exc
        except ValueError as exc:
            raise RemnawaveUnavailableError(
                "Remnawave returned a non-JSON response"
            ) from exc


def _extract_users(payload: Any) -> list[Mapping[str, Any]]:
    """Достать список пользователей из ответа панели.

    Панель заворачивает полезную нагрузку в ``response``, а внутри
    отдаёт либо массив, либо объект с ключом ``users``. Поддерживаем
    оба варианта, чтобы обновление панели не ломало кабинет.
    """
    body = payload
    if isinstance(body, Mapping):
        body = body.get("response", body)
    if isinstance(body, Mapping):
        body = body.get("users", body)
    if not isinstance(body, list):
        raise RemnawaveUnavailableError(
            "Remnawave returned an unexpected users payload"
        )
    return [user for user in body if isinstance(user, Mapping)]
