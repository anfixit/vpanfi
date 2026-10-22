"""Способы оплаты, которые сайт показывает покупателю.

До этого модуля сайт умел ровно один способ. Человек без СБП не мог
заплатить ничем, хотя у магазина включены и карты, а карта в России
есть у всех.

Названия живут здесь, а не на фронтенде: список включённых способов
меняется в настройках, и витрина не должна знать наперёд, какие бывают
способы. Незнакомый способ лучше не показывать вовсе, чем подписать
его внутренним именем: человек не должен гадать, куда его ведут
с деньгами.

Значения — это ``payment_method_data.type`` из API ЮKassa.
"""

from dataclasses import dataclass

__all__ = ["PaymentMethod", "known_methods", "is_known"]


@dataclass(frozen=True)
class PaymentMethod:
    """Способ оплаты глазами покупателя."""

    code: str
    name: str
    description: str


# Имена задаёт ЮKassa, менять их по своему усмотрению нельзя.
_CATALOGUE: dict[str, PaymentMethod] = {
    "bank_card": PaymentMethod(
        code="bank_card",
        name="Банковская карта",
        description="Мир, Visa или Mastercard",
    ),
    "sbp": PaymentMethod(
        code="sbp",
        name="СБП",
        description="QR-код или кнопка в приложении Вашего банка",
    ),
    "yoo_money": PaymentMethod(
        code="yoo_money",
        name="ЮMoney",
        description="Кошелёк ЮMoney",
    ),
    "sberbank": PaymentMethod(
        code="sberbank",
        name="SberPay",
        description="Оплата через Сбербанк Онлайн",
    ),
    "tinkoff_bank": PaymentMethod(
        code="tinkoff_bank",
        name="T-Pay",
        description="Оплата через приложение Т-Банка",
    ),
}


def is_known(code: str) -> bool:
    """Знаем ли мы, как называется этот способ."""
    return code in _CATALOGUE


def known_methods(codes: list[str]) -> list[PaymentMethod]:
    """Описания включённых способов, в том же порядке.

    Неизвестные способы выпадают: показать человеку безымянную кнопку
    оплаты хуже, чем не показать её совсем.
    """
    return [_CATALOGUE[code] for code in codes if code in _CATALOGUE]
