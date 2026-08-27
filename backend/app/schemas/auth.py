from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AuthSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class RegisterRequest(AuthSchema):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80, alias="displayName")


class LoginRequest(AuthSchema):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class PasswordResetRequest(AuthSchema):
    """Заявка на смену пароля: человек оставляет почту."""

    email: EmailStr


class PasswordResetConfirm(AuthSchema):
    """Новый пароль по ссылке из письма.

    Требования к длине те же, что при регистрации: восстановление не
    должно быть щелью, через которую в кабинет попадает пароль слабее
    того, что мы просим на входе.
    """

    token: str = Field(min_length=20, max_length=2048)
    password: str = Field(min_length=8, max_length=128)


class PasswordResetSent(AuthSchema):
    """Ответ на заявку: куда ушло письмо и насколько живёт ссылка."""

    email: EmailStr
    expires_in_minutes: int = Field(gt=0, alias="expiresInMinutes")


class AccessTokenResponse(AuthSchema):
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")
    expires_in: int = Field(gt=0, alias="expiresIn")


class TokenPairResponse(AccessTokenResponse):
    refresh_token: str = Field(alias="refreshToken")


class RefreshRequest(AuthSchema):
    refresh_token: str = Field(min_length=20, alias="refreshToken")


class OAuthStartResponse(AuthSchema):
    authorization_url: str = Field(alias="authorizationUrl")
    state: str


class UpdateProfileRequest(AuthSchema):
    display_name: str = Field(
        min_length=1,
        max_length=80,
        alias="displayName",
        description="Имя, которым кабинет обращается к человеку",
    )
    email: EmailStr


class ChangePasswordRequest(AuthSchema):
    current_password: str = Field(
        min_length=1,
        max_length=128,
        alias="currentPassword",
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        alias="newPassword",
    )


class DeleteAccountRequest(AuthSchema):
    password: str = Field(min_length=1, max_length=128)


class AuthProviderResponse(AuthSchema):
    """Способ входа, доступный на экране авторизации."""

    provider: str
    name: str
    authorization_url: str | None = Field(
        default=None, alias="authorizationUrl"
    )
    bot_username: str | None = Field(default=None, alias="botUsername")


class OAuthCallbackRequest(AuthSchema):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=4096)


class TelegramLoginRequest(AuthSchema):
    """Данные виджета Telegram вместе с его подписью."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: int
    auth_date: int = Field(alias="auth_date")
    hash: str = Field(min_length=1, max_length=256)
