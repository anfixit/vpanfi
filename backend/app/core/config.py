from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="VPANFI_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    frontend_origin: str = "http://localhost:5173"

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://vpanfi:vpanfi@postgres:5432/vpanfi"
    )
    redis_url: SecretStr = SecretStr("redis://redis:6379/0")

    jwt_secret: SecretStr = SecretStr("change-me-before-production")
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    remnawave_base_url: AnyHttpUrl | None = None
    remnawave_api_token: SecretStr | None = None
    remnawave_timeout_seconds: float = 10.0

    telegram_support_url: AnyHttpUrl = AnyHttpUrl("https://t.me/VPaNfi_bot")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
