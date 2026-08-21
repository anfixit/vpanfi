"""Перевод ответа панели в карточку подписки."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.schemas.cabinet import SubscriptionStatus
from app.services.panel import (
    UnreadablePanelUserError,
    read_panel_user,
    to_device,
    to_subscription,
)

# Панель 3.x отдаёт числовой id и больше не отдаёт uuid.
PANEL_USER_ID = 131


def panel_payload(**overrides: object) -> dict[str, object]:
    """Ответ панели с теми полями, которые она отдаёт на самом деле."""
    payload: dict[str, object] = {
        "id": PANEL_USER_ID,
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


def test_devices_over_the_limit_are_shown_as_they_are() -> None:
    # Подрезка под лимит показывала «2 из 2» тому, у кого в панели пять
    # устройств, и человек не понимал, почему новое не подключается.
    user = read_panel_user(panel_payload(hwidDeviceLimit=2))

    subscription = to_subscription(user, devices_used=5)

    assert subscription.devices_used == 5
    assert subscription.devices_limit == 2


def test_missing_device_limit_falls_back_to_the_tariff() -> None:
    user = read_panel_user(panel_payload(hwidDeviceLimit=None))

    assert to_subscription(user, devices_used=0).devices_limit == 3


def test_unparsable_expiry_does_not_crash_the_cabinet() -> None:
    user = read_panel_user(panel_payload(expireAt="not-a-date"))

    assert user.expires_at == date.today()


def test_plain_number_traffic_counter_is_accepted() -> None:
    user = read_panel_user(panel_payload(userTraffic=2048))

    assert user.used_traffic_bytes == 2048


def test_user_without_id_is_rejected() -> None:
    with pytest.raises(UnreadablePanelUserError):
        read_panel_user(panel_payload(id=None))


def test_old_panel_payload_with_only_uuid_is_rejected() -> None:
    """Ответ панели 2.x кабинету больше не годится.

    До 3.0.0 пользователь адресовался полем ``uuid``. Принять такой
    ответ молча значило бы ходить в панель по идентификатору, на который
    она отвечает 400, — и показывать человеку «Панель недоступна».
    """
    payload = panel_payload()
    del payload["id"]
    payload["uuid"] = "9f1d6d4e-1111-2222-3333-444455556666"

    with pytest.raises(UnreadablePanelUserError):
        read_panel_user(payload)


def test_boolean_is_not_a_user_id() -> None:
    # bool — подкласс int, и True тихо стало бы пользователем номер 1.
    with pytest.raises(UnreadablePanelUserError):
        read_panel_user(panel_payload(id=True))


def test_numeric_id_is_read_as_int() -> None:
    assert read_panel_user(panel_payload()).id == PANEL_USER_ID
    assert read_panel_user(panel_payload(id="131")).id == 131


def test_platform_name_is_not_repeated_in_the_version() -> None:
    device = to_device({
        "hwid": "abc",
        "platform": "Android",
        "osVersion": "Android 16",
        "deviceModel": "samsung SM-S938B",
    })

    assert device.platform == "Android 16"


def test_platform_and_version_are_joined_when_they_differ() -> None:
    device = to_device({
        "hwid": "abc",
        "platform": "iOS",
        "osVersion": "18.2",
    })

    assert device.platform == "iOS 18.2"


def test_device_without_a_version_keeps_the_platform() -> None:
    device = to_device({"hwid": "abc", "platform": "Windows"})

    assert device.platform == "Windows"
