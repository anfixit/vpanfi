"""Вход в кабинет через Telegram, VK и Яндекс."""

import hashlib
import hmac
import time
from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.security import (
    InvalidTokenError,
    create_token,
    decode_token,
)
from app.models.user import ExternalIdentity, IdentityProvider, User
from app.schemas.auth import TokenPairResponse
from app.services.auth import AuthService

__all__ = [
    "IdentityAlreadyLinkedError",
    "OAuthService",
    "ProviderNotConfiguredError",
    "ProviderRejectedError",
    "ProviderUnavailableError",
    "TelegramCheckFailedError",
]

# Ссылка на согласие живёт недолго: state носит с собой срок годности,
# поэтому хранить его на сервере не нужно.
STATE_LIFETIME = timedelta(minutes=15)
TELEGRAM_AUTH_MAX_AGE_SECONDS = 300
HTTP_TIMEOUT_SECONDS = 10.0

VK_AUTHORIZE_URL = "https://id.vk.com/authorize"
VK_TOKEN_URL = "https://id.vk.com/oauth2/auth"
VK_USER_URL = "https://id.vk.com/oauth2/user_info"
YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_USER_URL = "https://login.yandex.ru/info"


class ProviderNotConfiguredError(RuntimeError):
    """У провайдера нет учётных данных, вход через него выключен."""


class ProviderUnavailableError(RuntimeError):
    """Провайдер недоступен или ответил неожиданно."""


class ProviderRejectedError(ValueError):
    """Провайдер не подтвердил вход: истёкший или подменённый ответ."""


class TelegramCheckFailedError(ProviderRejectedError):
    """Подпись данных Telegram не сошлась."""


class IdentityAlreadyLinkedError(ValueError):
    """Этот внешний аккаунт уже привязан к другому пользователю."""


class OAuthService:
    """Вход и привязка внешних аккаунтов.

    Один и тот же механизм обслуживает и вход на публичном экране, и
    привязку в профиле: в обоих случаях внешняя личность связывается с
    пользователем кабинета. Разница только в том, есть ли уже вошедший
    пользователь.
    """

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._auth = AuthService(session, settings)

    def available_providers(self) -> list[IdentityProvider]:
        """Провайдеры, у которых есть учётные данные."""
        providers: list[IdentityProvider] = []
        if self._settings.telegram_enabled:
            providers.append(IdentityProvider.TELEGRAM)
        if self._settings.vk_enabled:
            providers.append(IdentityProvider.VK)
        if self._settings.yandex_enabled:
            providers.append(IdentityProvider.YANDEX)
        return providers

    def authorization_url(self, provider: IdentityProvider) -> str:
        """Ссылка на страницу согласия провайдера.

        Raises:
            ProviderNotConfiguredError: Провайдер не настроен.
        """
        self._require(provider)
        state = self._issue_state(provider)
        redirect = self._settings.redirect_url

        if provider is IdentityProvider.VK:
            query = {
                "client_id": self._settings.vk_client_id,
                "redirect_uri": redirect,
                "response_type": "code",
                "scope": "email",
                "state": state,
            }
            return f"{VK_AUTHORIZE_URL}?{urlencode(query)}"

        if provider is IdentityProvider.YANDEX:
            query = {
                "client_id": self._settings.yandex_client_id,
                "redirect_uri": redirect,
                "response_type": "code",
                "state": state,
            }
            return f"{YANDEX_AUTHORIZE_URL}?{urlencode(query)}"

        # Telegram не использует OAuth: у него виджет входа, который сам
        # передаёт подписанные данные в браузер.
        raise ProviderNotConfiguredError(
            "Telegram uses its login widget, not an authorization URL"
        )

    async def complete(
        self,
        provider: IdentityProvider,
        *,
        code: str,
        state: str,
        current_user: User | None = None,
    ) -> TokenPairResponse:
        """Завершить вход после возврата от провайдера.

        Raises:
            ProviderNotConfiguredError: Провайдер не настроен.
            ProviderRejectedError: state не сошёлся или истёк.
            ProviderUnavailableError: Провайдер недоступен.
            IdentityAlreadyLinkedError: Аккаунт занят другим пользователем.
        """
        self._require(provider)
        self._check_state(provider, state)

        if provider is IdentityProvider.VK:
            profile = await self._fetch_vk_profile(code)
        elif provider is IdentityProvider.YANDEX:
            profile = await self._fetch_yandex_profile(code)
        else:
            raise ProviderNotConfiguredError(str(provider))

        return await self._sign_in(provider, profile, current_user)

    async def complete_telegram(
        self,
        payload: Mapping[str, Any],
        *,
        current_user: User | None = None,
    ) -> TokenPairResponse:
        """Проверить подпись виджета Telegram и войти.

        Raises:
            ProviderNotConfiguredError: Токен бота не задан.
            TelegramCheckFailedError: Подпись не сошлась или устарела.
        """
        self._require(IdentityProvider.TELEGRAM)
        assert self._settings.telegram_login_bot_token is not None

        token = self._settings.telegram_login_bot_token.get_secret_value()
        profile = _verify_telegram(payload, bot_token=token)
        return await self._sign_in(
            IdentityProvider.TELEGRAM, profile, current_user
        )

    async def unlink(
        self,
        user: User,
        provider: IdentityProvider,
    ) -> None:
        """Отвязать внешний аккаунт.

        Raises:
            ProviderRejectedError: Это последний способ войти.
        """
        remaining = [
            identity
            for identity in user.identities
            if identity.provider is not provider
        ]

        if user.password_digest is None and not remaining:
            raise ProviderRejectedError(
                "Нельзя отвязать последний способ входа: сначала "
                "задайте пароль"
            )

        for identity in list(user.identities):
            if identity.provider is provider:
                user.identities.remove(identity)

        await self._session.commit()

    def _require(self, provider: IdentityProvider) -> None:
        if provider not in self.available_providers():
            raise ProviderNotConfiguredError(str(provider))

    def _issue_state(self, provider: IdentityProvider) -> str:
        return create_token(
            subject=str(provider),
            token_type="access",
            expires_delta=STATE_LIFETIME,
            settings=self._settings,
            extra_claims={"purpose": "oauth_state"},
        )

    def _check_state(self, provider: IdentityProvider, state: str) -> None:
        try:
            payload = decode_token(
                state,
                expected_type="access",
                settings=self._settings,
            )
        except InvalidTokenError as error:
            raise ProviderRejectedError("Ссылка входа устарела") from error

        if payload.get("purpose") != "oauth_state":
            raise ProviderRejectedError("Неожиданный state")
        if payload.get("sub") != str(provider):
            raise ProviderRejectedError("state выдан другому провайдеру")

    async def _sign_in(
        self,
        provider: IdentityProvider,
        profile: "ExternalProfile",
        current_user: User | None,
    ) -> TokenPairResponse:
        identity = await self._find_identity(provider, profile.provider_id)

        if current_user is not None:
            if identity is not None and identity.user_id != current_user.id:
                raise IdentityAlreadyLinkedError(profile.provider_id)
            user = current_user
        elif identity is not None:
            user = identity.user
        else:
            user = await self._find_or_create_user(profile)

        if identity is None:
            user.identities.append(
                ExternalIdentity(
                    provider=provider,
                    provider_user_id=profile.provider_id,
                    provider_email=profile.email,
                    provider_username=profile.username,
                )
            )

        tokens = await self._auth.issue_tokens(user)
        await self._session.commit()
        return tokens

    async def _find_identity(
        self,
        provider: IdentityProvider,
        provider_user_id: str,
    ) -> ExternalIdentity | None:
        statement = (
            select(ExternalIdentity)
            .options(
                selectinload(ExternalIdentity.user).selectinload(
                    User.identities
                )
            )
            .where(
                ExternalIdentity.provider == provider,
                ExternalIdentity.provider_user_id == provider_user_id,
            )
        )
        return await self._session.scalar(statement)

    async def _find_or_create_user(self, profile: "ExternalProfile") -> User:
        if profile.email:
            existing = await self._auth.find_by_email(profile.email)
            if existing is not None:
                return existing

        return await self._auth.create_external_user(
            email=profile.email
            or f"{profile.provider_id}@external.vpanfi.ru",
            display_name=profile.display_name,
        )

    async def _fetch_vk_profile(self, code: str) -> "ExternalProfile":
        assert self._settings.vk_client_secret is not None

        tokens = await self._post(
            VK_TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._settings.vk_client_id,
                "client_secret": (
                    self._settings.vk_client_secret.get_secret_value()
                ),
                "redirect_uri": self._settings.redirect_url,
            },
        )
        access_token = str(tokens.get("access_token") or "")
        if not access_token:
            raise ProviderUnavailableError("VK did not return a token")

        info = await self._post(VK_USER_URL, {"access_token": access_token})
        user = info.get("user") if isinstance(info, Mapping) else None
        body = user if isinstance(user, Mapping) else info

        provider_id = body.get("user_id") or tokens.get("user_id") or ""

        return ExternalProfile(
            provider_id=str(provider_id),
            email=_optional(body.get("email")),
            username=_optional(body.get("first_name")),
            display_name=" ".join(
                part
                for part in (
                    str(body.get("first_name") or ""),
                    str(body.get("last_name") or ""),
                )
                if part
            )
            or "Пользователь VK",
        )

    async def _fetch_yandex_profile(self, code: str) -> "ExternalProfile":
        assert self._settings.yandex_client_secret is not None

        tokens = await self._post(
            YANDEX_TOKEN_URL,
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self._settings.yandex_client_id,
                "client_secret": (
                    self._settings.yandex_client_secret.get_secret_value()
                ),
            },
        )
        access_token = str(tokens.get("access_token") or "")
        if not access_token:
            raise ProviderUnavailableError("Yandex did not return a token")

        info = await self._get(
            YANDEX_USER_URL,
            headers={"Authorization": f"OAuth {access_token}"},
        )

        return ExternalProfile(
            provider_id=str(info.get("id") or ""),
            email=_optional(info.get("default_email")),
            username=_optional(info.get("login")),
            display_name=str(
                info.get("real_name")
                or info.get("display_name")
                or "Пользователь Яндекса"
            ),
        )

    async def _post(
        self,
        url: str,
        data: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return await self._request("POST", url, data=data)

    async def _get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
    ) -> Mapping[str, Any]:
        return await self._request("GET", url, headers=headers)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT_SECONDS
            ) as client:
                response = await client.request(
                    method, url, data=data, headers=headers
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(str(error)) from error
        except ValueError as error:
            raise ProviderUnavailableError("Ответ не является JSON") from error

        if not isinstance(payload, Mapping):
            raise ProviderUnavailableError("Неожиданный ответ провайдера")
        return payload


class ExternalProfile:
    """Данные о человеке, полученные от провайдера."""

    def __init__(
        self,
        *,
        provider_id: str,
        display_name: str,
        email: str | None = None,
        username: str | None = None,
    ) -> None:
        if not provider_id:
            raise ProviderUnavailableError(
                "Провайдер не сообщил идентификатор пользователя"
            )

        self.provider_id = provider_id
        self.display_name = display_name
        self.email = email
        self.username = username


def _verify_telegram(
    payload: Mapping[str, Any],
    *,
    bot_token: str,
) -> ExternalProfile:
    """Проверить подпись данных виджета Telegram.

    Telegram подписывает поля HMAC-SHA256 на ключе SHA256(bot_token).
    Без этой проверки любой мог бы прислать чужой telegram id и войти
    под ним, поэтому подпись обязательна.
    """
    received_hash = str(payload.get("hash") or "")
    if not received_hash:
        raise TelegramCheckFailedError("Нет подписи")

    pairs = sorted(
        f"{key}={value}"
        for key, value in payload.items()
        if key != "hash" and value is not None
    )
    secret = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(
        secret, "\n".join(pairs).encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, received_hash):
        raise TelegramCheckFailedError("Подпись не сошлась")

    auth_date = int(payload.get("auth_date") or 0)
    if auth_date <= 0:
        raise TelegramCheckFailedError("Нет времени входа")

    if time.time() - auth_date > TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise TelegramCheckFailedError("Данные входа устарели")

    first = str(payload.get("first_name") or "")
    last = str(payload.get("last_name") or "")

    return ExternalProfile(
        provider_id=str(payload.get("id") or ""),
        display_name=" ".join(p for p in (first, last) if p)
        or "Пользователь Telegram",
        username=_optional(payload.get("username")),
    )


def _optional(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None
