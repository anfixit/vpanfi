"""Добор оплат: что делает обход, когда уведомление кассы не дошло.

Настоящей Postgres у проекта нет, поэтому сессия и сам
``CheckoutService`` здесь поддельные: правило сверки (поход в кассу и
сличение суммы) уже проверено в test_yookassa_webhook.py, а здесь
важно другое — кого обход берёт, как себя ведёт при молчащей кассе и
что подписка не выдаётся дважды, когда вебхук и обход проснулись на
одном платеже.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Select

from app.core.config import Settings
from app.integrations.yookassa.client import YookassaState
from app.models.billing import Payment, PaymentPurpose, PaymentStatus
from app.services import checkout as checkout_module
from app.services import payment_sweep
from app.services.checkout import (
    CheckoutNotConfiguredError,
    CheckoutService,
    CheckoutUnavailableError,
)


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "yookassa_shop_id": "54401",
        "yookassa_secret_key": "test_secret",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class _SessiyaBezBazy:
    """Сессия, которая только отдаёт заранее заданные идентификаторы."""

    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self.zapros: object | None = None
        self.rollbacks = 0

    async def scalars(self, statement: object) -> list[str]:
        self.zapros = statement
        return list(self._ids)

    async def rollback(self) -> None:
        self.rollbacks += 1


class _Kontekst:
    def __init__(self, session: _SessiyaBezBazy) -> None:
        self._session = session

    async def __aenter__(self) -> _SessiyaBezBazy:
        return self._session

    async def __aexit__(self, *exc: object) -> None:
        return None


def _podmenit_sessii(
    monkeypatch: pytest.MonkeyPatch, ids: list[str]
) -> list[_SessiyaBezBazy]:
    """Подменить фабрику сессий и вернуть список выданных сессий."""
    vydannye: list[_SessiyaBezBazy] = []

    def otkryt() -> _Kontekst:
        session = _SessiyaBezBazy(ids)
        vydannye.append(session)
        return _Kontekst(session)

    monkeypatch.setattr(payment_sweep, "async_session_factory", otkryt)
    monkeypatch.setattr(
        payment_sweep, "build_referral_service", lambda *_: None
    )
    monkeypatch.setattr(payment_sweep, "get_settings", _settings)
    return vydannye


class _PoddelnyjCheckout:
    """``CheckoutService`` без кассы и панели: отвечает по сценарию."""

    def __init__(self, scenarij: dict[str, str], zhurnal: list[str]) -> None:
        self._scenarij = scenarij
        self._zhurnal = zhurnal

    def __call__(self, *_: object) -> "_PoddelnyjCheckout":
        return self

    async def confirm(self, *, provider_payment_id: str) -> bool:
        self._zhurnal.append(f"confirm:{provider_payment_id}")
        scenarij = self._scenarij.get(provider_payment_id, "nichego")
        if scenarij == "kassa_molchit":
            raise CheckoutUnavailableError("boom")
        if scenarij == "net_skvada":
            raise CheckoutNotConfiguredError("no squad")
        if scenarij == "oshibka":
            raise RuntimeError("что-то пошло не так")
        return scenarij == "oplachen"

    async def needs_delivery(self, *, provider_payment_id: str) -> bool:
        self._zhurnal.append(f"needs:{provider_payment_id}")
        return self._scenarij.get(provider_payment_id) == "bez_ssylki"

    async def deliver(self, *, provider_payment_id: str) -> None:
        self._zhurnal.append(f"deliver:{provider_payment_id}")


def _podmenit_checkout(
    monkeypatch: pytest.MonkeyPatch, scenarij: dict[str, str]
) -> list[str]:
    zhurnal: list[str] = []
    monkeypatch.setattr(
        payment_sweep,
        "CheckoutService",
        _PoddelnyjCheckout(scenarij, zhurnal),
    )
    return zhurnal


async def test_lost_notification_is_picked_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Уведомление не дошло, платёж оплачен: обход выдаёт подписку сам."""
    _podmenit_sessii(monkeypatch, ["pay-1"])
    zhurnal = _podmenit_checkout(monkeypatch, {"pay-1": "oplachen"})

    assert await payment_sweep.obojti_svezhie() == 1
    assert zhurnal == ["confirm:pay-1", "deliver:pay-1"]


async def test_unpaid_payment_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Касса говорит, что не оплачен: ничего не выдаём."""
    _podmenit_sessii(monkeypatch, ["pay-1"])
    zhurnal = _podmenit_checkout(monkeypatch, {"pay-1": "nichego"})

    assert await payment_sweep.obojti_svezhie() == 0
    assert zhurnal == ["confirm:pay-1", "needs:pay-1"]


async def test_paid_without_link_is_delivered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Деньги приняты, а панель тогда молчала: обход довыдаёт."""
    _podmenit_sessii(monkeypatch, ["pay-1"])
    zhurnal = _podmenit_checkout(monkeypatch, {"pay-1": "bez_ssylki"})

    assert await payment_sweep.obojti_svezhie() == 1
    assert zhurnal == ["confirm:pay-1", "needs:pay-1", "deliver:pay-1"]


async def test_silent_cash_desk_does_not_break_the_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Касса не отвечает: обход не падает и не идёт дальше по списку.

    Молчащая касса касается всех платежей сразу, и остаток списка
    достанется следующему обходу через пару минут.
    """
    sessii = _podmenit_sessii(monkeypatch, ["pay-1", "pay-2"])
    zhurnal = _podmenit_checkout(monkeypatch, {"pay-1": "kassa_molchit"})

    assert await payment_sweep.obojti_svezhie() == 0
    assert zhurnal == ["confirm:pay-1"]
    # Сессия платежа откачена, иначе следующий обход получил бы её
    # мёртвой.
    assert sessii[-1].rollbacks == 1


async def test_missing_squad_stops_the_sweep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сквад не задан: выдавать нечем никому, обход прерывается тихо."""
    _podmenit_sessii(monkeypatch, ["pay-1", "pay-2"])
    zhurnal = _podmenit_checkout(monkeypatch, {"pay-1": "net_skvada"})

    assert await payment_sweep.obojti_svezhie() == 0
    assert zhurnal == ["confirm:pay-1"]


async def test_one_broken_payment_does_not_stop_the_rest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сбой на одном платеже не должен лишить выдачи остальные."""
    _podmenit_sessii(monkeypatch, ["pay-1", "pay-2"])
    zhurnal = _podmenit_checkout(
        monkeypatch, {"pay-1": "oshibka", "pay-2": "oplachen"}
    )

    assert await payment_sweep.obojti_svezhie() == 1
    assert "deliver:pay-2" in zhurnal


async def test_the_sweep_asks_only_about_our_own_payments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Платёж чужого провайдера и платёж без почты обход не берёт."""
    sessii = _podmenit_sessii(monkeypatch, [])
    _podmenit_checkout(monkeypatch, {})

    await payment_sweep.obojti_svezhie()

    statement = sessii[0].zapros
    assert isinstance(statement, Select)
    znacheniya = set(
        statement.compile().params.values()  # type: ignore[union-attr]
    )
    assert checkout_module.PROVIDER in znacheniya
    assert PaymentStatus.PENDING in znacheniya
    assert "contact_email IS NOT NULL" in str(statement)


async def test_paid_but_undelivered_payments_stay_in_the_selection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Оплачен, а подписка не выдана: обход должен брать и такие.

    Если выдача сорвалась на молчащей панели, платёж уже не PENDING, и
    по одному только PENDING он не попал бы ни в один следующий обход.
    А уведомления кассы в этом случае нет совсем — именно поэтому
    обход и понадобился.
    """
    sessii = _podmenit_sessii(monkeypatch, [])
    _podmenit_checkout(monkeypatch, {})

    await payment_sweep.obojti_svezhie()

    statement = sessii[0].zapros
    assert isinstance(statement, Select)
    znacheniya = set(
        statement.compile().params.values()  # type: ignore[union-attr]
    )
    assert PaymentStatus.SUCCEEDED in znacheniya
    assert "payments.delivered_at IS NULL" in str(statement)


async def test_the_newest_payment_is_asked_about_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Порядок выборки: сперва свежие.

    За свежей оплатой стоит человек, который ждёт письма прямо сейчас,
    а старое в суточном окне — почти всегда брошенная корзина. При
    упёртом в предел хвосте порядок «старые первыми» означал бы, что до
    свежей потерянной оплаты обход не доходит вовсе.
    """
    sessii = _podmenit_sessii(monkeypatch, [])
    _podmenit_checkout(monkeypatch, {})

    await payment_sweep.obojti_svezhie()

    assert "ORDER BY payments.created_at DESC" in str(sessii[0].zapros)


async def test_an_unknown_payment_is_not_asked_about(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Платежа с таким идентификатором у нас нет: в кассу не идём.

    Настоящий ``confirm`` ищет платёж по паре (провайдер,
    идентификатор): запись чужой кассы он не найдёт и в ЮKassa за ней
    не пойдёт.
    """
    kassa = _FakeKassa(_succeeded())
    monkeypatch.setattr(
        checkout_module, "YookassaGateway", lambda _settings: kassa
    )
    service = CheckoutService(
        _OdnaStroka(None, _Baza()),  # type: ignore[arg-type]
        _settings(),
    )

    assert await service.confirm(provider_payment_id="chuzhoj") is False
    assert kassa.asked == []


class _Baza:
    """Общее состояние строки платежа: то, что видно после commit."""

    def __init__(self) -> None:
        self.status = PaymentStatus.PENDING
        self.delivered_at: datetime | None = None


class _Rezultat:
    def __init__(self, rowcount: int) -> None:
        self.rowcount = rowcount


class _OdnaStroka:
    """Сессия поверх общей строки: свою копию платежа читает заново.

    Условный UPDATE из ``confirm`` отрабатывает здесь так же, как в
    базе: занять платёж получается только у того, кто пришёл первым.
    """

    def __init__(self, payment: Payment | None, baza: _Baza) -> None:
        self._payment = payment
        self._baza = baza

    async def scalar(self, statement: object) -> Payment | None:
        if self._payment is None:
            return None
        # Перечитывание, как у настоящей сессии в новой транзакции.
        self._payment.status = self._baza.status
        self._payment.delivered_at = self._baza.delivered_at
        return self._payment

    async def execute(self, statement: object) -> _Rezultat:
        # Точка переключения: настоящий UPDATE тоже уходит в сеть.
        await asyncio.sleep(0)
        if self._baza.status is PaymentStatus.PENDING:
            self._baza.status = PaymentStatus.SUCCEEDED
            return _Rezultat(1)
        return _Rezultat(0)

    async def commit(self) -> None:
        return None


class _FakeKassa:
    """ЮKassa без сети."""

    def __init__(self, state: YookassaState) -> None:
        self._state = state
        self.asked: list[str] = []

    async def __aenter__(self) -> "_FakeKassa":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get_payment(self, payment_id: str) -> YookassaState:
        self.asked.append(payment_id)
        # Касса отвечает по сети: пусть второй успеет вклиниться.
        await asyncio.sleep(0)
        return self._state


def _succeeded(amount_kopecks: int = 30000) -> YookassaState:
    return YookassaState(
        status="succeeded", paid=True, amount_kopecks=amount_kopecks
    )


def _payment() -> Payment:
    return Payment(
        user_id=None,
        contact_email="guest@example.com",
        amount_kopecks=30000,
        status=PaymentStatus.PENDING,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="yookassa",
        provider_payment_id="pay-1",
        description="30 дней",
        tariff_id=2,
        period_days=30,
    )


class _ServiceSVydachej(CheckoutService):
    """Настоящие ``confirm`` и ``needs_delivery``, выдача поддельная."""

    def __init__(
        self,
        session: object,
        settings: Settings,
        vydachi: list[str],
        baza: _Baza,
    ) -> None:
        super().__init__(session, settings)  # type: ignore[arg-type]
        self._vydachi = vydachi
        self._baza = baza

    async def deliver(self, *, provider_payment_id: str) -> None:
        # Панель отвечает не мгновенно: ровно в этот промежуток второй
        # обработчик и успел бы выдать подписку второй раз.
        await asyncio.sleep(0)
        self._vydachi.append(provider_payment_id)
        self._baza.delivered_at = datetime.now(UTC)


async def test_webhook_and_sweep_deliver_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Вебхук и обход проснулись на одном платеже: подписка одна.

    Оба идут тем же путём, что и вебхук в маршруте: confirm, затем
    needs_delivery, затем выдача, и оба под ``zamok_platezha``. Без
    замка второй успевал бы увидеть платёж оплаченным и без ссылки,
    пока первый ещё ходил в панель, и человек получил бы вдвое больше
    дней за те же деньги.
    """
    monkeypatch.setattr(
        checkout_module,
        "YookassaGateway",
        lambda _settings: _FakeKassa(_succeeded()),
    )
    baza = _Baza()
    vydachi: list[str] = []

    async def obrabotchik() -> None:
        # Своя сессия и своя копия платежа, как у двух разных вызовов.
        service = _ServiceSVydachej(
            _OdnaStroka(_payment(), baza), _settings(), vydachi, baza
        )
        async with payment_sweep.zamok_platezha("pay-1"):
            oplatil = await service.confirm(provider_payment_id="pay-1")
            if oplatil or await service.needs_delivery(
                provider_payment_id="pay-1"
            ):
                await service.deliver(provider_payment_id="pay-1")

    await asyncio.gather(obrabotchik(), obrabotchik())

    assert vydachi == ["pay-1"]
    assert baza.status is PaymentStatus.SUCCEEDED
    # Замок за собой убран: словарь не должен расти вечно.
    assert payment_sweep._ZAMKI == {}


async def test_an_undelivered_payment_is_delivered_on_the_next_sweep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Панель молчала, потом ответила: обход доводит выдачу до конца.

    Настоящие ``confirm`` и ``needs_delivery``: платёж уже succeeded,
    поэтому ``confirm`` отдаёт False (повтор не продлевает), а выдачу
    запускает именно ``needs_delivery``.
    """
    monkeypatch.setattr(
        checkout_module,
        "YookassaGateway",
        lambda _settings: _FakeKassa(_succeeded()),
    )
    baza = _Baza()
    baza.status = PaymentStatus.SUCCEEDED
    vydachi: list[str] = []
    service = _ServiceSVydachej(
        _OdnaStroka(_payment(), baza), _settings(), vydachi, baza
    )

    oplatil = await service.confirm(provider_payment_id="pay-1")
    assert oplatil is False
    assert await service.needs_delivery(provider_payment_id="pay-1") is True

    await service.deliver(provider_payment_id="pay-1")

    assert vydachi == ["pay-1"]
    # Отметка о выдаче закрывает платёж для следующих обходов, и
    # подписка не будет продлеваться каждые две минуты.
    assert await service.needs_delivery(provider_payment_id="pay-1") is False


async def test_only_one_claims_the_payment_without_the_lock() -> None:
    """Даже без замка переход pending → succeeded достаётся одному.

    Условный UPDATE в ``confirm`` отдаёт True ровно одному вызову:
    это и есть правило «продлевает только переход pending →
    succeeded», и оно не зависит от замка в памяти.
    """
    baza = _Baza()
    pervyj = CheckoutService(
        _OdnaStroka(_payment(), baza), _settings()  # type: ignore[arg-type]
    )
    vtoroj = CheckoutService(
        _OdnaStroka(_payment(), baza), _settings()  # type: ignore[arg-type]
    )

    itogi = [
        await pervyj._zanyat_oplachennym(_payment()),
        await vtoroj._zanyat_oplachennym(_payment()),
    ]

    assert itogi == [True, False]


def test_the_sweep_runs_no_more_than_once_a_minute() -> None:
    assert payment_sweep.dobor_period(
        _settings(yookassa_recheck_minutes=0)
    ) == timedelta(minutes=1)
    assert payment_sweep.dobor_period(
        _settings(yookassa_recheck_minutes=5)
    ) == timedelta(minutes=5)


def test_the_default_period_is_a_couple_of_minutes() -> None:
    """Человек ждёт письма со ссылкой: реже пары минут не годится."""
    assert payment_sweep.dobor_period(_settings()) <= timedelta(minutes=2)


async def test_cold_payments_are_a_separate_band(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Остывшие берутся своим обходом: от суток и до месяца.

    Пометить такой платёж несостоявшимся решает только касса (у
    ``confirm`` это ответ canceled), поэтому обход их не выбрасывает,
    а продолжает доспрашивать.
    """
    sessii = _podmenit_sessii(monkeypatch, [])
    _podmenit_checkout(monkeypatch, {})

    await payment_sweep.zakryt_ostyvshie()

    statement = sessii[0].zapros
    assert isinstance(statement, Select)
    # Две границы по дате вместо одной: сверху месяц, снизу сутки.
    granicy = [
        key
        for key in statement.compile().params  # type: ignore[union-attr]
        if "created_at" in key
    ]
    assert len(granicy) == 2
