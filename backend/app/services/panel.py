"""Перевод ответов панели в то, что видит пользователь кабинета."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from app.schemas.cabinet import (
    DeviceResponse,
    SubscriptionResponse,
    SubscriptionStatus,
)

__all__ = [
    "PanelUser",
    "UnreadablePanelUserError",
    "read_panel_user",
    "to_device",
    "to_subscription",
]

BYTES_IN_GIGABYTE = 1024**3
UNLIMITED_TRAFFIC_LABEL = "Без лимита"
DEFAULT_DEVICES_LIMIT = 3
DEFAULT_PLAN_NAME = "Подписка"

# Панель различает больше состояний, чем нужно показывать человеку.
PANEL_STATUS_MAP = {
    "ACTIVE": SubscriptionStatus.ACTIVE,
    "EXPIRED": SubscriptionStatus.EXPIRED,
    "DISABLED": SubscriptionStatus.DISABLED,
    "LIMITED": SubscriptionStatus.DISABLED,
}


class UnreadablePanelUserError(ValueError):
    """Панель вернула пользователя без обязательных полей."""


class PanelUser:
    """Пользователь панели в терминах кабинета."""

    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.raw = payload
        self.uuid = _read_uuid(payload)
        self.username = str(payload.get("username") or "")
        self.short_uuid = _optional_str(payload.get("shortUuid"))
        self.subscription_url = _optional_str(payload.get("subscriptionUrl"))
        self.status = PANEL_STATUS_MAP.get(
            str(payload.get("status", "")).upper(),
            SubscriptionStatus.DISABLED,
        )
        self.expires_at = _read_expiry(payload)
        self.traffic_limit_bytes = _read_int(payload.get("trafficLimitBytes"))
        self.used_traffic_bytes = _read_used_traffic(payload)
        self.devices_limit = (
            _read_int(payload.get("hwidDeviceLimit")) or DEFAULT_DEVICES_LIMIT
        )


def read_panel_user(payload: Mapping[str, Any]) -> PanelUser:
    """Разобрать ответ панели.

    Raises:
        UnreadablePanelUserError: Если нет UUID пользователя.
    """
    return PanelUser(payload)


def to_subscription(
    user: PanelUser,
    *,
    devices_used: int,
    balance_rub: int = 0,
    auto_renew_enabled: bool = False,
) -> SubscriptionResponse:
    """Собрать карточку подписки из данных панели."""
    today = date.today()
    expires_at = user.expires_at
    days_left = max(0, (expires_at - today).days)
    status = user.status

    # Панель может ещё не успеть перевести пользователя в EXPIRED, а дата
    # уже прошла: человеку важнее дата, чем внутренний статус.
    if status is SubscriptionStatus.ACTIVE and days_left == 0:
        status = SubscriptionStatus.EXPIRED

    return SubscriptionResponse(
        status=status,
        plan_name=DEFAULT_PLAN_NAME,
        days_left=days_left,
        expires_at=expires_at,
        traffic_label=_traffic_label(user.traffic_limit_bytes),
        devices_used=min(devices_used, user.devices_limit),
        devices_limit=user.devices_limit,
        auto_renew_enabled=auto_renew_enabled,
        balance_rub=balance_rub,
    )


def _traffic_label(limit_bytes: int) -> str:
    if limit_bytes <= 0:
        return UNLIMITED_TRAFFIC_LABEL

    gigabytes = limit_bytes / BYTES_IN_GIGABYTE
    if gigabytes >= 1:
        return f"{gigabytes:.0f} ГБ"
    return f"{limit_bytes / (1024 ** 2):.0f} МБ"


def _read_uuid(payload: Mapping[str, Any]) -> UUID:
    raw = payload.get("uuid")
    try:
        return UUID(str(raw))
    except (TypeError, ValueError) as error:
        raise UnreadablePanelUserError(
            "Remnawave user has no usable uuid"
        ) from error


def _read_expiry(payload: Mapping[str, Any]) -> date:
    raw = payload.get("expireAt")
    if not raw:
        return date.today()

    text = str(raw).replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return date.today()

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).date()


def _read_used_traffic(payload: Mapping[str, Any]) -> int:
    """Прочитать израсходованный трафик.

    Панель отдаёт его в поле ``userTraffic``, и в разных версиях это либо
    число, либо объект со счётчиками.
    """
    raw = payload.get("userTraffic")
    if isinstance(raw, Mapping):
        for key in ("usedTrafficBytes", "used", "total"):
            if key in raw:
                return _read_int(raw[key])
        return 0
    return _read_int(raw)


def _read_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _optional_str(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def to_device(
    payload: Mapping[str, Any],
    *,
    current_hwid: str | None = None,
) -> DeviceResponse:
    """Собрать карточку устройства из HWID-записи панели."""
    hwid = str(payload.get("hwid") or "")
    model = _optional_str(payload.get("deviceModel"))
    platform = _optional_str(payload.get("platform")) or "Устройство"
    version = _optional_str(payload.get("osVersion"))

    return DeviceResponse(
        id=hwid or "unknown",
        name=model or platform,
        platform=f"{platform} {version}".strip() if version else platform,
        last_seen_at=_read_moment(payload.get("updatedAt")),
        created_at=(
            _read_moment(payload.get("createdAt")) or datetime.now(UTC)
        ),
        current=bool(current_hwid) and hwid == current_hwid,
    )


def _read_moment(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment
