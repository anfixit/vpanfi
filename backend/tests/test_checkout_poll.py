"""Оплата, о которой не пришло уведомление, не должна пропадать.

Уведомление ЮKassa — единственный канал, из которого сайт узнаёт об
оплате: ``confirm`` и ``deliver`` зовутся только из вебхука. Адрес
уведомлений у магазина один, а магазин общий с ботом продаж и с
@hopbyhop_bot — те живут опросом кассы. Если адрес уедет другому
проекту или ЮKassa не достучится, оплаченная покупка повиснет
невыданной. Эти проверки держат второй канал: опрос кассы самим сайтом.
"""

from typing import Any
from uuid import UUID, uuid4

import app.services.checkout as checkout_module
import app.services.checkout_poll as poll_module
from app.core.config import Settings
from app.integrations.yookassa.client import (
    YookassaState,
    YookassaUnavailableError,
)
from app.models.billing import Payment, PaymentPurpose, PaymentStatus
from app.services.checkout import CheckoutService

PROVIDER_ID = "2e1f3b00-000f-5000-9000-1f1f1f1f1f1f"
AMOUNT = 30000


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "yookassa_shop_id": "1290805",
        "yookassa_secret_key": "test_secret",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _pending_payment() -> Payment:
    return Payment(
        id=uuid4(),
        user_id=None,
        contact_email="guest@example.test",
        amount_kopecks=AMOUNT,
        status=PaymentStatus.PENDING,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="yookassa",
        provider_payment_id=PROVIDER_ID,
        description="Тест, 30 дн.",
        tariff_id=2,
        period_days=30,
    )


class _Session:
    """Сессия без базы: один платёж, который находят любым способом."""

    def __init__(self, payment: Payment) -> None:
        self.payment = payment
        self.commits = 0

    async def scalar(self, _statement: object) -> Payment:
        return self.payment

    async def get(self, _model: object, _identifier: UUID) -> Payment:
        return self.payment

    async def commit(self) -> None:
        self.commits += 1


class _Kassa:
    """ЮKassa без сети: отвечает заранее заданным состоянием."""

    def __init__(self, state: YookassaState | None) -> None:
        self._state = state
        self.calls = 0

    async def __aenter__(self) -> "_Kassa":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def get_payment(self, _payment_id: str) -> YookassaState:
        self.calls += 1
        if self._state is None:
            raise YookassaUnavailableError("касса молчит")
        return self._state


def _oplacheno() -> YookassaState:
    return YookassaState(status="succeeded", paid=True, amount_kopecks=AMOUNT)


def _ne_oplacheno() -> YookassaState:
    return YookassaState(status="pending", paid=False, amount_kopecks=AMOUNT)


def _service(
    monkeypatch: Any,
    payment: Payment,
    kassa: _Kassa,
) -> tuple[CheckoutService, list[str]]:
    """Касса на подделке, а выдача — список вызовов вместо панели."""
    monkeypatch.setattr(
        checkout_module, "YookassaGateway", lambda _settings: kassa
    )
    service = CheckoutService(
        _Session(payment),  # type: ignore[arg-type]
        _settings(),
    )
    vydacha: list[str] = []

    async def _deliver(*, provider_payment_id: str) -> None:
        vydacha.append(provider_payment_id)
        # Настоящая выдача записывает платежу ссылку на подписку, и
        # именно по ней needs_delivery понимает, что довыдавать нечего.
        payment.subscription_url = "https://panel.example/sub/abc"

    monkeypatch.setattr(service, "deliver", _deliver)
    return service, vydacha


async def test_oplata_bez_uvedomleniya_vsyo_ravno_vydayotsya(
    monkeypatch: Any,
) -> None:
    """Человек заплатил, уведомления не было: подписку выдаёт опрос."""
    payment = _pending_payment()
    service, vydacha = _service(monkeypatch, payment, _Kassa(_oplacheno()))

    assert await service.poll(provider_payment_id=PROVIDER_ID) is True
    assert payment.status is PaymentStatus.SUCCEEDED
    assert vydacha == [PROVIDER_ID]


async def test_opros_i_vebhuk_vydayut_podpisku_odin_raz(
    monkeypatch: Any,
) -> None:
    """Пришли оба канала — выдача всё равно одна.

    Второй вызов здесь это вебхук: он зовёт ту же пару confirm и
    needs_delivery, что и опрос, и ничего не должен выдать повторно,
    иначе человек получит лишние дни за одни и те же деньги.
    """
    payment = _pending_payment()
    service, vydacha = _service(monkeypatch, payment, _Kassa(_oplacheno()))

    await service.poll(provider_payment_id=PROVIDER_ID)

    povtor = await service.confirm(provider_payment_id=PROVIDER_ID)
    assert povtor is False
    assert (
        await service.needs_delivery(provider_payment_id=PROVIDER_ID) is False
    )
    assert vydacha == [PROVIDER_ID]


async def test_nedostupnaya_kassa_ne_lomaet_opros(monkeypatch: Any) -> None:
    """Чужая поломка не должна ронять ни страницу, ни фоновый обход."""
    payment = _pending_payment()
    service, vydacha = _service(monkeypatch, payment, _Kassa(None))

    assert await service.poll(provider_payment_id=PROVIDER_ID) is False
    assert payment.status is PaymentStatus.PENDING
    assert vydacha == []


async def test_neoplachennyj_platyozh_nichego_ne_vydayot(
    monkeypatch: Any,
) -> None:
    """Касса говорит «ещё не оплачен» — выдавать нечего."""
    payment = _pending_payment()
    service, vydacha = _service(monkeypatch, payment, _Kassa(_ne_oplacheno()))

    assert await service.poll(provider_payment_id=PROVIDER_ID) is False
    assert payment.status is PaymentStatus.PENDING
    assert vydacha == []


async def test_stranica_rezultata_sprashivaet_kassu(monkeypatch: Any) -> None:
    """Страница результата показывает ссылку, а не «ещё не оплачено»."""
    payment = _pending_payment()
    kassa = _Kassa(_oplacheno())
    service, vydacha = _service(monkeypatch, payment, kassa)

    state = await service.state(payment.id)

    assert kassa.calls == 1
    assert vydacha == [PROVIDER_ID]
    assert state is not None
    assert state.paid is True
    assert state.subscription_url == "https://panel.example/sub/abc"


async def test_stranica_otvechaet_prezhnim_sostoyaniem_bez_kassy(
    monkeypatch: Any,
) -> None:
    """Касса не ответила — отдаём то, что знаем, а не ошибку."""
    payment = _pending_payment()
    service, _vydacha = _service(monkeypatch, payment, _Kassa(None))

    state = await service.state(payment.id)

    assert state is not None
    assert state.status == "pending"
    assert state.paid is False


async def test_vydannyj_platyozh_kassu_ne_bespokoit(monkeypatch: Any) -> None:
    """Оплаченный платёж повторно у кассы не спрашиваем."""
    payment = _pending_payment()
    payment.status = PaymentStatus.SUCCEEDED
    payment.subscription_url = "https://panel.example/sub/abc"
    kassa = _Kassa(_oplacheno())
    service, vydacha = _service(monkeypatch, payment, kassa)

    state = await service.state(payment.id)

    assert kassa.calls == 0
    assert vydacha == []
    assert state is not None
    assert state.paid is True


class _IdsSession:
    """Сессия, которая запоминает запрос на список незакрытых платежей."""

    def __init__(self, ids: list[str | None]) -> None:
        self.ids = ids
        self.statement: object | None = None

    async def scalars(self, statement: object) -> list[str | None]:
        self.statement = statement
        return self.ids


async def test_obhod_beryot_tolko_svoi_nezakrytye_platezhi() -> None:
    """Опрашивать чужое, оплаченное и древнее нечего и незачем."""
    session = _IdsSession([PROVIDER_ID, None])
    service = CheckoutService(session, _settings())  # type: ignore[arg-type]

    ids = await service.pending_provider_ids(limit=20)

    assert ids == [PROVIDER_ID]
    zapros = str(session.statement)
    assert "payments.status" in zapros
    assert "payments.created_at >=" in zapros
    assert "LIMIT" in zapros


async def test_fonovaya_zadacha_ne_padaet_iz_za_odnogo_platezha(
    monkeypatch: Any,
) -> None:
    """Один сломанный платёж не должен оставить без выдачи остальные."""
    oproshennye: list[str] = []

    class _FakeService:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def pending_provider_ids(self, *, limit: int) -> list[str]:
            assert limit > 0
            return ["pay-1", "pay-2"]

        async def poll(self, *, provider_payment_id: str) -> bool:
            oproshennye.append(provider_payment_id)
            if provider_payment_id == "pay-1":
                raise RuntimeError("база отвалилась посреди выдачи")
            return True

    class _FakeFactory:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_exc: object) -> None:
            return None

    monkeypatch.setattr(poll_module, "CheckoutService", _FakeService)
    monkeypatch.setattr(
        poll_module, "async_session_factory", lambda: _FakeFactory()
    )
    monkeypatch.setattr(poll_module, "get_settings", _settings)
    monkeypatch.setattr(
        poll_module, "build_referral_service", lambda _s, _n: None
    )

    vydano = await poll_module.obojti_ozhidayushchie_platezhi()

    assert oproshennye == ["pay-1", "pay-2"]
    assert vydano == 1


async def test_bez_nastroennoj_kassy_obhod_nichego_ne_delaet(
    monkeypatch: Any,
) -> None:
    """Выключенная касса не должна даже открывать сессию."""

    def _broken_factory() -> object:
        raise AssertionError("сессия не нужна: касса не настроена")

    monkeypatch.setattr(
        poll_module, "get_settings", lambda: Settings(_env_file=None)
    )
    monkeypatch.setattr(
        poll_module, "async_session_factory", _broken_factory
    )

    assert await poll_module.obojti_ozhidayushchie_platezhi() == 0
