from app.core.config import Settings


def test_empty_remnawave_values_are_treated_as_unset() -> None:
    settings = Settings(
        _env_file=None,
        remnawave_base_url="",
        remnawave_api_token="",
    )

    assert settings.remnawave_base_url is None
    assert settings.remnawave_api_token is None
