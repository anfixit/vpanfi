"""Цены сайт берёт у витрины бота, а не у браузера.

Сумму, пришедшую из браузера, подделать ничего не стоит: платёж создался бы
на любую цену, какую назовёт покупатель. Поэтому клиент присылает только
идентификатор тарифа и число дней, а рубли сервер выясняет сам.

Витрина остаётся за ботом намеренно: пока цены живут в одном месте, сайт и
бот не могут назвать человеку разные суммы за одно и то же.
"""

import logging
from types import TracebackType
from typing import Any, Self

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "ShopCatalogue",
    "ShopError",
    "ShopUnavailableError",
    "UnknownTariffError",
]


class ShopError(RuntimeError):
    """Базовая ошибка витрины."""


class ShopUnavailableError(ShopError):
    """Витрина недоступна или ответила непонятным."""


class UnknownTariffError(ShopError):
    """Такого тарифа или периода в продаже нет."""


class ShopCatalogue:
    """Тарифы и цены, как их видит витрина."""

    def __init__(self, settings: Settings) -> None:
        self._slug = settings.shop_slug
        self._client = httpx.AsyncClient(
            base_url=str(settings.shop_base_url).rstrip("/"),
            headers={"Accept": "application/json"},
            timeout=settings.remnawave_timeout_seconds,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def price_kopecks(self, tariff_id: int, period_days: int) -> int:
        """Цена выбранного периода в копейках."""
        tariff = await self._tariff(tariff_id)
        for period in tariff.get("periods") or []:
            if int(period.get("days", -1)) == period_days:
                return int(period["price_kopeks"])
        raise UnknownTariffError(
            f"tariff {tariff_id} has no {period_days} days"
        )

    async def tariff_name(self, tariff_id: int) -> str:
        """Название тарифа — оно уедет в описание платежа."""
        tariff = await self._tariff(tariff_id)
        return str(tariff.get("name") or "Подписка")

    async def device_limit(self, tariff_id: int) -> int | None:
        """Сколько устройств входит в тариф.

        Берём из витрины, а не из константы: тариф меняют в боте, и
        зашитое здесь число разошлось бы с тем, что человек видел при
        покупке. None означает, что витрина лимита не назвала.
        """
        tariff = await self._tariff(tariff_id)
        value = tariff.get("device_limit")
        return int(value) if value is not None else None

    async def _tariff(self, tariff_id: int) -> dict[str, Any]:
        for tariff in await self._catalogue():
            if int(tariff.get("id", -1)) == tariff_id:
                return tariff
        raise UnknownTariffError(f"tariff {tariff_id} is not on sale")

    async def _catalogue(self) -> list[dict[str, Any]]:
        try:
            response = await self._client.get(f"/{self._slug}")
            response.raise_for_status()
            answer = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Витрина недоступна: %s", type(exc).__name__)
            raise ShopUnavailableError("The shop is unreachable") from exc

        tariffs = answer.get("tariffs") if isinstance(answer, dict) else None
        if not isinstance(tariffs, list):
            raise ShopUnavailableError("The shop returned no tariffs")
        return [tariff for tariff in tariffs if isinstance(tariff, dict)]
