from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User

__all__ = ["UserRepository"]


class UserRepository:
    """Доступ к пользователям кабинета."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        # Связанные аккаунты загружаются сразу: профиль читает их уже за
        # пределами асинхронного контекста, а ленивая подгрузка там
        # заканчивается ошибкой вместо данных.
        statement = (
            select(User)
            .options(selectinload(User.identities))
            .where(User.id == user_id)
        )
        return await self._session.scalar(statement)

    async def get_by_email(self, email: str) -> User | None:
        statement = (
            select(User)
            .options(selectinload(User.identities))
            .where(func.lower(User.email) == email.strip().lower())
        )
        return await self._session.scalar(statement)

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user
