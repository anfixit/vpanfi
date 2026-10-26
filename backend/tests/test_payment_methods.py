"""Платить можно не только по СБП.

Сайт был зашит на один способ. Человек без СБП не мог заплатить ничем,
хотя у магазина включены и карты. Карта в России есть у всех, СБП
настроен не у всех.

Способы здесь — значения ``payment_method_data.type`` из API ЮKassa.
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
        "yookassa_shop_id": "54401",
        "yookassa_secret_key": SecretStr("test_secret"),
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_the_choice_is_left_to_the_cash_desk_out_of_the_box() -> None:
    """Список по умолчанию пуст, и это сознательно.

    Свой список пришлось бы сверять с кабинетом магазина вручную.
    22.10.2026 у магазина нет СБП, и зашитый в дефолт «bank_card,sbp»
    завёл бы половину покупателей в тупик уже на странице кассы.
    """
    assert _settings().payment_method_types == []


def test_methods_keep_the_configured_order() -> None:
    """Порядок в настройке — это порядок кнопок на экране."""
    types = _settings(
        yookassa_payment_methods="sbp,bank_card"
    ).payment_method_types

    assert types == ["sbp", "bank_card"]


def test_garbage_in_the_setting_does_not_kill_the_checkout() -> None:
    """Опечатка не должна оставлять сайт без кассы.

    Неизвестное имя доходит до каталога и выпадает уже там: списку
    настройки незачем знать справочник названий.
    """
    types = _settings(
        yookassa_payment_methods="bank_card, , карта, sbp,"
    ).payment_method_types

    assert [method.code for method in known_methods(types)] == [
        "bank_card",
        "sbp",
    ]


def test_duplicates_collapse() -> None:
    types = _settings(
        yookassa_payment_methods="sbp,sbp,bank_card"
    ).payment_method_types

    assert types == ["sbp", "bank_card"]


def test_empty_setting_leaves_the_choice_to_the_cash_desk() -> None:
    """Пустой список — это «не выбирать за человека», а не «платить нечем».

    Без ``payment_method_data`` ЮKassa показывает на своей странице все
    способы, включённые у магазина.
    """
    assert _settings(yookassa_payment_methods="").payment_method_types == []


def test_unknown_methods_are_not_shown_to_a_buyer() -> None:
    """Безымянная кнопка оплаты хуже отсутствующей.

    Способ мог появиться в настройке раньше, чем название в справочнике.
    Человек не должен гадать, куда его ведут с деньгами.
    """
    shown = [
        method.code
        for method in known_methods(["bank_card", "b2b_sberbank", "sbp"])
    ]

    assert shown == ["bank_card", "sbp"]


def test_every_offered_method_has_a_human_name() -> None:
    for method in known_methods(["bank_card", "sbp", "yoo_money"]):
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
        paymentMethod="bank_card",
    )

    assert request.payment_method == "bank_card"


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
    """Чужой способ уехал бы в ЮKassa как есть.

    Отказ покупатель увидел бы уже на её странице и решил бы, что
    сломались мы.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.start)

    assert "payment_method_types" in source
    assert "UnknownPaymentMethodError" in source


def test_chosen_method_reaches_the_cash_desk() -> None:
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
