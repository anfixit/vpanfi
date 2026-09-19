"""Изолированный клиент API бота продаж Bedolaga.

Бот продаж хранит свои подписки телеграм-клиентов отдельно от панели и
умеет продлевать их сам, синхронизируя итог с панелью внутри себя. Для
рефералки это единственный способ наградить пригласившего, который
пришёл из бота, а не с сайта: у него есть телеграм-идентификатор, но
может не быть учётки в панели вовсе.

Метод продления не идемпотентен: повторный вызов продлит подписку ещё
раз. Поэтому шлюз не повторяет запрос сам при сбое, а решает это
обработчик наград, который умеет отличить неизвестный исход от
известного и не выдать награду дважды.
"""

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "BedolagaError",
    "BedolagaGateway",
    "BedolagaNotConfiguredError",
    "BedolagaUnavailableError",
    "BedolagaUserNotFoundError",
]

USERS_PATH = "/users/by-telegram-id"
SUBSCRIPTIONS_PATH = "/subscriptions"

# У бота продаж свой хост, отдельный от панели и от сайта: запрос сюда
# не должен держать выдачу награды дольше, чем оправдано.
TIMEOUT_SECONDS = 15.0


class BedolagaError(RuntimeError):
    """Базовая ошибка интеграции с ботом продаж Bedolaga."""


class BedolagaNotConfiguredError(BedolagaError):
    """Ключ доступа к API бота продаж не задан."""


class BedolagaUnavailableError(BedolagaError):
    """Бот продаж недоступен или ответил ошибкой."""


class BedolagaUserNotFoundError(LookupError):
    """У бота продаж нет клиента с таким телеграм-идентификатором."""


class BedolagaGateway:
    """Единственная точка входа рефералки в API бота продаж."""

    def __init__(self, settings: Settings) -> None:
        if not settings.is_bedolaga_configured:
            raise BedolagaNotConfiguredError(
                "Bedolaga API token is required"
            )

        token = settings.bedolaga_api_token
        assert token is not None  # гарантировано is_bedolaga_configured
        self._client = httpx.AsyncClient(
            base_url=settings.bedolaga_api_url.rstrip("/"),
            headers={
                "X-API-Key": token.get_secret_value(),
                "Accept": "application/json",
            },
            timeout=TIMEOUT_SECONDS,
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
        """Закрыть HTTP-соединения с ботом продаж."""
        await self._client.aclose()

    async def subscription_id_by_telegram_id(self, telegram_id: int) -> int:
        """Найти платную подписку клиента бота по телеграм-идентификатору.

        Награда пригласившему не должна превратить его пробный период в
        платный, поэтому пробные подписки в расчёт не идут: нет ни одной
        платной, значит подходящего клиента нет вовсе.
        """
        path = f"{USERS_PATH}/{telegram_id}"
        payload = await self._request(
            "GET", path, not_found=BedolagaUserNotFoundError
        )
        if not isinstance(payload, Mapping):
            raise BedolagaUnavailableError(
                "Bedolaga returned an unexpected user payload"
            )

        subscription_id = _paid_subscription_id(payload)
        if subscription_id is None:
            raise BedolagaUserNotFoundError(path)
        return subscription_id

    async def extend(self, subscription_id: int, days: int) -> None:
        """Продлить подписку клиента бота на заданное число дней.

        Не идемпотентен и не повторяется здесь: при сбое обработчик
        наград сам решает, продлевать ли ещё раз.
        """
        # Запрос неповторяемый, поэтому негодное число дней отсекается до
        # сети: ноль и минус бот отклонил бы, а сбой в настройках мог бы
        # прислать сюда что угодно.
        if days <= 0:
            raise ValueError("days must be positive")
        path = f"{SUBSCRIPTIONS_PATH}/{subscription_id}/extend"
        await self._request("POST", path, json={"days": days})

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
        not_found: type[LookupError] | None = None,
    ) -> Any:
        """Сходить в бота продаж без повторов при сбое.

        Текст ошибки не несёт ни тела ответа, ни ключа доступа: тело
        может содержать чужие данные, а ключ виден в самом запросе.
        """
        try:
            response = await self._client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            logger.warning(
                "Bedolaga %s %s недоступен: %s",
                method,
                path,
                type(exc).__name__,
            )
            raise BedolagaUnavailableError(
                f"Bedolaga is unreachable: {method} {path}"
            ) from exc

        if (
            not_found is not None
            and response.status_code == httpx.codes.NOT_FOUND
        ):
            raise not_found(path)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Bedolaga %s %s ответил %s",
                method,
                path,
                exc.response.status_code,
            )
            raise BedolagaUnavailableError(
                f"Bedolaga {method} {path} responded with "
                f"{exc.response.status_code}"
            ) from exc

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise BedolagaUnavailableError(
                "Bedolaga returned a non-JSON response"
            ) from exc


def _paid_subscription_id(payload: Mapping[str, Any]) -> int | None:
    """Выбрать id платной подписки: основную либо самую новую из списка."""
    primary = payload.get("subscription")
    if isinstance(primary, Mapping) and not primary.get("is_trial"):
        subscription_id = primary.get("id")
        if isinstance(subscription_id, int):
            return subscription_id

    candidates = payload.get("subscriptions")
    if not isinstance(candidates, list):
        return None

    best_id: int | None = None
    best_end_date: datetime | None = None
    for item in candidates:
        if not isinstance(item, Mapping) or item.get("is_trial"):
            continue
        subscription_id = item.get("id")
        end_date = _parse_end_date(item.get("end_date"))
        if not isinstance(subscription_id, int) or end_date is None:
            continue
        if best_end_date is None or end_date > best_end_date:
            best_end_date = end_date
            best_id = subscription_id

    return best_id


def _parse_end_date(value: object) -> datetime | None:
    """Разобрать дату окончания, включая метку Z вместо смещения.

    Наивные даты считаются UTC: иначе сравнение с датой, у которой
    указано смещение, упало бы прямо на сортировке подписок.
    """
    if not isinstance(value, str):
        return None
    text = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed
