import pytest
from pydantic import ValidationError

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
