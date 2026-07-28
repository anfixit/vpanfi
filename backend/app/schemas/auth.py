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
