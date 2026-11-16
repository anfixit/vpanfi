from uuid import UUID

from app.api.dependencies import get_checkout_service
from app.schemas.cabinet import PaymentStatusResponse
from app.services.checkout import Smeta

CHECKOUT = "/api/v1/payments/checkout"
QUOTE = "/api/v1/payments/quote"
KNOWN_PAYMENT = UUID("22222222-3333-4444-5555-666666666666")


class StubCheckout:
    """Касса без базы и без ЮKassa: маршруты проверяем отдельно от них."""

    async def state(self, payment_id: UUID) -> PaymentStatusResponse | None:
        if payment_id != KNOWN_PAYMENT:
            return None
        return PaymentStatusResponse(
            status="succeeded",
            paid=True,
            subscription_url="https://panel.example/sub/abc",
        )

    async def smeta(
        self, *, email: str, tariff_id: int, period_days: int
    ) -> Smeta:
        return Smeta(
            amount_kopecks=50_000,
            base_kopecks=30_000,
            extra_devices=2,
            devices_limit=5,
            tariff_devices=3,
            description="30 дней, 30 дн., мест: 5",
        )


def test_checkout_rejects_a_price_from_the_browser(anonymous_client) -> None:
    """Сумму принимать нельзя — её назначает сервер."""
    answer = anonymous_client.post(
        CHECKOUT,
        json={
            "email": "guest@example.com",
            "tariffId": 2,
            "periodDays": 30,
            "amountKopecks": 1,
        },
    )

    assert answer.status_code == 422


def test_checkout_without_configured_cash_desk_says_so(
    anonymous_client,
) -> None:
    """Без настроенной кассы сайт обязан сказать это прямо, а не молчать."""
    answer = anonymous_client.post(
        CHECKOUT,
        json={"email": "guest@example.com", "tariffId": 2, "periodDays": 30},
    )

    assert answer.status_code == 503
    assert answer.json()["detail"]["code"] == "payments_not_configured"


def test_unknown_payment_is_not_found(app, anonymous_client) -> None:
    app.dependency_overrides[get_checkout_service] = StubCheckout

    answer = anonymous_client.get(
        "/api/v1/payments/11111111-1111-1111-1111-111111111111"
    )

    app.dependency_overrides.clear()
    assert answer.status_code == 404
    assert answer.json()["detail"]["code"] == "payment_not_found"


def test_paid_payment_shows_the_subscription_link(
    app, anonymous_client
) -> None:
    """После оплаты человеку нужна ссылка, а не слово «успешно»."""
    app.dependency_overrides[get_checkout_service] = StubCheckout

    answer = anonymous_client.get(f"/api/v1/payments/{KNOWN_PAYMENT}")

    app.dependency_overrides.clear()
    assert answer.status_code == 200
    assert answer.json() == {
        "status": "succeeded",
        "paid": True,
        "subscriptionUrl": "https://panel.example/sub/abc",
    }


def test_checkout_accepts_a_referral_code(anonymous_client) -> None:
    """Код приглашения — обычное поле запроса, схема его не отвергает."""
    answer = anonymous_client.post(
        CHECKOUT,
        json={
            "email": "guest@example.com",
            "tariffId": 2,
            "periodDays": 30,
            "ref": "Alyona_Tutina",
        },
    )

    assert answer.status_code != 422


def test_checkout_works_without_a_referral_code(anonymous_client) -> None:
    """Старый фронтенд ref не шлёт вовсе, и запрос должен проходить."""
    answer = anonymous_client.post(
        CHECKOUT,
        json={"email": "guest@example.com", "tariffId": 2, "periodDays": 30},
    )

    assert answer.status_code != 422


def test_quote_is_only_for_the_one_who_logged_in(anonymous_client) -> None:
    """В смете видно, сколько у человека мест: чужим её не отдаём."""
    answer = anonymous_client.post(
        QUOTE, json={"tariffId": 2, "periodDays": 30}
    )

    assert answer.status_code == 401


def test_quote_rejects_an_email_from_the_browser(client) -> None:
    """Почту смета не принимает — иначе по ней спросят чужие места."""
    answer = client.post(
        QUOTE,
        json={
            "tariffId": 2,
            "periodDays": 30,
            "email": "someone-else@example.com",
        },
    )

    assert answer.status_code == 422


def test_quote_shows_the_surcharge_before_the_payment(app, client) -> None:
    """Сумму человек должен видеть до кассы, а не на её странице."""
    app.dependency_overrides[get_checkout_service] = StubCheckout

    answer = client.post(QUOTE, json={"tariffId": 2, "periodDays": 30})

    app.dependency_overrides.pop(get_checkout_service)
    assert answer.status_code == 200
    assert answer.json() == {
        "amountKopecks": 50000,
        "baseKopecks": 30000,
        "extraDevices": 2,
        "devicesLimit": 5,
        "tariffDevices": 3,
    }


def test_checkout_swallows_a_garbage_referral_code(anonymous_client) -> None:
    """Мусорный код не должен ронять покупку отказом 422.

    normalize_code превращает его в None уже внутри CheckoutService —
    схема здесь только не даёт очень длинной строке пройти дальше.
    """
    answer = anonymous_client.post(
        CHECKOUT,
        json={
            "email": "guest@example.com",
            "tariffId": 2,
            "periodDays": 30,
            "ref": "не похоже на имя учётки!! " * 5,
        },
    )

    assert answer.status_code != 422
