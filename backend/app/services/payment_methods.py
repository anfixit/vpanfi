"""Способы оплаты, которые сайт показывает покупателю.

До этого модуля сайт умел ровно один способ: код 2, СБП. Он был зашит
в настройки одним числом и уходил в Platega при каждом платеже. Человек
без СБП не мог заплатить ничем, хотя у мерчанта сайта включены и карты,
и криптовалюта, а карта в России есть у всех.

Названия живут здесь, а не на фронтенде: список включённых способов
меняется в настройках, и витрина не должна знать наперёд, какие бывают
коды. Незнакомый код лучше не показывать вовсе, чем подписать
«Метод 14»: человек не должен гадать, куда его ведут с деньгами.
"""

from dataclasses import dataclass

__all__ = ["PaymentMethod", "known_methods", "is_known"]


@dataclass(frozen=True)
class PaymentMethod:
    """Способ оплаты глазами покупателя."""

    code: int
    name: str
    description: str


# Коды задаёт Platega, менять их по своему усмотрению нельзя.
_CATALOGUE: dict[int, PaymentMethod] = {
    2: PaymentMethod(
        code=2,
        name="СБП",
        description="QR-код или кнопка в приложении Вашего банка",
    ),
    11: PaymentMethod(
        code=11,
        name="Российская карта",
        description="Мир, Visa или Mastercard российского банка",
    ),
    12: PaymentMethod(
        code=12,
        name="Зарубежная карта",
        description="Карта банка вне России",
    ),
    13: PaymentMethod(
        code=13,
        name="Криптовалюта",
        description="Оплата в USDT и других монетах",
    ),
}


def is_known(code: int) -> bool:
    """Знаем ли мы, как называется этот способ."""
    return code in _CATALOGUE


def known_methods(codes: list[int]) -> list[PaymentMethod]:
    """Описания включённых способов, в том же порядке.

    Неизвестные коды выпадают: показать человеку безымянную кнопку
    оплаты хуже, чем не показать её совсем.
    """
    return [_CATALOGUE[code] for code in codes if code in _CATALOGUE]
