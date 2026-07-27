import httpx
import pytest
import respx

from app.core.config import Settings
from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveNotConfiguredError,
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)

PANEL_URL = "https://panel.example.test"
USERS_URL = f"{PANEL_URL}/api/users"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        remnawave_base_url=PANEL_URL,
        remnawave_api_token="test-token",
    )


def test_gateway_requires_credentials() -> None:
    with pytest.raises(RemnawaveNotConfiguredError):
        RemnawaveGateway(Settings(_env_file=None))


@respx.mock
async def test_list_users_unwraps_panel_envelope() -> None:
    respx.get(USERS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"response": {"users": [{"username": "anfisa"}]}},
        )
    )

    async with RemnawaveGateway(_settings()) as gateway:
        users = await gateway.list_users()

    assert users == [{"username": "anfisa"}]


@respx.mock
async def test_find_user_ignores_case() -> None:
    respx.get(USERS_URL).mock(
        return_value=httpx.Response(
            200,
            json={"response": [{"username": "Anfisa"}]},
        )
    )

    async with RemnawaveGateway(_settings()) as gateway:
        user = await gateway.find_user_by_username("ANFISA")

    assert user["username"] == "Anfisa"


@respx.mock
async def test_missing_user_raises_lookup_error() -> None:
    respx.get(USERS_URL).mock(
        return_value=httpx.Response(200, json={"response": []})
    )

    async with RemnawaveGateway(_settings()) as gateway:
        with pytest.raises(RemnawaveUserNotFoundError):
            await gateway.find_user_by_username("anfisa")


@respx.mock
async def test_panel_error_becomes_domain_error() -> None:
    respx.get(USERS_URL).mock(return_value=httpx.Response(500))

    async with RemnawaveGateway(_settings()) as gateway:
        with pytest.raises(RemnawaveUnavailableError):
            await gateway.list_users()


@respx.mock
async def test_unreachable_panel_becomes_domain_error() -> None:
    respx.get(USERS_URL).mock(side_effect=httpx.ConnectError("down"))

    async with RemnawaveGateway(_settings()) as gateway:
        with pytest.raises(RemnawaveUnavailableError):
            await gateway.list_users()
