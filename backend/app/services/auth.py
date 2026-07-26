from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.billing import BillingAccount
from app.models.session import RefreshSession
from app.models.user import User
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPairResponse


class EmailAlreadyRegisteredError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InvalidRefreshSessionError(ValueError):
    pass


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)

    async def register(self, request: RegisterRequest) -> TokenPairResponse:
        email = request.email.lower()
        if await self._users.get_by_email(email) is not None:
            raise EmailAlreadyRegisteredError(email)

        user = User(
            email=email,
            display_name=request.display_name.strip(),
            password_digest=hash_password(request.password),
        )
        await self._users.add(user)
        self._session.add(BillingAccount(user_id=user.id))

        tokens = await self._issue_token_pair(user)
        await self._session.commit()
        return tokens

    async def login(self, request: LoginRequest) -> TokenPairResponse:
        user = await self._users.get_by_email(request.email)
        if (
            user is None
            or not user.is_active
            or user.password_digest is None
            or not verify_password(request.password, user.password_digest)
        ):
            raise InvalidCredentialsError

        tokens = await self._issue_token_pair(user)
        await self._session.commit()
        return tokens

    async def refresh(self, request: RefreshRequest) -> TokenPairResponse:
        try:
            payload = decode_token(
                request.refresh_token,
                expected_type="refresh",
                settings=self._settings,
            )
            user_id = UUID(str(payload["sub"]))
            token_id = str(payload["jti"])
        except (InvalidTokenError, KeyError, TypeError, ValueError) as error:
            raise InvalidRefreshSessionError from error

        statement = select(RefreshSession).where(RefreshSession.token_id == token_id)
        refresh_session = await self._session.scalar(statement)
        now = datetime.now(UTC)

        if (
            refresh_session is None
            or refresh_session.revoked
            or refresh_session.expires_at <= now
            or refresh_session.user_id != user_id
        ):
            raise InvalidRefreshSessionError

        user = await self._users.get_by_id(user_id)
        if user is None or not user.is_active:
            raise InvalidRefreshSessionError

        refresh_session.revoked = True
        tokens = await self._issue_token_pair(user)
        await self._session.commit()
        return tokens

    async def _issue_token_pair(self, user: User) -> TokenPairResponse:
        access_delta = timedelta(minutes=self._settings.access_token_minutes)
        refresh_delta = timedelta(days=self._settings.refresh_token_days)
        refresh_token_id = str(uuid4())
        refresh_expires_at = datetime.now(UTC) + refresh_delta

        access_token = create_token(
            subject=str(user.id),
            token_type="access",
            expires_delta=access_delta,
            settings=self._settings,
            extra_claims={"admin": user.is_admin},
        )
        refresh_token = create_token(
            subject=str(user.id),
            token_type="refresh",
            expires_delta=refresh_delta,
            settings=self._settings,
            token_id=refresh_token_id,
        )

        self._session.add(
            RefreshSession(
                user_id=user.id,
                token_id=refresh_token_id,
                expires_at=refresh_expires_at,
            )
        )

        return TokenPairResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(access_delta.total_seconds()),
        )
