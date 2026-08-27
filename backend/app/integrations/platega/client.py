"""Единственная точка входа сайта в API Platega.

Клиент знает только про платежи: он не ходит в панель, ничего не пишет в
базу и не решает, что делать после оплаты. Поэтому его можно проверить
целиком на замоканных ответах, не поднимая ни базы, ни панели.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "PlategaError",
    "PlategaGateway",
    "PlategaNotConfiguredError",
    "PlategaPayment",
    "PlategaUnavailableError",
]

CREATE_PATH = "/transaction/process"
# Длину описания ограничивает сама Platega: более длинное она отвергает.
DESCRIPTION_LIMIT = 64


class PlategaError(RuntimeError):
    """Базовая ошибка интеграции с Platega."""


class PlategaNotConfiguredError(PlategaError):
    """Мерчант или секрет не заданы."""


class PlategaUnavailableError(PlategaError):
    """Platega недоступна или ответила непригодным ответом."""


@dataclass(frozen=True)
class PlategaPayment:
    """Созданный платёж: его идентификатор и ссылка на оплату."""

    id: str
    redirect_url: str


class PlategaGateway:
    """Касса сайта: создать платёж и спросить его состояние."""

    def __init__(self, settings: Settings) -> None:
        if not settings.is_platega_configured:
            raise PlategaNotConfiguredError(
                "Platega merchant id and secret are required"
            )

        secret = settings.platega_secret
        assert secret is not None  # гарантировано is_platega_configured
        self._payment_method = settings.platega_payment_method
        self._client = httpx.AsyncClient(
            base_url=str(settings.platega_base_url).rstrip("/"),
            headers={
                "X-MerchantId": settings.platega_merchant_id or "",
                "X-Secret": secret.get_secret_value(),
                "Accept": "application/json",
            },
            timeout=settings.platega_timeout_seconds,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Закрыть соединения с Platega."""
        await self._client.aclose()

    async def create_payment(
        self,
        *,
        amount_rubles: float,
        description: str,
        payload: str,
        return_url: str,
        failed_url: str,
        payment_method: int | None = None,
    ) -> PlategaPayment:
        """Создать платёж и получить ссылку, по которой человек заплатит.

        Способ выбирает покупатель. Если он не пришёл, берём запасной
        из настроек: остаться совсем без способа хуже, чем увести
        человека в СБП, который он, возможно, и хотел.
        """
        body: dict[str, Any] = {
            "paymentMethod": payment_method or self._payment_method,
            "paymentDetails": {
                "amount": round(amount_rubles, 2),
                "currency": "RUB",
            },
            "description": description[:DESCRIPTION_LIMIT],
            "return": return_url,
            "failedUrl": failed_url,
            "payload": payload,
        }

        answer = await self._request("POST", CREATE_PATH, json=body)

        # Platega называет идентификатор то id, то transactionId.
        identifier = answer.get("transactionId") or answer.get("id")
        redirect = answer.get("redirect")
        if not identifier or not redirect:
            logger.warning("Platega ответила без ссылки на оплату")
            raise PlategaUnavailableError(
                "Platega returned a payment without a redirect link"
            )

        return PlategaPayment(id=str(identifier), redirect_url=str(redirect))

    async def get_payment(self, payment_id: str) -> Mapping[str, Any]:
        """Спросить состояние платежа у самой Platega."""
        return await self._request("GET", f"/transaction/{payment_id}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        try:
            response = await self._client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            logger.warning(
                "Platega %s %s недоступна: %s",
                method,
                path,
                type(exc).__name__,
            )
            raise PlategaUnavailableError("Platega is unreachable") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Тело ответа не логируем: в нём может оказаться наш секрет.
            logger.warning(
                "Platega %s %s ответила %s",
                method,
                path,
                exc.response.status_code,
            )
            raise PlategaUnavailableError(
                f"Platega responded with {exc.response.status_code}"
            ) from exc

        try:
            answer = response.json()
        except ValueError as exc:
            raise PlategaUnavailableError(
                "Platega returned a non-JSON response"
            ) from exc

        if not isinstance(answer, Mapping):
            raise PlategaUnavailableError(
                "Platega returned an unexpected body"
            )
        return answer
