from datetime import date

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services.letters import subscription_ready_letter
from app.services.mail import Mailer, MailNotConfiguredError, build_message

LETTER = subscription_ready_letter(
    subscription_url="https://panel.example/sub/abc",
    expires_at=date(2026, 9, 21),
    support_url="https://t.me/Anfikus",
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "smtp_host": "smtp.example.test",
        "smtp_port": 2525,
        "smtp_user": "user",
        "smtp_password": SecretStr("secret"),
        "smtp_from_email": "noreply@vpanfi.su",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_mail_is_not_configured_without_a_host() -> None:
    assert _settings(smtp_host=None).is_mail_configured is False


def test_mail_is_configured_when_the_relay_is_described() -> None:
    assert _settings().is_mail_configured is True


def test_mailer_refuses_to_start_without_settings() -> None:
    with pytest.raises(MailNotConfiguredError):
        Mailer(Settings(_env_file=None))


def test_message_carries_both_forms_and_a_readable_sender() -> None:
    """Простой текст нужен для почтовиков, которые не показывают разметку."""
    message = build_message(
        letter=LETTER,
        to_email="guest@example.com",
        from_email="noreply@vpanfi.su",
        from_name="VPaNfi",
    )

    assert message["To"] == "guest@example.com"
    assert message["From"] == "VPaNfi <noreply@vpanfi.su>"
    assert message["Subject"] == "Ваша подписка VPaNfi готова"

    kinds = {part.get_content_type() for part in message.walk()}
    assert "text/plain" in kinds
    assert "text/html" in kinds


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


async def test_letter_is_sent_once_even_if_delivery_repeats(
    monkeypatch,
) -> None:
    """Platega уведомляет повторно — письмо дублироваться не должно."""
    from datetime import UTC, datetime

    from app.models.billing import Payment, PaymentPurpose, PaymentStatus
    from app.services import checkout as checkout_module

    sent: list[str] = []

    class StubMailer:
        def __init__(self, settings: object) -> None:
            pass

        async def send(self, *, to_email: str, letter: object) -> bool:
            sent.append(to_email)
            return True

    monkeypatch.setattr(checkout_module, "Mailer", StubMailer)

    payment = Payment(
        user_id=None,
        contact_email="guest@example.com",
        amount_kopecks=30000,
        status=PaymentStatus.SUCCEEDED,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="platega",
        description="30 дней",
        period_days=30,
        subscription_url="https://panel.example/sub/abc",
    )
    session = FakeSession()
    service = checkout_module.CheckoutService(session, _settings())  # type: ignore[arg-type]

    await service._notify(payment, date(2026, 9, 21))
    assert sent == ["guest@example.com"]
    assert payment.notified_at is not None

    # Второй заход: письмо уже отправлено, отметка стоит.
    await service._notify(payment, date(2026, 9, 21))
    assert sent == ["guest@example.com"]


async def test_no_letter_without_a_configured_relay(monkeypatch) -> None:
    """Без почтового узла выдача не должна падать — только предупредить."""
    from app.models.billing import Payment, PaymentPurpose, PaymentStatus
    from app.services import checkout as checkout_module

    payment = Payment(
        user_id=None,
        contact_email="guest@example.com",
        amount_kopecks=30000,
        status=PaymentStatus.SUCCEEDED,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="platega",
        description="30 дней",
        period_days=30,
        subscription_url="https://panel.example/sub/abc",
    )
    service = checkout_module.CheckoutService(
        FakeSession(),  # type: ignore[arg-type]
        Settings(_env_file=None),
    )

    await service._notify(payment, date(2026, 9, 21))

    assert payment.notified_at is None
