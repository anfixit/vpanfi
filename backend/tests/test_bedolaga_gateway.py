from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.core.config import Settings
from app.integrations.bedolaga.client import (
    BedolagaGateway,
    BedolagaNotConfiguredError,
    BedolagaUnavailableError,
    BedolagaUserNotFoundError,
    BotUser,
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


@respx.mock
@pytest.mark.parametrize("days", [0, -5])
async def test_extend_refuses_non_positive_days_before_the_network(
    days: int,
) -> None:
    """Продление неповторяемо, поэтому негодные дни не доходят до сети."""
    route = respx.post(f"{BASE_URL}/subscriptions/777/extend").mock(
        return_value=httpx.Response(200, json={})
    )

    async with _gateway() as gateway:
        with pytest.raises(ValueError):
            await gateway.extend(777, days)

    assert route.call_count == 0


@respx.mock
async def test_user_by_telegram_id_parses_the_referral_fields() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "telegram_id": TELEGRAM_ID,
                "referral_code": "anfisa-42",
                "referred_by_id": 7,
                "has_had_paid_subscription": True,
                "subscription": None,
                "subscriptions": [],
            },
        )
    )

    async with _gateway() as gateway:
        user = await gateway.user_by_telegram_id(TELEGRAM_ID)

    assert user == BotUser(
        id=42,
        telegram_id=TELEGRAM_ID,
        referral_code="anfisa-42",
        referred_by_id=7,
        has_had_paid_subscription=True,
    )


@respx.mock
async def test_user_by_telegram_id_unknown_is_not_found() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(404)
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUserNotFoundError):
            await gateway.user_by_telegram_id(TELEGRAM_ID)


@respx.mock
async def test_user_by_id_fetches_the_numeric_endpoint() -> None:
    route = respx.get(f"{BASE_URL}/users/42").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": 42,
                "telegram_id": None,
                "referral_code": "anfisa-42",
                "referred_by_id": None,
                "has_had_paid_subscription": False,
            },
        )
    )

    async with _gateway() as gateway:
        user = await gateway.user_by_id(42)

    assert user == BotUser(
        id=42,
        telegram_id=None,
        referral_code="anfisa-42",
        referred_by_id=None,
        has_had_paid_subscription=False,
    )
    assert route.calls.last.request.headers["X-API-Key"] == TOKEN


@respx.mock
async def test_user_by_id_unknown_is_not_found() -> None:
    respx.get(f"{BASE_URL}/users/42").mock(return_value=httpx.Response(404))

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUserNotFoundError):
            await gateway.user_by_id(42)


@respx.mock
async def test_user_by_id_failure_becomes_domain_error() -> None:
    respx.get(f"{BASE_URL}/users/42").mock(return_value=httpx.Response(500))

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUnavailableError):
            await gateway.user_by_id(42)


@respx.mock
async def test_list_users_returns_the_page_and_total() -> None:
    route = respx.get(f"{BASE_URL}/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": 1,
                        "telegram_id": 1001,
                        "referral_code": "a",
                        "referred_by_id": None,
                        "has_had_paid_subscription": True,
                    },
                    {
                        "id": 2,
                        "telegram_id": 1002,
                        "referral_code": "b",
                        "referred_by_id": 1,
                        "has_had_paid_subscription": False,
                    },
                ],
                "total": 2,
                "limit": 200,
                "offset": 0,
            },
        )
    )

    async with _gateway() as gateway:
        users, total = await gateway.list_users()

    assert total == 2
    assert [user.id for user in users] == [1, 2]
    query = route.calls.last.request.url.params
    assert query["limit"] == "200"
    assert query["offset"] == "0"


@respx.mock
async def test_list_users_skips_a_malformed_item(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Обломок одного пользователя не должен прерывать обход всех."""
    respx.get(f"{BASE_URL}/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"telegram_id": 1001},  # без id: бракуется целиком
                    {
                        "id": 2,
                        "telegram_id": 1002,
                        "referral_code": None,
                        "referred_by_id": None,
                        "has_had_paid_subscription": True,
                    },
                ],
                "total": 2,
                "limit": 200,
                "offset": 0,
            },
        )
    )

    async with _gateway() as gateway:
        users, total = await gateway.list_users()

    assert total == 2
    assert [user.id for user in users] == [2]
    assert any(
        record.levelname == "WARNING" for record in caplog.records
    )


@respx.mock
async def test_list_users_failure_becomes_domain_error() -> None:
    respx.get(f"{BASE_URL}/users").mock(return_value=httpx.Response(500))

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUnavailableError):
            await gateway.list_users()


@respx.mock
async def test_purchases_walks_every_page_ascending_by_time() -> None:
    """Две страницы транзакций собираются в один список по возрастанию."""
    route = respx.get(f"{BASE_URL}/transactions").mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 1,
                            "user_id": 2,
                            "type": "subscription_payment",
                            "is_completed": True,
                            "created_at": "2027-01-01T00:00:00",
                            "completed_at": "2027-01-02T00:00:00",
                        }
                    ],
                    "total": 2,
                    "limit": 1,
                    "offset": 0,
                },
            ),
            httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "id": 2,
                            "user_id": 2,
                            "type": "subscription_payment",
                            "is_completed": True,
                            "created_at": "2026-12-01T00:00:00",
                            "completed_at": "2026-12-05T00:00:00",
                        }
                    ],
                    "total": 2,
                    "limit": 1,
                    "offset": 1,
                },
            ),
        ]
    )

    async with _gateway() as gateway:
        purchases = await gateway.purchases(2)

    assert [purchase.id for purchase in purchases] == [2, 1]
    assert purchases[0].completed_at < purchases[1].completed_at
    first_request = route.calls[0].request
    query = first_request.url.params
    assert query["user_id"] == "2"
    assert query["type"] == "subscription_payment"
    assert query["is_completed"] == "true"


@respx.mock
async def test_purchases_falls_back_to_created_at_when_completed_at_is_null(
) -> None:
    respx.get(f"{BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": 1,
                        "user_id": 2,
                        "type": "subscription_payment",
                        "is_completed": True,
                        "created_at": "2027-01-01T00:00:00",
                        "completed_at": None,
                    }
                ],
                "total": 1,
                "limit": 200,
                "offset": 0,
            },
        )
    )

    async with _gateway() as gateway:
        purchases = await gateway.purchases(2)

    assert len(purchases) == 1
    assert purchases[0].completed_at == datetime(
        2027, 1, 1, tzinfo=UTC
    )


@respx.mock
async def test_purchases_skips_a_malformed_transaction(
    caplog: pytest.LogCaptureFixture,
) -> None:
    respx.get(f"{BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"user_id": 2},  # без id транзакции
                    {
                        "id": 2,
                        "user_id": 2,
                        "created_at": "2027-01-01T00:00:00",
                        "completed_at": "2027-01-02T00:00:00",
                    },
                ],
                "total": 2,
                "limit": 200,
                "offset": 0,
            },
        )
    )

    async with _gateway() as gateway:
        purchases = await gateway.purchases(2)

    assert [purchase.id for purchase in purchases] == [2]
    assert any(
        record.levelname == "WARNING" for record in caplog.records
    )


@respx.mock
async def test_purchases_stops_at_an_empty_page() -> None:
    """total лжёт про число страниц: пустая страница обрывает обход."""
    route = respx.get(f"{BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            200,
            json={"items": [], "total": 999, "limit": 200, "offset": 0},
        )
    )

    async with _gateway() as gateway:
        purchases = await gateway.purchases(2)

    assert purchases == []
    assert route.call_count == 1


@respx.mock
async def test_purchases_stops_after_the_hard_page_cap() -> None:
    """Неверный total на стороне бота не должен превратить обход в вечный
    цикл: потолок в 20 страниц останавливает его сам.
    """

    def _page(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": offset + 1,
                        "user_id": 2,
                        "created_at": "2027-01-01T00:00:00",
                        "completed_at": "2027-01-01T00:00:00",
                    }
                ],
                # total всегда больше того, что реально отдано: без
                # потолка страниц обход не остановился бы сам.
                "total": 10_000,
                "limit": 1,
                "offset": offset,
            },
        )

    route = respx.get(f"{BASE_URL}/transactions").mock(side_effect=_page)

    async with _gateway() as gateway:
        purchases = await gateway.purchases(2)

    assert route.call_count == 20
    assert len(purchases) == 20


@respx.mock
async def test_purchases_never_leaks_the_token_on_failure() -> None:
    respx.get(f"{BASE_URL}/transactions").mock(
        return_value=httpx.Response(500)
    )

    async with _gateway() as gateway:
        with pytest.raises(BedolagaUnavailableError) as exc_info:
            await gateway.purchases(2)

    assert TOKEN not in str(exc_info.value)
