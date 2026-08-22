from app.core.config import get_settings
from app.models.billing import Payment, PaymentPurpose, PaymentStatus
from app.services.checkout import CheckoutService

WEBHOOK = "/api/v1/payments/platega/webhook"


class FakeSession:
    """Сессия без базы: проверяем правило, а не SQL."""

    def __init__(self, payment: Payment | None) -> None:
        self._payment = payment
        self.commits = 0

    async def scalar(self, statement: object) -> Payment | None:
        return self._payment

    async def commit(self) -> None:
        self.commits += 1


def _payment(status: PaymentStatus) -> Payment:
    return Payment(
        user_id=None,
        contact_email="guest@example.com",
        amount_kopecks=30000,
        status=status,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="platega",
        provider_payment_id="tx-1",
        description="30 дней",
        tariff_id=2,
        period_days=30,
    )


def _service(session: FakeSession, settings: object) -> CheckoutService:
    return CheckoutService(session, settings)  # type: ignore[arg-type]


async def test_first_confirmation_wins() -> None:
    """Продлевает подписку только тот вызов, который сам оплатил платёж."""
    payment = _payment(PaymentStatus.PENDING)
    session = FakeSession(payment)
    service = _service(session, get_settings())

    paid = await service.confirm(
        provider_payment_id="tx-1", status_name="CONFIRMED"
    )

    assert paid is True
    assert payment.status is PaymentStatus.SUCCEEDED


async def test_repeated_confirmation_changes_nothing() -> None:
    """Platega шлёт уведомление, пока не увидит 200: повтор не продлевает."""
    payment = _payment(PaymentStatus.SUCCEEDED)
    session = FakeSession(payment)
    service = _service(session, get_settings())

    paid = await service.confirm(
        provider_payment_id="tx-1", status_name="CONFIRMED"
    )

    assert paid is False
    assert session.commits == 0


async def test_failed_status_marks_the_payment() -> None:
    payment = _payment(PaymentStatus.PENDING)
    session = FakeSession(payment)
    service = _service(session, get_settings())

    paid = await service.confirm(
        provider_payment_id="tx-1", status_name="CANCELED"
    )

    assert paid is False
    assert payment.status is PaymentStatus.FAILED


async def test_unknown_payment_is_ignored() -> None:
    session = FakeSession(None)
    service = _service(session, get_settings())

    assert (
        await service.confirm(
            provider_payment_id="tx-404", status_name="CONFIRMED"
        )
        is False
    )


def test_webhook_without_credentials_is_rejected(anonymous_client) -> None:
    answer = anonymous_client.post(
        WEBHOOK,
        json={"id": "tx-1", "status": "CONFIRMED"},
        headers={"X-MerchantId": "wrong", "X-Secret": "wrong"},
    )

    assert answer.status_code == 401


def test_empty_verification_ping_is_answered(anonymous_client) -> None:
    """Platega проверяет адрес пустым запросом до первой оплаты."""
    answer = anonymous_client.post(WEBHOOK, content=b"")

    assert answer.status_code == 200
