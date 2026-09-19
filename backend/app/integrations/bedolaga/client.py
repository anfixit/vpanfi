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
from dataclasses import dataclass
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
    "BotPurchase",
    "BotUser",
]

USERS_PATH = "/users/by-telegram-id"
# Список и выдача по числовому id: тот же ресурс, что и по telegram id
# выше, только другой ключ поиска ("/users/{id}" против
# "/users/by-telegram-id/{tg}").
USERS_LIST_PATH = "/users"
TRANSACTIONS_PATH = "/transactions"
SUBSCRIPTIONS_PATH = "/subscriptions"

# У бота продаж свой хост, отдельный от панели и от сайта: запрос сюда
# не должен держать выдачу награды дольше, чем оправдано.
TIMEOUT_SECONDS = 15.0

# Максимум страницы у /users и /transactions по документации бота.
MAX_PAGE_LIMIT = 200
# Обход покупок одного клиента не должен зависнуть навечно из-за
# бага на стороне бота, отдающего total больше реального числа строк.
MAX_PURCHASE_PAGES = 20


@dataclass(frozen=True)
class BotUser:
    """Клиент бота продаж в объёме, нужном рефералке.

    Полей у бота больше (email, статус, теги и так далее), но мосту
    нужны только эти пять: остальное разбирать незачем.
    """

    id: int
    telegram_id: int | None
    referral_code: str | None
    referred_by_id: int | None
    has_had_paid_subscription: bool


@dataclass(frozen=True)
class BotPurchase:
    """Завершённая покупка подписки в боте продаж (одна транзакция)."""

    id: int
    user_id: int
    completed_at: datetime


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
        payload = await self._user_payload_by_telegram_id(telegram_id)
        subscription_id = _paid_subscription_id(payload)
        if subscription_id is None:
            raise BedolagaUserNotFoundError(f"{USERS_PATH}/{telegram_id}")
        return subscription_id

    async def user_by_telegram_id(self, telegram_id: int) -> BotUser:
        """Найти клиента бота продаж по телеграм-идентификатору.

        Тот же запрос, что и у subscription_id_by_telegram_id (общий
        _user_payload_by_telegram_id): бот отдаёт по этому пути одного
        пользователя целиком, а не только его подписку.
        """
        payload = await self._user_payload_by_telegram_id(telegram_id)
        user = _parse_bot_user(payload)
        if user is None:
            raise BedolagaUnavailableError(
                "Bedolaga returned an unexpected user payload"
            )
        return user

    async def user_by_id(self, user_id: int) -> BotUser:
        """Найти клиента бота продаж по его числовому id."""
        path = f"{USERS_LIST_PATH}/{user_id}"
        payload = await self._request(
            "GET", path, not_found=BedolagaUserNotFoundError
        )
        user = _parse_bot_user(payload)
        if user is None:
            raise BedolagaUnavailableError(
                "Bedolaga returned an unexpected user payload"
            )
        return user

    async def list_users(
        self, *, limit: int = MAX_PAGE_LIMIT, offset: int = 0
    ) -> tuple[list[BotUser], int]:
        """Одна страница клиентов бота продаж.

        Возвращает только эту страницу и общее число записей: обходом
        всех страниц занимается вызывающий (sync_bot), а не шлюз.
        Обломок одного пользователя в списке не должен прервать вызов
        целиком, поэтому такой элемент просто пропускается с записью
        предупреждения в лог.
        """
        payload = await self._request(
            "GET",
            USERS_LIST_PATH,
            params={"limit": limit, "offset": offset},
        )
        items, total = _paged_items(payload, "users")

        users: list[BotUser] = []
        for item in items:
            user = _parse_bot_user(item)
            if user is None:
                logger.warning(
                    "Bedolaga list_users: пропущен неразборчивый элемент"
                )
                continue
            users.append(user)
        return users, total

    async def purchases(self, user_id: int) -> list[BotPurchase]:
        """Все завершённые оплаты подписки клиента, по возрастанию времени.

        Обходит все страницы /transactions сам (у sync_bot нет причин
        знать про пагинацию бота), с жёстким потолком страниц: неверный
        total на стороне бота не должен превратить обход в вечный цикл.
        """
        purchases: list[BotPurchase] = []
        offset = 0
        for _ in range(MAX_PURCHASE_PAGES):
            payload = await self._request(
                "GET",
                TRANSACTIONS_PATH,
                params={
                    "user_id": user_id,
                    "type": "subscription_payment",
                    "is_completed": True,
                    "limit": MAX_PAGE_LIMIT,
                    "offset": offset,
                },
            )
            items, total = _paged_items(payload, "transactions")
            if not items:
                break

            for item in items:
                purchase = _parse_bot_purchase(item)
                if purchase is None:
                    logger.warning(
                        "Bedolaga purchases: пропущена неразборчивая "
                        "транзакция"
                    )
                    continue
                purchases.append(purchase)

            offset += len(items)
            if offset >= total:
                break

        purchases.sort(key=lambda purchase: purchase.completed_at)
        return purchases

    async def _user_payload_by_telegram_id(
        self, telegram_id: int
    ) -> Mapping[str, Any]:
        """Общий запрос за пользователем по телеграм-id.

        Оба метода-потребителя (подписка и сам пользователь) ходят по
        одному и тому же пути и разбирают один и тот же ответ каждый
        по-своему.
        """
        path = f"{USERS_PATH}/{telegram_id}"
        payload = await self._request(
            "GET", path, not_found=BedolagaUserNotFoundError
        )
        if not isinstance(payload, Mapping):
            raise BedolagaUnavailableError(
                "Bedolaga returned an unexpected user payload"
            )
        return payload

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
        params: Mapping[str, Any] | None = None,
        not_found: type[LookupError] | None = None,
    ) -> Any:
        """Сходить в бота продаж без повторов при сбое.

        Текст ошибки не несёт ни тела ответа, ни ключа доступа: тело
        может содержать чужие данные, а ключ виден в самом запросе.
        """
        try:
            response = await self._client.request(
                method, path, json=json, params=params
            )
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
        end_date = _parse_timestamp(item.get("end_date"))
        if not isinstance(subscription_id, int) or end_date is None:
            continue
        if best_end_date is None or end_date > best_end_date:
            best_end_date = end_date
            best_id = subscription_id

    return best_id


def _parse_timestamp(value: object) -> datetime | None:
    """Разобрать метку времени бота, включая Z вместо смещения.

    Используется и для даты окончания подписки, и для времени покупки:
    формат у бота один и тот же везде. Наивные даты считаются UTC:
    иначе сравнение с датой со смещением упало бы прямо на сортировке.
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
    return parsed.astimezone(UTC)


def _parse_bot_user(payload: Any) -> BotUser | None:
    """Собрать BotUser из ответа бота, ничего не изобретая за него.

    Единственное обязательное поле это числовой id: без него запись
    нельзя ни с чем сопоставить, и она бракуется целиком. Остальные
    поля бот отдаёт как есть, но с чужого сервера безопаснее не
    доверять типам вслепую.
    """
    if not isinstance(payload, Mapping):
        return None

    user_id = payload.get("id")
    if not isinstance(user_id, int):
        return None

    telegram_id = payload.get("telegram_id")
    if not isinstance(telegram_id, int):
        telegram_id = None

    referral_code = payload.get("referral_code")
    if not isinstance(referral_code, str):
        referral_code = None

    referred_by_id = payload.get("referred_by_id")
    if not isinstance(referred_by_id, int):
        referred_by_id = None

    return BotUser(
        id=user_id,
        telegram_id=telegram_id,
        referral_code=referral_code,
        referred_by_id=referred_by_id,
        has_had_paid_subscription=bool(
            payload.get("has_had_paid_subscription")
        ),
    )


def _parse_bot_purchase(item: Any) -> BotPurchase | None:
    """Собрать BotPurchase из строки /transactions.

    Пустой completed_at (транзакция бывает завершена, но без отдельно
    записанного момента завершения) заменяется на created_at: покупка
    точно случилась не позже этого момента.
    """
    if not isinstance(item, Mapping):
        return None

    purchase_id = item.get("id")
    user_id = item.get("user_id")
    if not isinstance(purchase_id, int) or not isinstance(user_id, int):
        return None

    completed_at = _parse_timestamp(item.get("completed_at"))
    if completed_at is None:
        completed_at = _parse_timestamp(item.get("created_at"))
    if completed_at is None:
        return None

    return BotPurchase(
        id=purchase_id, user_id=user_id, completed_at=completed_at
    )


def _paged_items(payload: Any, what: str) -> tuple[list[Any], int]:
    """Достать список и total со страницы /users или /transactions.

    Обе ручки отдают одну и ту же форму конверта, поэтому разбор общий.
    """
    if not isinstance(payload, Mapping):
        raise BedolagaUnavailableError(
            f"Bedolaga returned an unexpected {what} payload"
        )
    items = payload.get("items")
    total = payload.get("total")
    if not isinstance(items, list) or not isinstance(total, int):
        raise BedolagaUnavailableError(
            f"Bedolaga returned an unexpected {what} payload"
        )
    return items, total
