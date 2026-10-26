"""Единственная точка входа сайта в API ЮKassa.

Клиент знает только про платежи: он не ходит в панель, ничего не пишет в
базу и не решает, что делать после оплаты. Поэтому его можно проверить
целиком на замоканных ответах, не поднимая ни базы, ни панели.

Отличие от прежней кассы в одном, и оно важное: ЮKassa не подписывает
свои уведомления. Верить телу уведомления нельзя, поэтому у клиента есть
``get_payment``: состояние платежа мы всегда спрашиваем сами.
"""

import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from types import TracebackType
from typing import Any, Self

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "YookassaError",
    "YookassaGateway",
    "YookassaNotConfiguredError",
    "YookassaPayment",
    "YookassaState",
    "YookassaUnavailableError",
]

CREATE_PATH = "/payments"
# Длину описания ограничивает сама ЮKassa: более длинное она отвергает.
DESCRIPTION_LIMIT = 128
KOPECKS_IN_RUBLE = 100
# Состояние, которое ЮKassa считает оплатой.
SUCCESS_STATUS = "succeeded"
# Состояние, после которого ждать оплаты бессмысленно.
CANCELED_STATUS = "canceled"


class YookassaError(RuntimeError):
    """Базовая ошибка интеграции с ЮKassa."""


class YookassaNotConfiguredError(YookassaError):
    """Магазин или секретный ключ не заданы."""


class YookassaUnavailableError(YookassaError):
    """ЮKassa недоступна или ответила непригодным ответом."""


@dataclass(frozen=True)
class YookassaPayment:
    """Созданный платёж: его идентификатор и ссылка на оплату."""

    id: str
    confirmation_url: str


@dataclass(frozen=True)
class YookassaState:
    """Состояние платежа глазами самой кассы.

    Сумма отдельным полем и может отсутствовать: сверять уведомление
    надо именно с ней, а не с тем, что прислали на вебхук.
    """

    status: str
    paid: bool
    amount_kopecks: int | None


class YookassaGateway:
    """Касса сайта: создать платёж и спросить его состояние."""

    def __init__(self, settings: Settings) -> None:
        if not settings.is_yookassa_configured:
            raise YookassaNotConfiguredError(
                "YooKassa shop id and secret key are required"
            )

        secret = settings.yookassa_secret_key
        assert secret is not None  # гарантировано is_yookassa_configured
        self._client = httpx.AsyncClient(
            base_url=str(settings.yookassa_base_url).rstrip("/"),
            auth=(
                settings.yookassa_shop_id or "",
                secret.get_secret_value(),
            ),
            headers={"Accept": "application/json"},
            timeout=settings.yookassa_timeout_seconds,
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
        """Закрыть соединения с ЮKassa."""
        await self._client.aclose()

    async def create_payment(
        self,
        *,
        amount_rubles: float,
        description: str,
        payload: str,
        return_url: str,
        payment_method: str | None = None,
    ) -> YookassaPayment:
        """Создать платёж и получить ссылку, по которой человек заплатит.

        Способ выбирает покупатель. Если он не пришёл, не шлём
        ``payment_method_data`` вовсе: ЮKassa тогда покажет на своей
        странице все включённые у магазина способы, и это лучше, чем
        увести человека в один заранее выбранный.

        Чек по 54-ФЗ не передаётся: сайт его не формирует, как не
        формировал и с прежней кассой.
        """
        body: dict[str, Any] = {
            # Сумма уходит строкой с двумя знаками: «300.0» и «300»
            # ЮKassa отвергает.
            "amount": {
                "value": f"{Decimal(str(amount_rubles)):.2f}",
                "currency": "RUB",
            },
            # Одностадийный платёж: деньги списываются сразу, без
            # отдельного подтверждения с нашей стороны.
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description[:DESCRIPTION_LIMIT],
            # Наш идентификатор платежа едет с деньгами: по нему платёж
            # видно в кабинете кассы и его же легко сверить с базой.
            "metadata": {"payment_id": payload},
        }
        if payment_method:
            body["payment_method_data"] = {"type": payment_method}

        answer = await self._request(
            "POST",
            CREATE_PATH,
            json=body,
            # Свой ключ на каждую попытку. Повтор с тем же ключом вернул
            # бы прежний платёж вместо нового, а без заголовка ЮKassa
            # откажет вовсе.
            headers={"Idempotence-Key": str(uuid.uuid4())},
        )

        identifier = answer.get("id")
        confirmation = answer.get("confirmation")
        url = (
            confirmation.get("confirmation_url")
            if isinstance(confirmation, Mapping)
            else None
        )
        if not identifier or not url:
            logger.warning("ЮKassa ответила без ссылки на оплату")
            raise YookassaUnavailableError(
                "YooKassa returned a payment without a confirmation url"
            )

        return YookassaPayment(id=str(identifier), confirmation_url=str(url))

    async def get_payment(self, payment_id: str) -> YookassaState:
        """Спросить состояние платежа у самой ЮKassa."""
        answer = await self._request("GET", f"{CREATE_PATH}/{payment_id}")
        return YookassaState(
            status=str(answer.get("status") or ""),
            paid=answer.get("paid") is True,
            amount_kopecks=_kopecks(answer.get("amount")),
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        try:
            response = await self._client.request(
                method, path, json=json, headers=headers
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "ЮKassa %s %s недоступна: %s",
                method,
                path,
                type(exc).__name__,
            )
            raise YookassaUnavailableError("YooKassa is unreachable") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Тело ответа не логируем: в нём может оказаться наш секрет.
            logger.warning(
                "ЮKassa %s %s ответила %s",
                method,
                path,
                exc.response.status_code,
            )
            raise YookassaUnavailableError(
                f"YooKassa responded with {exc.response.status_code}"
            ) from exc

        try:
            answer = response.json()
        except ValueError as exc:
            raise YookassaUnavailableError(
                "YooKassa returned a non-JSON response"
            ) from exc

        if not isinstance(answer, Mapping):
            raise YookassaUnavailableError(
                "YooKassa returned an unexpected body"
            )
        return answer


def _kopecks(amount: object) -> int | None:
    """Сумма платежа в копейках, если её вообще можно прочитать.

    Непрочитанная сумма это None, а не ноль: ноль сошёлся бы с
    бесплатным платежом, а None честно означает «сверять нечем».
    """
    if not isinstance(amount, Mapping):
        return None
    try:
        rubles = Decimal(str(amount.get("value")))
    except (InvalidOperation, TypeError):
        return None
    return int(rubles * KOPECKS_IN_RUBLE)
