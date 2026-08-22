from app.models.billing import Payment, PaymentPurpose, PaymentStatus


def test_payment_can_belong_to_a_guest() -> None:
    """Гость платит по почте, аккаунта у него может не быть вовсе."""
    payment = Payment(
        user_id=None,
        contact_email="guest@example.com",
        amount_kopecks=30000,
        status=PaymentStatus.PENDING,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="platega",
        description="Подписка на 30 дней",
        tariff_id=2,
        period_days=30,
    )

    assert payment.user_id is None
    assert payment.contact_email == "guest@example.com"
    assert payment.period_days == 30
    assert payment.subscription_url is None
