from uuid import UUID

from app.api.dependencies import get_checkout_service
from app.schemas.cabinet import PaymentStatusResponse

CHECKOUT = "/api/v1/payments/checkout"
KNOWN_PAYMENT = UUID("22222222-3333-4444-5555-666666666666")


class StubCheckout:
    """Касса без базы и без Platega: маршруты проверяем отдельно от них."""

    async def state(self, payment_id: UUID) -> PaymentStatusResponse | None:
        if payment_id != KNOWN_PAYMENT:
            return None
        return PaymentStatusResponse(
            status="succeeded",
            paid=True,
            subscription_url="https://panel.example/sub/abc",
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
