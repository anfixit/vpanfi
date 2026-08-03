from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest
import respx

from app.core.config import Settings
from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveNotConfiguredError,
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
    extract_short_uuid,
)

PANEL_URL = "https://panel.example.test"
USERS_URL = f"{PANEL_URL}/api/users"
USER_UUID = UUID("9f1d6d4e-1111-2222-3333-444455556666")
SHORT_UUID = "abcd1234efgh"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        remnawave_base_url=PANEL_URL,
        remnawave_api_token="test-token",
    )


def _gateway() -> RemnawaveGateway:
    return RemnawaveGateway(_settings())


def test_gateway_requires_credentials() -> None:
    with pytest.raises(RemnawaveNotConfiguredError):
        RemnawaveGateway(Settings(_env_file=None))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (f"https://panel.example/sub/{SHORT_UUID}", SHORT_UUID),
        (f"https://panel.example/sub/{SHORT_UUID}/", SHORT_UUID),
        (f"https://panel.example/sub/{SHORT_UUID}?format=v2ray", SHORT_UUID),
        (f"  {SHORT_UUID}  ", SHORT_UUID),
        ("", None),
        ("https://panel.example/sub/", None),
        ("short", None),
        ("https://panel.example/sub/has spaces here", None),
    ],
)
def test_extract_short_uuid(value: str, expected: str | None) -> None:
    assert extract_short_uuid(value) == expected


@respx.mock
async def test_lookup_by_short_uuid_unwraps_the_envelope() -> None:
    respx.get(f"{USERS_URL}/by-short-uuid/{SHORT_UUID}").mock(
        return_value=httpx.Response(
            200,
            json={"response": {"uuid": str(USER_UUID), "username": "anfisa"}},
        )
    )

    async with _gateway() as gateway:
        user = await gateway.get_user_by_short_uuid(SHORT_UUID)

    assert user["uuid"] == str(USER_UUID)


@respx.mock
async def test_unknown_subscription_raises_lookup_error() -> None:
    respx.get(f"{USERS_URL}/by-short-uuid/{SHORT_UUID}").mock(
        return_value=httpx.Response(404)
    )

    async with _gateway() as gateway:
        with pytest.raises(RemnawaveUserNotFoundError):
            await gateway.get_user_by_short_uuid(SHORT_UUID)


@respx.mock
async def test_create_user_sends_the_panel_payload() -> None:
    route = respx.post(USERS_URL).mock(
        return_value=httpx.Response(
            201, json={"response": {"uuid": str(USER_UUID)}}
        )
    )

    async with _gateway() as gateway:
        await gateway.create_user(
            username="anfisa",
            expire_at=datetime(2027, 1, 1, tzinfo=UTC),
        )

    body = route.calls.last.request.content.decode()
    assert '"username":"anfisa"' in body
    assert '"status":"ACTIVE"' in body
    # Личность из Telegram к пользователю панели не привязывается:
    # подписку находит только её собственная ссылка.
    assert "telegramId" not in body


@respx.mock
async def test_set_expiry_patches_the_user() -> None:
    route = respx.patch(USERS_URL).mock(
        return_value=httpx.Response(
            200, json={"response": {"uuid": str(USER_UUID)}}
        )
    )

    async with _gateway() as gateway:
        await gateway.set_expiry(USER_UUID, datetime(2027, 6, 1, tzinfo=UTC))

    body = route.calls.last.request.content.decode()
    assert str(USER_UUID) in body
    assert "2027-06-01" in body


@respx.mock
async def test_list_devices_accepts_both_payload_shapes() -> None:
    url = f"{PANEL_URL}/api/hwid/devices/{USER_UUID}"
    respx.get(url).mock(
        return_value=httpx.Response(
            200,
            json={"response": {"devices": [{"hwid": "device-1"}]}},
        )
    )

    async with _gateway() as gateway:
        devices = await gateway.list_devices(USER_UUID)

    assert devices == [{"hwid": "device-1"}]


@respx.mock
async def test_delete_device_posts_the_pair() -> None:
    route = respx.post(f"{PANEL_URL}/api/hwid/devices/delete").mock(
        return_value=httpx.Response(200, json={"response": {}})
    )

    async with _gateway() as gateway:
        await gateway.delete_device(USER_UUID, "device-1")

    body = route.calls.last.request.content.decode()
    assert '"hwid":"device-1"' in body
    assert str(USER_UUID) in body


@respx.mock
async def test_panel_error_becomes_domain_error() -> None:
    respx.get(f"{USERS_URL}/{USER_UUID}").mock(
        return_value=httpx.Response(500)
    )

    async with _gateway() as gateway:
        with pytest.raises(RemnawaveUnavailableError):
            await gateway.get_user_by_uuid(USER_UUID)


@respx.mock
async def test_unreachable_panel_becomes_domain_error() -> None:
    respx.get(f"{USERS_URL}/{USER_UUID}").mock(
        side_effect=httpx.ConnectError("down")
    )

    async with _gateway() as gateway:
        with pytest.raises(RemnawaveUnavailableError):
            await gateway.get_user_by_uuid(USER_UUID)
