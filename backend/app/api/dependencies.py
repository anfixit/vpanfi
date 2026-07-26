from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.auth import AuthService
from app.services.cabinet import CabinetService

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@lru_cache
def get_cabinet_service() -> CabinetService:
    return CabinetService()


def get_auth_service(session: DatabaseSession) -> AuthService:
    return AuthService(session, get_settings())
