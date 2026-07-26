from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=80, serialization_alias="displayName")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPairResponse(BaseModel):
    access_token: str = Field(serialization_alias="accessToken")
    refresh_token: str = Field(serialization_alias="refreshToken")
    token_type: str = Field(default="bearer", serialization_alias="tokenType")
    expires_in: int = Field(gt=0, serialization_alias="expiresIn")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, serialization_alias="refreshToken")


class OAuthStartResponse(BaseModel):
    authorization_url: str = Field(serialization_alias="authorizationUrl")
    state: str
