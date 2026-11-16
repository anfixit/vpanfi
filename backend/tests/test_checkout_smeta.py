"""Смета продления: доплата за места сверх тарифного.

Витрина продаёт один базовый тариф на три устройства, а продление в
панели лимита не касается — ``set_expiry`` двигает только срок. Пока
доплаты не было, человек с пятью местами платил на сайте как за три.
"""

import inspect

import httpx
import respx

from app.core.config import Settings
from app.services.checkout import (
    CheckoutService,
    doplata_za_mesta,
    mest_sverh_tarifa,
    mesyacev_v_periode,
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
    "payment_methods": [{"method_id": "yookassa"}],
}


def _settings() -> Settings:
    return Settings(
        _env_file=None, shop_base_url=SHOP_URL, shop_slug="vpanfi"
    )


class SmetaCheckout(CheckoutService):
    """Касса с заранее известным числом мест в подписке.

    Подменён только поход в базу и панель: сам расчёт — настоящий. Иначе
    тест проверял бы заглушку, а не цену, которую человек увидит.
    """

    def __init__(self, mest: int | None) -> None:
        super().__init__(None, _settings())  # type: ignore[arg-type]
        self._mest = mest

    async def _mest_v_podpiske(self, email: str) -> int | None:
        return self._mest


def _vitrina() -> None:
    respx.get(f"{SHOP_URL}/vpanfi").mock(
        return_value=httpx.Response(200, json=CATALOGUE)
    )


def test_month_count_follows_the_period() -> None:
    assert mesyacev_v_periode(30) == 1
    assert mesyacev_v_periode(90) == 3
    assert mesyacev_v_periode(180) == 6


def test_a_short_period_is_still_a_month() -> None:
    """Неделя не даёт нулевой доплаты: место занято и в неё."""
    assert mesyacev_v_periode(7) == 1


def test_places_are_counted_only_above_the_tariff() -> None:
    assert mest_sverh_tarifa(5, 3) == 2
    assert mest_sverh_tarifa(3, 3) == 0


def test_fewer_places_than_the_tariff_are_not_a_discount() -> None:
    """Отрицательных доплат не бывает: тариф дешевле не становится."""
    assert mest_sverh_tarifa(2, 3) == 0


def test_unknown_limit_gives_no_surcharge() -> None:
    """Панель молчит или подписка не привязана — берём базовую цену."""
    assert mest_sverh_tarifa(None, 3) == 0
    assert mest_sverh_tarifa(5, None) == 0


def test_surcharge_is_monthly_not_one_off() -> None:
    """100 ₽ за место за каждый месяц периода — так считает бот."""
    assert doplata_za_mesta(2, 30) == 20_000
    assert doplata_za_mesta(2, 90) == 60_000
    assert doplata_za_mesta(0, 180) == 0


@respx.mock
async def test_five_places_cost_more_than_the_base_tariff() -> None:
    _vitrina()

    smeta = await SmetaCheckout(5).smeta(
        email="ya@example.com", tariff_id=2, period_days=30
    )

    assert smeta.base_kopecks == 30_000
    assert smeta.amount_kopecks == 50_000
    assert smeta.extra_devices == 2
    assert smeta.devices_limit == 5


@respx.mock
async def test_the_receipt_says_how_many_places_were_paid() -> None:
    """Иначе 500 ₽ в выгрузке кассы выглядят как ошибка против 300."""
    _vitrina()

    smeta = await SmetaCheckout(5).smeta(
        email="ya@example.com", tariff_id=2, period_days=30
    )

    assert "мест: 5" in smeta.description


@respx.mock
async def test_three_places_pay_the_tariff_price() -> None:
    _vitrina()

    smeta = await SmetaCheckout(3).smeta(
        email="ya@example.com", tariff_id=2, period_days=30
    )

    assert smeta.amount_kopecks == 30_000
    assert smeta.extra_devices == 0
    assert "мест" not in smeta.description


@respx.mock
async def test_unknown_places_do_not_block_the_purchase() -> None:
    """Молчащая панель не повод не дать заплатить."""
    _vitrina()

    smeta = await SmetaCheckout(None).smeta(
        email="ya@example.com", tariff_id=2, period_days=30
    )

    assert smeta.amount_kopecks == 30_000
    assert smeta.extra_devices == 0
    assert smeta.devices_limit is None


@respx.mock
async def test_the_quarter_is_charged_for_three_months() -> None:
    _vitrina()

    smeta = await SmetaCheckout(5).smeta(
        email="ya@example.com", tariff_id=3, period_days=90
    )

    assert smeta.amount_kopecks == 80_000 + 60_000


def test_the_payment_takes_its_sum_from_the_estimate() -> None:
    """Прямой вызов цены витрины в ``start`` вернул бы прежнюю дырку."""
    source = inspect.getsource(CheckoutService.start)

    assert "amount_kopecks=smeta.amount_kopecks" in source
    assert "price_kopecks" not in source
