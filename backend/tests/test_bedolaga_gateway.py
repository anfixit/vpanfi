import httpx
import pytest
import respx

from app.core.config import Settings
from app.integrations.bedolaga.client import (
    BedolagaGateway,
    BedolagaNotConfiguredError,
    BedolagaUnavailableError,
    BedolagaUserNotFoundError,
)

BASE_URL = "https://bedolaga.example.test/api"
TELEGRAM_ID = 100500
TOKEN = "s3cret-bedolaga-token"


def _settings(*, token: str | None = TOKEN) -> Settings:
    return Settings(
        _env_file=None,
        bedolaga_api_url=BASE_URL,
        bedolaga_api_token=token,
    )


def _gateway(*, token: str | None = TOKEN) -> BedolagaGateway:
    return BedolagaGateway(_settings(token=token))


def test_gateway_requires_a_token() -> None:
    with pytest.raises(BedolagaNotConfiguredError):
        BedolagaGateway(_settings(token=None))


@respx.mock
async def test_lookup_takes_the_primary_subscription() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "telegram_id": TELEGRAM_ID,
                "subscription": {
                    "id": 777,
                    "is_trial": False,
                    "end_date": "2027-01-01T00:00:00",
                    "status": "active",
                },
                "subscriptions": [],
            },
        )
    )

    async with _gateway() as gateway:
        subscription_id = await gateway.subscription_id_by_telegram_id(
            TELEGRAM_ID
        )

    assert subscription_id == 777


@respx.mock
async def test_lookup_sends_the_api_key_header() -> None:
    route = respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "subscription": {
                    "id": 1,
                    "is_trial": False,
                    "end_date": "2027-01-01T00:00:00",
                },
                "subscriptions": [],
            },
        )
    )

    async with _gateway() as gateway:
        await gateway.subscription_id_by_telegram_id(TELEGRAM_ID)

    assert route.calls.last.request.headers["X-API-Key"] == TOKEN


@respx.mock
async def test_lookup_falls_back_to_the_latest_paid_subscription() -> None:
    """Пустая или пробная основная подписка не мешает найти платную."""
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "subscription": None,
                "subscriptions": [
                    {
                        "id": 1,
                        "is_trial": True,
                        "end_date": "2027-06-01T00:00:00",
                    },
                    {
                        "id": 2,
                        "is_trial": False,
                        "end_date": "2026-12-01T00:00:00",
                    },
                    {
                        "id": 3,
                        "is_trial": False,
                        # Метка Z должна распознаваться так же, как смещение.
                        "end_date": "2027-03-01T00:00:00Z",
                    },
                ],
            },
        )
    )

    async with _gateway() as gateway:
        subscription_id = await gateway.subscription_id_by_telegram_id(
            TELEGRAM_ID
        )

    assert subscription_id == 3


@respx.mock
async def test_trial_primary_subscription_is_skipped() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "subscription": {
                    "id": 1,
                    "is_trial": True,
                    "end_date": "2027-06-01T00:00:00",
                },
                "subscriptions": [
                    {
                        "id": 2,
                        "is_trial": False,
                        "end_date": "2026-12-01T00:00:00",
                    },
                ],
            },
        )
    )

    async with _gateway() as gateway:
        subscription_id = await gateway.subscription_id_by_telegram_id(
            TELEGRAM_ID
        )

    assert subscription_id == 2


@respx.mock
async def test_only_trial_subscriptions_is_not_found() -> None:
    """Награда за рефералку не должна превращать пробную подписку в платную."""
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "subscription": None,
                "subscriptions": [
                    {
                        "id": 1,
                        "is_trial": True,
                        "end_date": "2027-06-01T00:00:00",
                    },
                ],
            },
        )
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUserNotFoundError):
            await gateway.subscription_id_by_telegram_id(TELEGRAM_ID)


@respx.mock
async def test_unknown_telegram_id_is_not_found() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(404)
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUserNotFoundError):
            await gateway.subscription_id_by_telegram_id(TELEGRAM_ID)


@respx.mock
async def test_lookup_failure_becomes_domain_error() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(500)
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUnavailableError):
            await gateway.subscription_id_by_telegram_id(TELEGRAM_ID)


@respx.mock
async def test_unreachable_bedolaga_becomes_domain_error() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        side_effect=httpx.ConnectError("down")
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUnavailableError):
            await gateway.subscription_id_by_telegram_id(TELEGRAM_ID)


@respx.mock
async def test_extend_sends_days_and_the_api_key() -> None:
    route = respx.post(f"{BASE_URL}/subscriptions/777/extend").mock(
        return_value=httpx.Response(
            200,
            json={"id": 777, "end_date": "2027-02-01T00:00:00"},
        )
    )

    async with _gateway() as gateway:
        await gateway.extend(777, 30)

    request = route.calls.last.request
    assert request.content.decode() == '{"days":30}'
    assert request.headers["X-API-Key"] == TOKEN


@respx.mock
async def test_extend_failure_becomes_domain_error() -> None:
    respx.post(f"{BASE_URL}/subscriptions/777/extend").mock(
        return_value=httpx.Response(
            500, json={"detail": "Failed to sync with Remnawave"}
        )
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUnavailableError):
            await gateway.extend(777, 30)


@respx.mock
async def test_extend_is_not_retried_on_failure() -> None:
    """extend не идемпотентен: шлюз не должен повторять запрос сам."""
    route = respx.post(f"{BASE_URL}/subscriptions/777/extend").mock(
        return_value=httpx.Response(500)
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUnavailableError):
            await gateway.extend(777, 30)

    assert route.call_count == 1


@respx.mock
async def test_error_text_never_contains_the_token() -> None:
    respx.post(f"{BASE_URL}/subscriptions/777/extend").mock(
        return_value=httpx.Response(
            500, json={"detail": "Failed to sync with Remnawave"}
        )
    )
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        side_effect=httpx.ConnectError("down")
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUnavailableError) as extend_exc:
            await gateway.extend(777, 30)
        with pytest.raises(BedolagaUnavailableError) as lookup_exc:
            await gateway.subscription_id_by_telegram_id(TELEGRAM_ID)

    for exc_info in (extend_exc, lookup_exc):
        assert TOKEN not in str(exc_info.value)
        assert TOKEN not in repr(exc_info.value)
        # Тело ответа тоже не должно попадать в текст ошибки.
        assert "Failed to sync with Remnawave" not in str(exc_info.value)
