import httpx
import pytest
import respx
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.platega.client import (
    PlategaGateway,
    PlategaNotConfiguredError,
    PlategaUnavailableError,
)

PLATEGA_URL = "https://platega.example.test"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        platega_base_url=PLATEGA_URL,
        platega_merchant_id="merchant-1",
        platega_secret=SecretStr("secret-1"),
    )


def test_gateway_requires_credentials() -> None:
    with pytest.raises(PlategaNotConfiguredError):
        PlategaGateway(Settings(_env_file=None))


@respx.mock
async def test_create_payment_sends_the_documented_body() -> None:
    route = respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(
            200,
            json={"id": "tx-1", "redirect": "https://pay.platega.io?id=tx-1"},
        )
    )

    async with PlategaGateway(_settings()) as gateway:
        payment = await gateway.create_payment(
            amount_rubles=300.0,
            description="Подписка на 30 дней",
            payload="payment-uuid",
            return_url="https://vpanfi.su/pay/done",
            failed_url="https://vpanfi.su/pay/failed",
        )

    request = route.calls.last.request
    body = request.content.decode()
    assert request.headers["X-MerchantId"] == "merchant-1"
    assert request.headers["X-Secret"] == "secret-1"
    assert '"paymentMethod":2' in body
    assert '"amount":300.0' in body
    assert '"currency":"RUB"' in body
    assert '"payload":"payment-uuid"' in body
    assert payment.id == "tx-1"
    assert payment.redirect_url == "https://pay.platega.io?id=tx-1"


@respx.mock
async def test_transaction_id_is_accepted_instead_of_id() -> None:
    """Platega называет идентификатор двумя способами — принимаем оба."""
    respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(
            200, json={"transactionId": "tx-2", "redirect": "https://pay/2"}
        )
    )

    async with PlategaGateway(_settings()) as gateway:
        payment = await gateway.create_payment(
            amount_rubles=800.0,
            description="Подписка",
            payload="p",
            return_url="https://vpanfi.su/done",
            failed_url="https://vpanfi.su/failed",
        )

    assert payment.id == "tx-2"


@respx.mock
async def test_answer_without_redirect_is_an_error() -> None:
    """Платёж без ссылки бесполезен: человеку некуда идти платить."""
    respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(200, json={"id": "tx-3"})
    )

    async with PlategaGateway(_settings()) as gateway:
        with pytest.raises(PlategaUnavailableError):
            await gateway.create_payment(
                amount_rubles=300.0,
                description="Подписка",
                payload="p",
                return_url="https://vpanfi.su/done",
                failed_url="https://vpanfi.su/failed",
            )


@respx.mock
async def test_description_is_cut_to_the_limit() -> None:
    """Platega принимает не длиннее 64 символов и иначе отвечает ошибкой."""
    route = respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(
            200, json={"id": "t", "redirect": "https://p"}
        )
    )

    async with PlategaGateway(_settings()) as gateway:
        await gateway.create_payment(
            amount_rubles=300.0,
            description="я" * 200,
            payload="p",
            return_url="https://vpanfi.su/done",
            failed_url="https://vpanfi.su/failed",
        )

    sent = route.calls.last.request.content.decode("unicode_escape")
    assert "я" * 65 not in sent


@respx.mock
async def test_platega_error_becomes_domain_error() -> None:
    respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(500)
    )

    async with PlategaGateway(_settings()) as gateway:
        with pytest.raises(PlategaUnavailableError):
            await gateway.create_payment(
                amount_rubles=300.0,
                description="Подписка",
                payload="p",
                return_url="https://vpanfi.su/done",
                failed_url="https://vpanfi.su/failed",
            )
