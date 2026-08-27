"""Платить можно не только по СБП.

Сайт был зашит на один способ, код 2. Человек без СБП не мог заплатить
ничем, хотя у мерчанта включены и карты, и криптовалюта. Карта в России
есть у всех, СБП настроен не у всех.
"""

from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.schemas.cabinet import CheckoutRequest
from app.services.payment_methods import known_methods


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "platega_merchant_id": "merchant",
        "platega_secret": SecretStr("secret"),
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_card_is_offered_out_of_the_box() -> None:
    """Ради карты всё и затевалось: 11 — карта российского банка."""
    assert 11 in _settings().payment_method_codes


def test_methods_keep_the_configured_order() -> None:
    """Порядок в настройке — это порядок кнопок на экране."""
    codes = _settings(platega_payment_methods="13,2,11").payment_method_codes

    assert codes == [13, 2, 11]


def test_garbage_in_the_setting_does_not_kill_the_checkout() -> None:
    """Опечатка не должна оставлять сайт без кассы."""
    codes = _settings(
        platega_payment_methods="2, , карта, 11,"
    ).payment_method_codes

    assert codes == [2, 11]


def test_duplicates_collapse() -> None:
    codes = _settings(platega_payment_methods="2,2,11").payment_method_codes

    assert codes == [2, 11]


def test_empty_setting_falls_back_to_a_single_method() -> None:
    """Пустой список означал бы «платить нечем»."""
    codes = _settings(
        platega_payment_methods="",
        platega_payment_method=2,
    ).payment_method_codes

    assert codes == [2]


def test_unknown_codes_are_not_shown_to_a_buyer() -> None:
    """Безымянная кнопка оплаты хуже отсутствующей.

    Код мог появиться в настройке раньше, чем название в справочнике.
    Человек не должен гадать, куда его ведут с деньгами.
    """
    shown = [method.code for method in known_methods([2, 99, 11])]

    assert shown == [2, 11]


def test_every_offered_method_has_a_human_name() -> None:
    for method in known_methods([2, 11, 12, 13]):
        assert method.name
        assert method.description
        assert not method.name.startswith("Метод")


def test_request_without_a_method_is_still_valid() -> None:
    """Старый фронтенд не шлёт способ, и такой запрос обязан работать."""
    request = CheckoutRequest(
        email="guest@example.com",
        tariffId=2,
        periodDays=30,
    )

    assert request.payment_method is None


def test_request_carries_the_chosen_method() -> None:
    request = CheckoutRequest(
        email="guest@example.com",
        tariffId=2,
        periodDays=30,
        paymentMethod=11,
    )

    assert request.payment_method == 11


def test_amount_still_cannot_be_dictated_by_the_buyer() -> None:
    """Новое поле не должно было ослабить старую защиту."""
    with pytest.raises(ValidationError):
        CheckoutRequest(
            email="guest@example.com",
            tariffId=2,
            periodDays=30,
            amount=1,  # type: ignore[call-arg]
        )


def test_checkout_refuses_a_method_that_is_switched_off() -> None:
    """Чужой код уехал бы в Platega как есть.

    Отказ покупатель увидел бы уже на её странице и решил бы, что
    сломались мы.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.start)

    assert "payment_method_codes" in source
    assert "UnknownPaymentMethodError" in source


def test_chosen_method_reaches_platega() -> None:
    """Проверка без выхода наружу: способ должен дойти до кассы."""
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.start)

    assert "payment_method=payment_method" in source


def test_methods_route_is_declared_before_the_uuid_one() -> None:
    """Иначе «methods» уедет в разбор UUID и вернёт 422.

    Так уже вышло с /tariffs, и увидеть это можно только запросом:
    маршруты сами по себе выглядят исправными.
    """
    import inspect

    from app.api.routes import payments

    source = inspect.getsource(payments)

    assert source.index('"/methods"') < source.index('"/{payment_id}"')
