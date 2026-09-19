import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import DEFAULT_JWT_SECRET, Settings

STRONG_SECRET = "a" * 64


def test_empty_remnawave_values_are_treated_as_unset() -> None:
    settings = Settings(
        _env_file=None,
        remnawave_base_url="",
        remnawave_api_token="",
    )

    assert settings.remnawave_base_url is None
    assert settings.remnawave_api_token is None


def test_development_keeps_the_placeholder_secret() -> None:
    settings = Settings(_env_file=None)

    assert settings.jwt_secret.get_secret_value() == DEFAULT_JWT_SECRET
    assert settings.is_production is False


def test_production_rejects_the_placeholder_secret() -> None:
    with pytest.raises(ValidationError, match="VPANFI_JWT_SECRET"):
        Settings(_env_file=None, environment="production")


def test_production_rejects_a_short_secret() -> None:
    with pytest.raises(ValidationError, match="at least"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret="too-short",
        )


def test_production_rejects_debug_mode() -> None:
    with pytest.raises(ValidationError, match="VPANFI_DEBUG"):
        Settings(
            _env_file=None,
            environment="production",
            jwt_secret=STRONG_SECRET,
            debug=True,
        )


def test_production_accepts_a_generated_secret() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret=STRONG_SECRET,
    )

    assert settings.is_production is True


def test_allowed_origins_splits_a_comma_separated_list() -> None:
    settings = Settings(
        _env_file=None,
        frontend_origin="https://vpanfi.ru, https://www.vpanfi.ru",
    )

    assert settings.allowed_origins == [
        "https://vpanfi.ru",
        "https://www.vpanfi.ru",
    ]


def test_platega_is_not_configured_without_both_values() -> None:
    """Одного мерчанта без секрета мало: касса настроена целиком или нет."""
    only_merchant = Settings(_env_file=None, platega_merchant_id="cf9fe88f")

    assert only_merchant.is_platega_configured is False


def test_platega_is_configured_when_both_values_are_present() -> None:
    settings = Settings(
        _env_file=None,
        platega_merchant_id="cf9fe88f",
        platega_secret=SecretStr("secret"),
    )

    assert settings.is_platega_configured is True
    assert str(settings.platega_base_url).rstrip("/") == "https://app.platega.io"
    assert settings.platega_payment_method == 2


def test_empty_platega_values_are_treated_as_unset() -> None:
    """Пустая переменная — это «не настроено», а не «настроено пустым»."""
    settings = Settings(
        _env_file=None,
        platega_merchant_id="",
        platega_secret="",
    )

    assert settings.platega_merchant_id is None
    assert settings.platega_secret is None
    assert settings.is_platega_configured is False


def test_referral_defaults_are_off_and_thirty_days() -> None:
    """Рефералка молчит, пока её не включат явно.

    Тридцать дней тому и другому, потолок пять человек в месяц и
    получасовой повтор для фоновой задачи: числа из замысла программы.
    """
    settings = Settings(_env_file=None)

    assert settings.referral_enabled is False
    assert settings.referral_friend_days == 15
    assert settings.referral_inviter_days == 15
    assert settings.referral_renewal_days == 15
    assert settings.referral_renewal_min_gap_days == 20
    assert settings.referral_monthly_cap == 5
    assert settings.referral_retry_minutes == 30
    assert settings.bedolaga_api_url == "https://vpanfibot.ru/api"
    assert settings.bedolaga_api_token is None
    assert settings.is_bedolaga_configured is False


def test_referral_enabled_is_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VPANFI_REFERRAL_ENABLED", "true")

    settings = Settings(_env_file=None)

    assert settings.referral_enabled is True


def test_bedolaga_is_configured_only_with_a_token() -> None:
    settings = Settings(
        _env_file=None, bedolaga_api_token=SecretStr("secret")
    )

    assert settings.is_bedolaga_configured is True


def test_empty_bedolaga_token_is_treated_as_unset() -> None:
    """Секрет из GitHub может прийти пустым: пустая строка это не ключ."""
    settings = Settings(_env_file=None, bedolaga_api_token="")

    assert settings.bedolaga_api_token is None
    assert settings.is_bedolaga_configured is False
