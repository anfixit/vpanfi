"""Изолированный адаптер над HTTP API панели Remnawave.

Панель — единственный источник правды о подписках: тем же данным
управляет Telegram-бот. Поэтому кабинет ничего не кэширует у себя, а
каждый запрос идёт в панель через этот модуль. Наружу отдаются обычные
словари, чтобы смена версии панели правилась в одном файле.
"""

from collections.abc import Mapping
from datetime import datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse
from uuid import UUID

import httpx

from app.core.config import Settings

__all__ = [
    "RemnawaveError",
    "RemnawaveGateway",
    "RemnawaveNotConfiguredError",
    "RemnawaveUnavailableError",
    "RemnawaveUserNotFoundError",
    "extract_short_uuid",
]

USERS_PATH = "/api/users"
HWID_DEVICES_PATH = "/api/hwid/devices"

# Панель принимает и отдаёт короткий идентификатор подписки в пути
# ссылки вида https://panel.example/sub/<shortUuid>.
MIN_SHORT_UUID_LENGTH = 8
MAX_SHORT_UUID_LENGTH = 64


class RemnawaveError(RuntimeError):
    """Базовая ошибка интеграции с Remnawave."""


class RemnawaveNotConfiguredError(RemnawaveError):
    """URL панели или токен доступа не заданы."""


class RemnawaveUnavailableError(RemnawaveError):
    """Панель недоступна или ответила ошибкой."""


class RemnawaveUserNotFoundError(LookupError):
    """Пользователь не найден в панели."""


def extract_short_uuid(subscription_link: str) -> str | None:
    """Достать короткий идентификатор из ссылки на подписку.

    Пользователь приносит ссылку из бота, и она бывает в разном виде:
    полный URL, URL с query-строкой или просто сам идентификатор.

    Args:
        subscription_link: То, что пользователь вставил в поле.

    Returns:
        Короткий идентификатор или None, если распознать не удалось.
    """
    candidate = subscription_link.strip()
    if not candidate:
        return None

    if "://" in candidate:
        candidate = urlparse(candidate).path

    candidate = candidate.strip("/").split("?", 1)[0]
    if not candidate:
        return None

    tail = candidate.rsplit("/", 1)[-1]
    if not tail.replace("-", "").replace("_", "").isalnum():
        return None
    if not MIN_SHORT_UUID_LENGTH <= len(tail) <= MAX_SHORT_UUID_LENGTH:
        return None

    return tail


class RemnawaveGateway:
    """Единственная точка входа VPaNfi в API панели Remnawave."""

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

    async def get_user_by_uuid(self, user_uuid: UUID) -> Mapping[str, Any]:
        """Вернуть пользователя панели по его UUID."""
        return _as_user(await self._get(f"{USERS_PATH}/{user_uuid}"))

    async def get_user_by_short_uuid(
        self,
        short_uuid: str,
    ) -> Mapping[str, Any]:
        """Вернуть пользователя по короткому идентификатору подписки."""
        return _as_user(
            await self._get(f"{USERS_PATH}/by-short-uuid/{short_uuid}")
        )

    async def get_user_by_username(
        self,
        username: str,
    ) -> Mapping[str, Any]:
        """Вернуть пользователя панели по имени."""
        return _as_user(
            await self._get(f"{USERS_PATH}/by-username/{username}")
        )

    async def get_user_by_telegram_id(
        self,
        telegram_id: int,
    ) -> Mapping[str, Any]:
        """Вернуть пользователя панели по Telegram-идентификатору."""
        payload = await self._get(
            f"{USERS_PATH}/by-telegram-id/{telegram_id}"
        )
        body = _unwrap(payload)
        # Эта ручка отдаёт массив: у одного Telegram-аккаунта может быть
        # несколько пользователей панели.
        if isinstance(body, list):
            if not body:
                raise RemnawaveUserNotFoundError(str(telegram_id))
            first = body[0]
            if not isinstance(first, Mapping):
                raise RemnawaveUnavailableError(
                    "Remnawave returned an unexpected user payload"
                )
            return first
        return _as_user(payload)

    async def create_user(
        self,
        *,
        username: str,
        expire_at: datetime,
        telegram_id: int | None = None,
        email: str | None = None,
        traffic_limit_bytes: int = 0,
        hwid_device_limit: int | None = None,
    ) -> Mapping[str, Any]:
        """Завести пользователя в панели.

        Вызывается только для аккаунта, к которому ещё ничего не
        привязано, иначе в панели появится дубль.
        """
        body: dict[str, Any] = {
            "username": username,
            "expireAt": _to_panel_time(expire_at),
            "trafficLimitBytes": traffic_limit_bytes,
            "status": "ACTIVE",
        }
        if telegram_id is not None:
            body["telegramId"] = telegram_id
        if email is not None:
            body["email"] = email
        if hwid_device_limit is not None:
            body["hwidDeviceLimit"] = hwid_device_limit

        return _as_user(await self._request("POST", USERS_PATH, json=body))

    async def set_expiry(
        self,
        user_uuid: UUID,
        expire_at: datetime,
    ) -> Mapping[str, Any]:
        """Передвинуть дату окончания подписки."""
        body = {
            "uuid": str(user_uuid),
            "expireAt": _to_panel_time(expire_at),
        }
        return _as_user(await self._request("PATCH", USERS_PATH, json=body))

    async def list_devices(self, user_uuid: UUID) -> list[Mapping[str, Any]]:
        """Вернуть устройства, привязанные к пользователю панели."""
        payload = await self._get(f"{HWID_DEVICES_PATH}/{user_uuid}")
        body = _unwrap(payload)
        if isinstance(body, Mapping):
            body = body.get("devices", body)
        if not isinstance(body, list):
            raise RemnawaveUnavailableError(
                "Remnawave returned an unexpected devices payload"
            )
        return [device for device in body if isinstance(device, Mapping)]

    async def delete_device(self, user_uuid: UUID, hwid: str) -> None:
        """Отвязать устройство от пользователя панели."""
        await self._request(
            "POST",
            f"{HWID_DEVICES_PATH}/delete",
            json={"userUuid": str(user_uuid), "hwid": hwid},
        )

    async def _get(self, path: str) -> Any:
        return await self._request("GET", path)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
    ) -> Any:
        try:
            response = await self._client.request(method, path, json=json)
            if response.status_code == httpx.codes.NOT_FOUND:
                raise RemnawaveUserNotFoundError(path)
            response.raise_for_status()
            if not response.content:
                return None
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


def _to_panel_time(moment: datetime) -> str:
    return moment.astimezone().isoformat()


def _unwrap(payload: Any) -> Any:
    """Снять обёртку ``response``, которой панель оборачивает ответ."""
    if isinstance(payload, Mapping) and "response" in payload:
        return payload["response"]
    return payload


def _as_user(payload: Any) -> Mapping[str, Any]:
    body = _unwrap(payload)
    if not isinstance(body, Mapping):
        raise RemnawaveUnavailableError(
            "Remnawave returned an unexpected user payload"
        )
    return body
