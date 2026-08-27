import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
from app.services.notify import (
    TelegramNotifier,
    registraciya_soobshchenie,
    vhod_soobshchenie,
)
from app.services.trial import TrialService


class EmailAlreadyRegisteredError(ValueError):
    pass


class InvalidCredentialsError(ValueError):
    """Общий отказ. Оставлен ради совместимости с прежними вызовами."""


class EmailNotRegisteredError(InvalidCredentialsError):
    """Такой почты в кабинете нет."""


class WrongLoginPasswordError(InvalidCredentialsError):
    """Почта есть, пароль не подходит."""


class PasswordLoginUnavailableError(InvalidCredentialsError):
    """Аккаунт заведён через внешний вход, пароля у него нет.

    Отдельный случай, потому что «неверный пароль» здесь неправда:
    человек его никогда не задавал и будет вводить варианты
    до бесконечности.
    """

    def __init__(self, provider: str) -> None:
        super().__init__(provider)
        self.provider = provider


class AccountDisabledError(InvalidCredentialsError):
    """Аккаунт отключён."""


class InvalidResetTokenError(ValueError):
    """Ссылка восстановления не годится.

    Подделана, просрочена или уже использована.
    """


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
        # Пробный доступ выдаём после того, как аккаунт закреплён:
        # панель может не ответить, и терять из-за этого регистрацию
        # нельзя. Ошибку grant глотает сам и пишет в журнал.
        granted = await TrialService(self._session, self._settings).grant(user)
        self._soobshchit(
            "registration",
            registraciya_soobshchenie(
                email=user.email,
                display_name=user.display_name,
                trial_granted=granted,
            ),
        )
        return tokens

    async def login(self, request: LoginRequest) -> TokenPairResponse:
        """Впустить в кабинет или объяснить, что именно не так.

        Раньше на все четыре случая отвечали «Неверный email или пароль».
        Человеку, который завёл вход через Телеграм, это сообщение
        предлагает вечно подбирать пароль, которого он не задавал, а
        тому, кто ошибся в адресе, ничего не подсказывает.

        Развёрнутый ответ позволяет постороннему проверить, заведена ли
        почта. Для сервиса такого размера это приемлемая цена за то,
        чтобы человек не терялся на входе.
        """
        user = await self._users.get_by_email(request.email)
        if user is None:
            raise EmailNotRegisteredError(request.email)
        if not user.is_active:
            raise AccountDisabledError(request.email)
        if user.password_digest is None:
            raise PasswordLoginUnavailableError(self._external_provider(user))
        if not verify_password(request.password, user.password_digest):
            raise WrongLoginPasswordError(request.email)

        tokens = await self._issue_token_pair(user)
        await self._session.commit()
        self._soobshchit(
            "login",
            vhod_soobshchenie(
                email=user.email, display_name=user.display_name
            ),
        )
        return tokens

    def _soobshchit(self, sobytie: str, text: str) -> None:
        """Рассказать владельцу о движении на сайте.

        Ни регистрация, ни вход не должны зависеть от телеграма:
        отправка уходит в фон и молчит, если событие выключено или
        уведомления не настроены.
        """
        if sobytie not in self._settings.alert_events:
            return
        TelegramNotifier(self._settings).send_later(text)

    async def start_password_reset(self, email: str) -> tuple[User, str]:
        """Выдать ссылку восстановления. Письмо шлёт вызывающий.

        Ссылка это подписанный токен, а не запись в базе: лишняя
        таблица здесь ничего не даёт, а вот протухание нужно, и его
        даёт срок жизни токена.

        В токен кладём отпечаток нынешнего пароля. Как только пароль
        сменится, отпечаток перестанет совпадать, и ссылка умрёт: одну
        и ту же ссылку нельзя использовать дважды, а старое письмо
        в чужом ящике перестаёт быть ключом от аккаунта.
        """
        user = await self._users.get_by_email(email.lower())
        if user is None:
            raise EmailNotRegisteredError(email)
        if not user.is_active:
            raise AccountDisabledError(email)

        token = create_token(
            subject=str(user.id),
            token_type="password_reset",
            expires_delta=timedelta(
                minutes=self._settings.password_reset_ttl_minutes
            ),
            settings=self._settings,
            extra_claims={"pwd": self._password_fingerprint(user)},
        )
        return user, token

    async def finish_password_reset(self, token: str, password: str) -> User:
        """Поставить новый пароль по ссылке из письма.

        Все сеансы после смены закрываем: если пароль восстанавливают,
        доступ мог быть у кого-то ещё, и оставлять ему живой вход
        значит сделать восстановление бессмысленным.
        """
        try:
            payload = decode_token(
                token,
                expected_type="password_reset",
                settings=self._settings,
            )
        except InvalidTokenError as error:
            raise InvalidResetTokenError(str(error)) from error

        try:
            user_id = UUID(str(payload.get("sub")))
        except ValueError as error:
            raise InvalidResetTokenError("subject is not a user id") from error

        # Забираем сразу со связями: ответ показывает способы входа,
        # а дотягивать их лениво асинхронная сессия не умеет. Пароль
        # к этому моменту уже сменён, поэтому падение здесь выглядит
        # как «пароль не сменился», хотя сменился.
        user = await self._session.scalar(
            select(User)
            .options(selectinload(User.identities))
            .where(User.id == user_id)
        )
        if user is None or not user.is_active:
            raise InvalidResetTokenError("user is gone or disabled")

        if payload.get("pwd") != self._password_fingerprint(user):
            # Пароль уже меняли после того, как выдали эту ссылку.
            raise InvalidResetTokenError("link has already been used")

        user.password_digest = hash_password(password)
        await self._revoke_all_sessions(user)
        await self._session.commit()
        return user

    @staticmethod
    def _password_fingerprint(user: User) -> str:
        """Короткий отпечаток пароля. Сам пароль по нему не восстановить."""
        digest = user.password_digest or ""
        return hashlib.sha256(digest.encode()).hexdigest()[:16]

    @staticmethod
    def _external_provider(user: User) -> str:
        """Каким входом человек пользовался, чтобы назвать его в ответе."""
        identities = getattr(user, "identities", None) or []
        for identity in identities:
            provider = getattr(identity, "provider", None)
            if provider:
                return str(getattr(provider, "value", provider))
        return ""

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
        user.remnawave_user_id = None
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
