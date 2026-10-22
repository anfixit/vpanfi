"""Клиент ЮKassa: что уходит в кассу и что мы понимаем в ответе."""

import json as jsonlib

import httpx
import pytest
import respx
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.yookassa.client import (
    YookassaGateway,
    YookassaNotConfiguredError,
    YookassaUnavailableError,
)

YOOKASSA_URL = "https://yookassa.example.test/v3"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        yookassa_base_url=YOOKASSA_URL,
        yookassa_shop_id="54401",
        yookassa_secret_key=SecretStr("test_secret"),
    )


def test_gateway_requires_credentials() -> None:
    with pytest.raises(YookassaNotConfiguredError):
        YookassaGateway(Settings(_env_file=None))


@respx.mock
async def test_create_payment_sends_the_documented_body() -> None:
    route = respx.post(f"{YOOKASSA_URL}/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "2d8f1b00-000f-5000-9000-1b68e7f15d3c",
                "status": "pending",
                "paid": False,
                "amount": {"value": "300.00", "currency": "RUB"},
                "confirmation": {
                    "type": "redirect",
                    "confirmation_url": "https://yoomoney.ru/checkout/1",
                },
            },
        )
    )

    async with YookassaGateway(_settings()) as gateway:
        payment = await gateway.create_payment(
            amount_rubles=300.0,
            description="Подписка на 30 дней",
            payload="payment-uuid",
            return_url="https://vpanfi.su/buy?token=payment-uuid",
            payment_method="sbp",
        )

    request = route.calls.last.request
    body = jsonlib.loads(request.content)
    assert request.headers["Authorization"].startswith("Basic ")
    assert body["amount"] == {"value": "300.00", "currency": "RUB"}
    assert body["capture"] is True
    assert body["confirmation"] == {
        "type": "redirect",
        "return_url": "https://vpanfi.su/buy?token=payment-uuid",
    }
    assert body["payment_method_data"] == {"type": "sbp"}
    assert body["metadata"] == {"payment_id": "payment-uuid"}
    # Чеки по 54-ФЗ сайт не передаёт: фискализации у магазина нет.
    assert "receipt" not in body
    assert payment.id == "2d8f1b00-000f-5000-9000-1b68e7f15d3c"
    assert payment.confirmation_url == "https://yoomoney.ru/checkout/1"


@respx.mock
async def test_each_attempt_carries_its_own_idempotence_key() -> None:
    """Без заголовка ЮKassa откажет, а повтор с тем же ключом вернёт старое."""
    route = respx.post(f"{YOOKASSA_URL}/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pay-1",
                "confirmation": {"confirmation_url": "https://pay/1"},
            },
        )
    )

    async with YookassaGateway(_settings()) as gateway:
        for _ in range(2):
            await gateway.create_payment(
                amount_rubles=300.0,
                description="Подписка",
                payload="p",
                return_url="https://vpanfi.su/buy?token=p",
            )

    keys = [call.request.headers["Idempotence-Key"] for call in route.calls]
    assert all(keys)
    assert keys[0] != keys[1]


@respx.mock
async def test_amount_is_sent_with_two_decimals() -> None:
    """ЮKassa принимает сумму строкой и отвергает «300.0» и «300»."""
    route = respx.post(f"{YOOKASSA_URL}/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pay-2",
                "confirmation": {"confirmation_url": "https://pay/2"},
            },
        )
    )

    async with YookassaGateway(_settings()) as gateway:
        await gateway.create_payment(
            amount_rubles=99.9,
            description="Подписка",
            payload="p",
            return_url="https://vpanfi.su/buy?token=p",
        )

    body = jsonlib.loads(route.calls.last.request.content)
    assert body["amount"]["value"] == "99.90"


@respx.mock
async def test_payment_method_is_omitted_when_the_buyer_did_not_choose(
) -> None:
    """Без способа ЮKassa сама покажет свой выбор — это лучше отказа."""
    route = respx.post(f"{YOOKASSA_URL}/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pay-3",
                "confirmation": {"confirmation_url": "https://pay/3"},
            },
        )
    )

    async with YookassaGateway(_settings()) as gateway:
        await gateway.create_payment(
            amount_rubles=300.0,
            description="Подписка",
            payload="p",
            return_url="https://vpanfi.su/buy?token=p",
        )

    body = jsonlib.loads(route.calls.last.request.content)
    assert "payment_method_data" not in body


@respx.mock
async def test_answer_without_confirmation_url_is_an_error() -> None:
    """Платёж без ссылки бесполезен: человеку некуда идти платить."""
    respx.post(f"{YOOKASSA_URL}/payments").mock(
        return_value=httpx.Response(200, json={"id": "pay-4"})
    )

    async with YookassaGateway(_settings()) as gateway:
        with pytest.raises(YookassaUnavailableError):
            await gateway.create_payment(
                amount_rubles=300.0,
                description="Подписка",
                payload="p",
                return_url="https://vpanfi.su/buy?token=p",
            )


@respx.mock
async def test_description_is_cut_to_the_limit() -> None:
    """ЮKassa принимает не длиннее 128 символов."""
    route = respx.post(f"{YOOKASSA_URL}/payments").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pay-5",
                "confirmation": {"confirmation_url": "https://pay/5"},
            },
        )
    )

    async with YookassaGateway(_settings()) as gateway:
        await gateway.create_payment(
            amount_rubles=300.0,
            description="я" * 200,
            payload="p",
            return_url="https://vpanfi.su/buy?token=p",
        )

    body = jsonlib.loads(route.calls.last.request.content)
    assert len(body["description"]) == 128


@respx.mock
async def test_yookassa_error_becomes_domain_error() -> None:
    respx.post(f"{YOOKASSA_URL}/payments").mock(
        return_value=httpx.Response(500)
    )

    async with YookassaGateway(_settings()) as gateway:
        with pytest.raises(YookassaUnavailableError):
            await gateway.create_payment(
                amount_rubles=300.0,
                description="Подписка",
                payload="p",
                return_url="https://vpanfi.su/buy?token=p",
            )


@respx.mock
async def test_state_is_read_from_the_cash_desk_itself() -> None:
    """Уведомление ЮKassa не подписывает: состояние спрашиваем сами."""
    respx.get(f"{YOOKASSA_URL}/payments/pay-6").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "pay-6",
                "status": "succeeded",
                "paid": True,
                "amount": {"value": "300.00", "currency": "RUB"},
            },
        )
    )

    async with YookassaGateway(_settings()) as gateway:
        state = await gateway.get_payment("pay-6")

    assert state.status == "succeeded"
    assert state.paid is True
    assert state.amount_kopecks == 30000


@respx.mock
async def test_state_without_an_amount_is_readable() -> None:
    """Сумму сверять будет нечем, но статус знать всё равно надо."""
    respx.get(f"{YOOKASSA_URL}/payments/pay-7").mock(
        return_value=httpx.Response(
            200, json={"id": "pay-7", "status": "canceled", "paid": False}
        )
    )

    async with YookassaGateway(_settings()) as gateway:
        state = await gateway.get_payment("pay-7")

    assert state.status == "canceled"
    assert state.paid is False
    assert state.amount_kopecks is None
