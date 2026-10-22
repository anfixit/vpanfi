"""Уведомление ЮKassa: кому верим и что продлеваем.

ЮKassa уведомления не подписывает. По телу нельзя верить ни статусу, ни
сумме: кто угодно знает наш адрес вебхука. Поэтому из тела берём только
идентификатор платежа, а состояние спрашиваем у самой кассы и сверяем
сумму с тем, что записано у нас.
"""

from typing import Any

import pytest

from app.core.config import Settings
from app.integrations.yookassa.client import YookassaState
from app.models.billing import Payment, PaymentPurpose, PaymentStatus
from app.services import checkout as checkout_module
from app.services.checkout import CheckoutService, CheckoutUnavailableError
from app.services.notify import TelegramNotifier

WEBHOOK = "/api/v1/payments/yookassa/webhook"


class FakeSession:
    """Сессия без базы: проверяем правило, а не SQL."""

    def __init__(self, payment: Payment | None) -> None:
        self._payment = payment
        self.commits = 0

    async def scalar(self, statement: object) -> Payment | None:
        return self._payment

    async def commit(self) -> None:
        self.commits += 1


class _FakeKassa:
    """ЮKassa без сети: get_payment всегда отвечает заданным состоянием."""

    def __init__(self, state: YookassaState | Exception) -> None:
        self._state = state
        self.asked: list[str] = []

    async def __aenter__(self) -> "_FakeKassa":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get_payment(self, payment_id: str) -> YookassaState:
        self.asked.append(payment_id)
        if isinstance(self._state, Exception):
            raise self._state
        return self._state


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "yookassa_shop_id": "54401",
        "yookassa_secret_key": "test_secret",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _payment(
    status: PaymentStatus, *, referral_code: str | None = None
) -> Payment:
    return Payment(
        user_id=None,
        contact_email="guest@example.com",
        amount_kopecks=30000,
        status=status,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="yookassa",
        provider_payment_id="pay-1",
        description="30 дней",
        tariff_id=2,
        period_days=30,
        referral_code=referral_code,
    )


def _service(
    session: FakeSession,
    kassa: _FakeKassa,
    monkeypatch: pytest.MonkeyPatch,
    **overrides: Any,
) -> CheckoutService:
    monkeypatch.setattr(
        checkout_module, "YookassaGateway", lambda _settings: kassa
    )
    return CheckoutService(session, _settings(**overrides))  # type: ignore[arg-type]


def _succeeded(amount_kopecks: int = 30000) -> YookassaState:
    return YookassaState(
        status="succeeded", paid=True, amount_kopecks=amount_kopecks
    )


async def test_first_confirmation_wins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Продлевает подписку только тот вызов, который сам оплатил платёж."""
    payment = _payment(PaymentStatus.PENDING)
    session = FakeSession(payment)
    kassa = _FakeKassa(_succeeded())
    service = _service(session, kassa, monkeypatch)

    paid = await service.confirm(provider_payment_id="pay-1")

    assert paid is True
    assert payment.status is PaymentStatus.SUCCEEDED
    # Статус взят у кассы, а не из тела уведомления.
    assert kassa.asked == ["pay-1"]


async def test_repeated_notification_changes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ЮKassa шлёт уведомление, пока не увидит 200: повтор не продлевает."""
    payment = _payment(PaymentStatus.SUCCEEDED)
    session = FakeSession(payment)
    service = _service(session, _FakeKassa(_succeeded()), monkeypatch)

    paid = await service.confirm(provider_payment_id="pay-1")

    assert paid is False
    assert session.commits == 0


async def test_unknown_payment_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Уведомление о чужом платеже: в кассу за ним даже не ходим."""
    kassa = _FakeKassa(_succeeded())
    service = _service(FakeSession(None), kassa, monkeypatch)

    assert await service.confirm(provider_payment_id="pay-404") is False
    assert kassa.asked == []


async def test_a_different_amount_does_not_grant_a_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Заплатили не столько, сколько мы записали: выдачу не начинаем."""
    sent: list[str] = []
    monkeypatch.setattr(
        TelegramNotifier,
        "send_later",
        lambda self, text: sent.append(text),
    )
    payment = _payment(PaymentStatus.PENDING)
    session = FakeSession(payment)
    service = _service(
        session, _FakeKassa(_succeeded(amount_kopecks=100)), monkeypatch
    )

    paid = await service.confirm(provider_payment_id="pay-1")

    assert paid is False
    assert payment.status is PaymentStatus.PENDING
    assert session.commits == 0
    # Разошедшаяся сумма это повод разобраться руками, а не молча забыть.
    assert len(sent) == 1


async def test_unreadable_amount_does_not_grant_a_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сверить нечем — значит и подтверждать нечего."""
    monkeypatch.setattr(TelegramNotifier, "send_later", lambda self, _: None)
    payment = _payment(PaymentStatus.PENDING)
    service = _service(
        FakeSession(payment),
        _FakeKassa(
            YookassaState(status="succeeded", paid=True, amount_kopecks=None)
        ),
        monkeypatch,
    )

    assert await service.confirm(provider_payment_id="pay-1") is False
    assert payment.status is PaymentStatus.PENDING


async def test_succeeded_but_not_paid_is_not_a_payment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment = _payment(PaymentStatus.PENDING)
    service = _service(
        FakeSession(payment),
        _FakeKassa(
            YookassaState(status="succeeded", paid=False, amount_kopecks=30000)
        ),
        monkeypatch,
    )

    assert await service.confirm(provider_payment_id="pay-1") is False
    assert payment.status is PaymentStatus.PENDING


async def test_canceled_payment_is_marked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment = _payment(PaymentStatus.PENDING)
    service = _service(
        FakeSession(payment),
        _FakeKassa(
            YookassaState(status="canceled", paid=False, amount_kopecks=30000)
        ),
        monkeypatch,
    )

    paid = await service.confirm(provider_payment_id="pay-1")

    assert paid is False
    assert payment.status is PaymentStatus.FAILED


async def test_pending_payment_stays_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ЮKassa уведомляет и о незавершённом платеже: это ещё не отказ.

    Человек мог закрыть страницу банка и вернуться к ней через минуту.
    Пометив платёж несостоявшимся, мы не приняли бы его оплату вовсе.
    """
    payment = _payment(PaymentStatus.PENDING)
    service = _service(
        FakeSession(payment),
        _FakeKassa(
            YookassaState(
                status="waiting_for_capture", paid=False, amount_kopecks=30000
            )
        ),
        monkeypatch,
    )

    assert await service.confirm(provider_payment_id="pay-1") is False
    assert payment.status is PaymentStatus.PENDING


async def test_reversal_of_a_delivered_payment_notifies_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Касса отменила уже выданный платёж: одно уведомление владельцу."""
    sent: list[str] = []
    monkeypatch.setattr(
        TelegramNotifier,
        "send_later",
        lambda self, text: sent.append(text),
    )
    payment = _payment(PaymentStatus.SUCCEEDED, referral_code="Alyona_Tutina")
    session = FakeSession(payment)
    service = _service(
        session,
        _FakeKassa(
            YookassaState(status="canceled", paid=False, amount_kopecks=30000)
        ),
        monkeypatch,
    )

    paid = await service.confirm(provider_payment_id="pay-1")

    assert paid is False
    assert payment.status is PaymentStatus.SUCCEEDED
    assert session.commits == 0
    assert len(sent) == 1
    assert "referral-rewards" in sent[0]


async def test_silent_cash_desk_is_reported_upwards(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Касса не ответила: вебхуку надо вернуть не 200, чтобы он повторился."""
    from app.integrations.yookassa.client import YookassaUnavailableError

    service = _service(
        FakeSession(_payment(PaymentStatus.PENDING)),
        _FakeKassa(YookassaUnavailableError("boom")),
        monkeypatch,
    )

    with pytest.raises(CheckoutUnavailableError):
        await service.confirm(provider_payment_id="pay-1")


async def test_paid_without_link_needs_delivery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Панель молчала при первой выдаче: повтор вебхука должен довыдать."""
    payment = _payment(PaymentStatus.SUCCEEDED)
    service = _service(
        FakeSession(payment), _FakeKassa(_succeeded()), monkeypatch
    )

    assert await service.needs_delivery(provider_payment_id="pay-1") is True


async def test_delivered_payment_is_not_delivered_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment = _payment(PaymentStatus.SUCCEEDED)
    payment.subscription_url = "https://panel.example/sub/abc"
    service = _service(
        FakeSession(payment), _FakeKassa(_succeeded()), monkeypatch
    )

    assert await service.needs_delivery(provider_payment_id="pay-1") is False


def test_empty_verification_ping_is_answered(anonymous_client) -> None:
    """Пустой запрос по адресу вебхука не должен давать ошибку."""
    answer = anonymous_client.post(WEBHOOK, content=b"")

    assert answer.status_code == 200


def test_notification_without_an_identifier_is_answered(
    anonymous_client,
) -> None:
    """Повторять такое уведомление бессмысленно: отвечаем 200 и забываем."""
    answer = anonymous_client.post(
        WEBHOOK, json={"event": "payment.succeeded"}
    )

    assert answer.status_code == 200


def test_broken_body_is_rejected(anonymous_client) -> None:
    answer = anonymous_client.post(WEBHOOK, content=b"{not json")

    assert answer.status_code == 400
