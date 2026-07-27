"""Запросы пользователя тянут связанные аккаунты сразу.

Профиль читает ``user.identities`` уже после того, как запрос к базе
завершён. При ленивой загрузке это заканчивается ошибкой на боевом
сервере, хотя в тестах с объектом в памяти всё выглядит исправным —
поэтому проверяется именно наличие eager-загрузки в запросе.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

from app.models.user import User
from app.repositories.users import UserRepository


def loaded_relationships(statement: object) -> set[str]:
    options = getattr(statement, "_with_options", ())
    names: set[str] = set()
    for option in options:
        for element in getattr(option, "path", ()):
            name = getattr(element, "key", None)
            if name:
                names.add(name)
    return names


async def captured_statement(method: str, *args: object) -> object:
    session = AsyncMock()
    session.scalar.return_value = None
    await getattr(UserRepository(session), method)(*args)
    return session.scalar.await_args.args[0]


async def test_lookup_by_id_loads_identities() -> None:
    statement = await captured_statement("get_by_id", uuid4())

    assert "identities" in loaded_relationships(statement)


async def test_lookup_by_email_loads_identities() -> None:
    statement = await captured_statement("get_by_email", "anfisa@vpanfi.ru")

    assert "identities" in loaded_relationships(statement)


def test_identities_are_not_loaded_by_default() -> None:
    # Если это перестанет быть правдой, eager-загрузка выше лишняя.
    assert User.identities.property.lazy == "select"
