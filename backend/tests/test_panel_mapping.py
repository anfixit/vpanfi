"""Перевод ответа панели в карточку подписки."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.schemas.cabinet import SubscriptionStatus
from app.services.panel import (
    UnreadablePanelUserError,
    read_panel_user,
    to_subscription,
)

PANEL_UUID = "9f1d6d4e-1111-2222-3333-444455556666"


def panel_payload(**overrides: object) -> dict[str, object]:
    """Ответ панели с теми полями, которые она отдаёт на самом деле."""
    payload: dict[str, object] = {
        "uuid": PANEL_UUID,
        "shortUuid": "abcd1234efgh",
        "username": "anfisa",
        "status": "ACTIVE",
        "expireAt": (
            datetime.now(UTC) + timedelta(days=30)
        ).isoformat(),
        "trafficLimitBytes": 0,
        "hwidDeviceLimit": 3,
        "subscriptionUrl": "https://panel.example/sub/abcd1234efgh",
        "telegramId": 42,
        "userTraffic": {"usedTrafficBytes": 1024},
    }
    payload.update(overrides)
    return payload


def test_active_subscription_is_readable() -> None:
    user = read_panel_user(panel_payload())
    subscription = to_subscription(user, devices_used=2)

    assert subscription.status is SubscriptionStatus.ACTIVE
    assert subscription.days_left in (29, 30)
    assert subscription.traffic_label == "Без лимита"
    assert subscription.devices_limit == 3
    assert subscription.devices_used == 2


def test_traffic_limit_is_shown_in_gigabytes() -> None:
    user = read_panel_user(
        panel_payload(trafficLimitBytes=50 * 1024**3)
    )

    assert to_subscription(user, devices_used=0).traffic_label == "50 ГБ"


def test_limited_status_reads_as_disabled() -> None:
    user = read_panel_user(panel_payload(status="LIMITED"))

    assert to_subscription(user, devices_used=0).status is (
        SubscriptionStatus.DISABLED
    )


def test_past_expiry_wins_over_a_stale_active_status() -> None:
    # Панель не всегда успевает перевести пользователя в EXPIRED.
    expired = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    user = read_panel_user(panel_payload(status="ACTIVE", expireAt=expired))
    subscription = to_subscription(user, devices_used=0)

    assert subscription.status is SubscriptionStatus.EXPIRED
    assert subscription.days_left == 0


def test_devices_used_never_exceeds_the_limit() -> None:
    user = read_panel_user(panel_payload(hwidDeviceLimit=2))

    assert to_subscription(user, devices_used=5).devices_used == 2


def test_missing_device_limit_falls_back_to_the_tariff() -> None:
    user = read_panel_user(panel_payload(hwidDeviceLimit=None))

    assert to_subscription(user, devices_used=0).devices_limit == 3


def test_unparsable_expiry_does_not_crash_the_cabinet() -> None:
    user = read_panel_user(panel_payload(expireAt="not-a-date"))

    assert user.expires_at == date.today()


def test_plain_number_traffic_counter_is_accepted() -> None:
    user = read_panel_user(panel_payload(userTraffic=2048))

    assert user.used_traffic_bytes == 2048


def test_user_without_uuid_is_rejected() -> None:
    with pytest.raises(UnreadablePanelUserError):
        read_panel_user(panel_payload(uuid=None))
