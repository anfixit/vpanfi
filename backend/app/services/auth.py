from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
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
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPairResponse,
)


class EmailAlreadyRegisteredError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    pass


class InvalidRefreshSessionError(ValueError):
    pass


class EmailTakenError(ValueError):
    """Такой адрес уже принадлежит другому аккаунту."""


class WrongPasswordError(ValueError):
    """Введён неверный текущий пароль."""


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

    async def update_profile(
        self,
        user: User,
        *,
        display_name: str,
        email: str,
    ) -> User:
        """Сохранить имя и адрес пользователя.

        Raises:
            EmailTakenError: Адрес занят другим аккаунтом.
        """
        normalized = email.strip().lower()

        if normalized != user.email:
            existing = await self._users.get_by_email(normalized)
            if existing is not None and existing.id != user.id:
                raise EmailTakenError(normalized)
            user.email = normalized

        user.display_name = display_name.strip()
        await self._session.commit()
        return user

    async def change_password(
        self,
        user: User,
        *,
        current_password: str,
        new_password: str,
    ) -> TokenPairResponse:
        """Сменить пароль и завершить остальные сеансы.

        Возвращает свежую пару токенов: смена пароля отзывает все
        refresh-сессии, поэтому текущему устройству нужна новая.

        Raises:
            WrongPasswordError: Текущий пароль не подошёл.
        """
        if user.password_digest is None or not verify_password(
            current_password, user.password_digest
        ):
            raise WrongPasswordError

        user.password_digest = hash_password(new_password)
        await self._revoke_all_sessions(user)

        tokens = await self._issue_token_pair(user)
        await self._session.commit()
        return tokens

    async def delete_account(self, user: User, password: str) -> None:
        """Удалить личные данные аккаунта.

        Строка пользователя остаётся, но обезличивается: на неё
        ссылаются платежи, а финансовую историю удалять нельзя. После
        этого войти в аккаунт невозможно, а прежний адрес снова
        свободен для регистрации.

        Подписка в панели не трогается: она может быть оплачена и
        принадлежит панели, а не кабинету.

        Raises:
            WrongPasswordError: Пароль не подошёл.
        """
        if user.password_digest is None or not verify_password(
            password, user.password_digest
        ):
            raise WrongPasswordError

        await self._revoke_all_sessions(user)
        user.identities.clear()

        user.email = f"deleted-{user.id}@vpanfi.ru"
        user.display_name = "Удалённый аккаунт"
        user.password_digest = None
        user.is_active = False
        user.is_admin = False
        user.remnawave_user_uuid = None
        user.remnawave_username = None

        await self._session.commit()

    async def issue_tokens(self, user: User) -> TokenPairResponse:
        """Выдать пару токенов уже известному пользователю.

        Нужна входу через внешних провайдеров: пароль там не проверяется,
        личность подтверждает провайдер.
        """
        return await self._issue_token_pair(user)

    async def find_by_email(self, email: str) -> User | None:
        """Найти пользователя по адресу."""
        return await self._users.get_by_email(email)

    async def create_external_user(
        self,
        *,
        email: str,
        display_name: str,
    ) -> User:
        """Создать аккаунт для входа через провайдера, без пароля.

        Пароль остаётся пустым: человек не задавал его и войти по нему
        нельзя. Задать его можно позже в профиле.
        """
        user = User(
            email=email.strip().lower(),
            display_name=display_name.strip() or "Пользователь",
            password_digest=None,
        )
        await self._users.add(user)
        self._session.add(BillingAccount(user_id=user.id))
        return user

    async def _revoke_all_sessions(self, user: User) -> None:
        await self._session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == user.id)
            .values(revoked=True)
        )

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

        statement = select(RefreshSession).where(
            RefreshSession.token_id == token_id
        )
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
