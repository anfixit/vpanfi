"""Вход через внешних провайдеров.

Подпись Telegram и state в OAuth — это защита от входа под чужим
аккаунтом, поэтому проверяются в первую очередь именно отказы.
"""

import hashlib
import hmac
import time
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.user import IdentityProvider
from app.services.oauth import (
    OAuthService,
    ProviderNotConfiguredError,
    ProviderRejectedError,
    TelegramCheckFailedError,
    _verify_telegram,
)

BOT_TOKEN = "123456:AAaaBBbbCCccDDdd"
STRONG_SECRET = "s" * 64


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {"_env_file": None, "jwt_secret": STRONG_SECRET}
    base.update(overrides)
    return Settings(**base)


def service(**overrides: Any) -> OAuthService:
    # Сессия не нужна: проверяются ссылки, state и подписи.
    return OAuthService(
        AsyncSession.__new__(AsyncSession), settings(**overrides)
    )


def sign_telegram(payload: dict[str, Any], token: str = BOT_TOKEN) -> dict:
    pairs = sorted(
        f"{key}={value}" for key, value in payload.items() if key != "hash"
    )
    secret = hashlib.sha256(token.encode()).digest()
    signature = hmac.new(
        secret, "\n".join(pairs).encode(), hashlib.sha256
    ).hexdigest()
    return {**payload, "hash": signature}


def telegram_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "id": 4242,
        "first_name": "Анфиса",
        "last_name": "Ковганюк",
        "username": "anfisa",
        "auth_date": int(time.time()),
    }
    payload.update(overrides)
    return payload


def test_no_providers_without_credentials() -> None:
    assert service().available_providers() == []


def test_providers_appear_one_by_one() -> None:
    only_vk = service(vk_client_id="1", vk_client_secret="secret")
    assert only_vk.available_providers() == [IdentityProvider.VK]

    both = service(
        vk_client_id="1",
        vk_client_secret="secret",
        yandex_client_id="2",
        yandex_client_secret="secret",
    )
    assert both.available_providers() == [
        IdentityProvider.VK,
        IdentityProvider.YANDEX,
    ]


def test_authorization_url_is_refused_without_credentials() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        service().authorization_url(IdentityProvider.VK)


def test_vk_authorization_url_carries_redirect_and_state() -> None:
    configured = service(
        vk_client_id="1234",
        vk_client_secret="secret",
        frontend_origin="https://vpanfi.su",
    )

    url = configured.authorization_url(IdentityProvider.VK)

    assert url.startswith("https://id.vk.com/authorize?")
    assert "client_id=1234" in url
    assert "vpanfi.su%2Fauth%2Fcallback" in url
    assert "state=" in url


def test_yandex_authorization_url_is_built() -> None:
    configured = service(
        yandex_client_id="abc",
        yandex_client_secret="secret",
        frontend_origin="https://vpanfi.su",
    )

    url = configured.authorization_url(IdentityProvider.YANDEX)

    assert url.startswith("https://oauth.yandex.ru/authorize?")
    assert "client_id=abc" in url


def test_telegram_has_no_authorization_url() -> None:
    configured = service(
        telegram_bot_token=BOT_TOKEN, telegram_bot_username="VPaNfi_bot"
    )

    # У Telegram виджет, а не страница согласия.
    with pytest.raises(ProviderNotConfiguredError):
        configured.authorization_url(IdentityProvider.TELEGRAM)


def test_state_from_another_provider_is_refused() -> None:
    configured = service(
        vk_client_id="1",
        vk_client_secret="secret",
        yandex_client_id="2",
        yandex_client_secret="secret",
    )
    vk_url = configured.authorization_url(IdentityProvider.VK)
    vk_state = vk_url.split("state=")[1]

    with pytest.raises(ProviderRejectedError, match="провайдеру"):
        configured._check_state(IdentityProvider.YANDEX, vk_state)


def test_forged_state_is_refused() -> None:
    configured = service(vk_client_id="1", vk_client_secret="secret")

    with pytest.raises(ProviderRejectedError):
        configured._check_state(IdentityProvider.VK, "not-a-real-state")


def test_valid_telegram_signature_is_accepted() -> None:
    profile = _verify_telegram(
        sign_telegram(telegram_payload()), bot_token=BOT_TOKEN
    )

    assert profile.provider_id == "4242"
    assert profile.display_name == "Анфиса Ковганюк"
    assert profile.username == "anfisa"


def test_telegram_without_a_signature_is_refused() -> None:
    with pytest.raises(TelegramCheckFailedError, match="Нет подписи"):
        _verify_telegram(telegram_payload(), bot_token=BOT_TOKEN)


def test_tampered_telegram_id_is_refused() -> None:
    signed = sign_telegram(telegram_payload())
    # Подменяем идентификатор, оставив чужую подпись: без проверки так
    # можно было бы войти под любым аккаунтом.
    signed["id"] = 999

    with pytest.raises(TelegramCheckFailedError, match="не сошлась"):
        _verify_telegram(signed, bot_token=BOT_TOKEN)


def test_telegram_signed_by_another_bot_is_refused() -> None:
    signed = sign_telegram(telegram_payload(), token="999:OTHERTOKEN")

    with pytest.raises(TelegramCheckFailedError, match="не сошлась"):
        _verify_telegram(signed, bot_token=BOT_TOKEN)


def test_stale_telegram_login_is_refused() -> None:
    stale = sign_telegram(
        telegram_payload(auth_date=int(time.time()) - 3600)
    )

    with pytest.raises(TelegramCheckFailedError, match="устарели"):
        _verify_telegram(stale, bot_token=BOT_TOKEN)
