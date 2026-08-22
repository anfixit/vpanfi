import httpx
import pytest
import respx

from app.core.config import Settings
from app.services.shop import (
    ShopCatalogue,
    ShopUnavailableError,
    UnknownTariffError,
)

SHOP_URL = "https://bot.example.test/cabinet/landing"

CATALOGUE = {
    "title": "VPaNfi",
    "tariffs": [
        {
            "id": 2,
            "name": "30 дней",
            "device_limit": 3,
            "traffic_limit_gb": 0,
            "periods": [{"days": 30, "price_kopeks": 30000}],
        },
        {
            "id": 3,
            "name": "90 дней",
            "device_limit": 3,
            "traffic_limit_gb": 0,
            "periods": [{"days": 90, "price_kopeks": 80000}],
        },
    ],
    "payment_methods": [{"method_id": "platega"}],
}


def _settings() -> Settings:
    return Settings(_env_file=None, shop_base_url=SHOP_URL, shop_slug="vpanfi")


@respx.mock
async def test_price_comes_from_the_shop_not_from_the_client() -> None:
    respx.get(f"{SHOP_URL}/vpanfi").mock(
        return_value=httpx.Response(200, json=CATALOGUE)
    )

    async with ShopCatalogue(_settings()) as shop:
        assert await shop.price_kopecks(2, 30) == 30000
        assert await shop.tariff_name(3) == "90 дней"


@respx.mock
async def test_unknown_tariff_is_rejected() -> None:
    """Неизвестный тариф — попытка купить то, чего не продаём."""
    respx.get(f"{SHOP_URL}/vpanfi").mock(
        return_value=httpx.Response(200, json=CATALOGUE)
    )

    async with ShopCatalogue(_settings()) as shop:
        with pytest.raises(UnknownTariffError):
            await shop.price_kopecks(99, 30)


@respx.mock
async def test_unknown_period_is_rejected() -> None:
    respx.get(f"{SHOP_URL}/vpanfi").mock(
        return_value=httpx.Response(200, json=CATALOGUE)
    )

    async with ShopCatalogue(_settings()) as shop:
        with pytest.raises(UnknownTariffError):
            await shop.price_kopecks(2, 31)


@respx.mock
async def test_broken_shop_becomes_domain_error() -> None:
    respx.get(f"{SHOP_URL}/vpanfi").mock(return_value=httpx.Response(502))

    async with ShopCatalogue(_settings()) as shop:
        with pytest.raises(ShopUnavailableError):
            await shop.price_kopecks(2, 30)
