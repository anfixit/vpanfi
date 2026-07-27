from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import InvalidTokenError, decode_token
from app.db.session import get_db_session
from app.models.user import User
from app.repositories.users import UserRepository
from app.services.auth import AuthService
from app.services.cabinet import CabinetService
from app.services.subscription import SubscriptionService

__all__ = [
    "CurrentUser",
    "DatabaseSession",
    "get_auth_service",
    "get_cabinet_service",
    "get_current_user",
    "get_subscription_service",
]

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

bearer_scheme = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


@lru_cache
def get_cabinet_service() -> CabinetService:
    return CabinetService()


def get_auth_service(session: DatabaseSession) -> AuthService:
    return AuthService(session, get_settings())


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: BearerCredentials,
    session: DatabaseSession,
    settings: SettingsDep,
) -> User:
    """Вернуть пользователя, подписавшего запрос access-токеном.

    Raises:
        HTTPException: 401, если токена нет, он недействителен или
            пользователь отключён.
    """
    if credentials is None:
        raise _unauthorized("missing_access_token", "Нужно войти в кабинет")

    try:
        payload = decode_token(
            credentials.credentials,
            expected_type="access",
            settings=settings,
        )
        user_id = UUID(str(payload["sub"]))
    except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
        raise _unauthorized(
            "invalid_access_token",
            "Сеанс истёк, войдите заново",
        ) from error

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or not user.is_active:
        raise _unauthorized("user_unavailable", "Аккаунт недоступен")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_subscription_service(
    session: DatabaseSession,
    settings: SettingsDep,
) -> SubscriptionService:
    return SubscriptionService(session, settings)
