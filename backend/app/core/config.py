from functools import lru_cache
from typing import Literal, Self

from pydantic import AnyHttpUrl, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]

DEFAULT_JWT_SECRET = "change-me-before-production"
MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    """Конфигурация VPaNfi из переменных окружения."""

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

    jwt_secret: SecretStr = SecretStr(DEFAULT_JWT_SECRET)
    access_token_minutes: int = 15
    refresh_token_days: int = 30

    remnawave_base_url: AnyHttpUrl | None = None
    remnawave_api_token: SecretStr | None = None
    remnawave_timeout_seconds: float = 10.0

    # Касса сайта. Мерчант отдельный от кассы бота: у бота свой, и
    # перепутать их значит увести деньги на чужой счёт.
    platega_merchant_id: str | None = None
    platega_secret: SecretStr | None = None
    platega_base_url: AnyHttpUrl = AnyHttpUrl("https://app.platega.io")
    platega_timeout_seconds: float = 15.0
    # 2 — СБП, тот же способ оплаты, который бот показывает на витрине.
    platega_payment_method: int = 2

    # Витрина бота: сайт читает оттуда тарифы и цены, чтобы они не
    # разъехались с ботом.
    shop_base_url: AnyHttpUrl = AnyHttpUrl(
        "https://vpanfibot.ru/cabinet/landing"
    )
    shop_slug: str = "vpanfi"

    # Поддержка — живой человек, а не бот оформления: с вопросом
    # в меню покупки идти некуда.
    telegram_support_url: AnyHttpUrl = AnyHttpUrl("https://t.me/Anfikus")

    # Способы входа в кабинет. Каждый включается независимо: провайдер
    # без учётных данных просто не предлагается на экране входа, а не
    # ломает вход остальным.
    #
    # Бот входа — отдельная сущность от бота, который продаёт подписки.
    # Telegram здесь только подтверждает личность и ничего не говорит о
    # том, какая подписка принадлежит человеку: её находит собственная
    # ссылка подписки.
    telegram_login_bot_token: SecretStr | None = None
    telegram_login_bot_username: str | None = None
    vk_client_id: str | None = None
    vk_client_secret: SecretStr | None = None
    yandex_client_id: str | None = None
    yandex_client_secret: SecretStr | None = None
    oauth_redirect_url: AnyHttpUrl | None = None

    @field_validator(
        "remnawave_base_url",
        "remnawave_api_token",
        "platega_merchant_id",
        "platega_secret",
        "telegram_login_bot_token",
        "telegram_login_bot_username",
        "vk_client_id",
        "vk_client_secret",
        "yandex_client_id",
        "yandex_client_secret",
        "oauth_redirect_url",
        mode="before",
    )
    @classmethod
    def empty_optional_secret_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def production_requires_real_secrets(self) -> Self:
        """Не дать приложению подняться в проде с дефолтным ключом.

        Раньше отсутствие настройки означало бы рабочий сервис, который
        подписывает токены общеизвестным значением: любой смог бы
        выпустить себе валидный access token.

        Raises:
            ValueError: Если в production JWT-ключ дефолтный или короткий.
        """
        if not self.is_production:
            return self

        secret = self.jwt_secret.get_secret_value()
        if secret == DEFAULT_JWT_SECRET:
            raise ValueError(
                "VPANFI_JWT_SECRET must be set to a unique value in "
                "production"
            )
        if len(secret) < MIN_JWT_SECRET_LENGTH:
            raise ValueError(
                "VPANFI_JWT_SECRET must be at least "
                f"{MIN_JWT_SECRET_LENGTH} characters in production"
            )

        if self.debug:
            raise ValueError("VPANFI_DEBUG must stay off in production")

        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def vk_enabled(self) -> bool:
        return bool(self.vk_client_id and self.vk_client_secret)

    @property
    def yandex_enabled(self) -> bool:
        return bool(self.yandex_client_id and self.yandex_client_secret)

    @property
    def telegram_enabled(self) -> bool:
        return bool(
            self.telegram_login_bot_token
            and self.telegram_login_bot_username
        )

    @property
    def redirect_url(self) -> str:
        """Куда провайдер возвращает пользователя после согласия."""
        if self.oauth_redirect_url is not None:
            return str(self.oauth_redirect_url)

        origin = self.allowed_origins[0] if self.allowed_origins else ""
        return f"{origin.rstrip('/')}/auth/callback"

    @property
    def is_platega_configured(self) -> bool:
        """Касса готова, только когда есть и мерчант, и секрет.

        Половина реквизитов хуже, чем ничего: платёж создастся и упрётся
        в отказ авторизации уже после того, как человек нажал «оплатить».
        """
        return bool(self.platega_merchant_id and self.platega_secret)

    @property
    def allowed_origins(self) -> list[str]:
        """Источники, которым разрешён доступ к API из браузера."""
        origins = self.frontend_origin.split(",")
        return [origin.strip() for origin in origins if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
