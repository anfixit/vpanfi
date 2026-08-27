"""Человек, который не может войти, потерян так же, как не купивший.

Раньше на все четыре причины отказа сайт отвечал «Неверный email или
пароль», а восстановления не было вовсе. Заведший вход через Телеграм
подбирал пароль, которого не задавал, и подобрать не мог никогда.
"""

from datetime import timedelta
from typing import Any

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.core.security import create_token, hash_password
from app.services.auth import (
    AuthService,
    InvalidResetTokenError,
)
from app.services.letters import password_reset_letter
from tests.conftest import build_user


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "jwt_secret": SecretStr("secret-for-tests-only-not-real"),
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class FakeSession:
    """Сессия, помнящая только то, что нужно проверке."""

    def __init__(self, user: Any = None) -> None:
        self.user = user
        self.commits = 0
        self.statements: list[Any] = []

    async def get(self, _model: Any, _key: Any) -> Any:
        return self.user

    async def execute(self, statement: Any) -> None:
        self.statements.append(statement)

    async def commit(self) -> None:
        self.commits += 1


def _service(session: Any, settings: Settings | None = None) -> AuthService:
    return AuthService(session, settings or _settings())


def _reset_token(
    user: Any,
    settings: Settings,
    *,
    minutes: int = 60,
    fingerprint: str | None = None,
) -> str:
    return create_token(
        subject=str(user.id),
        token_type="password_reset",
        expires_delta=timedelta(minutes=minutes),
        settings=settings,
        extra_claims={
            "pwd": fingerprint
            if fingerprint is not None
            else AuthService._password_fingerprint(user)
        },
    )


@pytest.mark.anyio
async def test_new_password_replaces_the_old_one() -> None:
    settings = _settings()
    user = build_user()
    user.password_digest = hash_password("staryj-parol-2026")
    session = FakeSession(user)
    was = user.password_digest

    await _service(session, settings).finish_password_reset(
        _reset_token(user, settings), "novyj-parol-2026"
    )

    assert user.password_digest != was
    assert session.commits == 1


@pytest.mark.anyio
async def test_link_dies_after_it_is_used() -> None:
    """Иначе письмо в чужом ящике навсегда остаётся ключом.

    Отпечаток пароля лежит в самом токене, поэтому первая же смена
    делает ссылку негодной, и хранить использованные ссылки не нужно.
    """
    settings = _settings()
    user = build_user()
    user.password_digest = hash_password("staryj-parol-2026")
    session = FakeSession(user)
    token = _reset_token(user, settings)

    service = _service(session, settings)
    await service.finish_password_reset(token, "novyj-parol-2026")

    with pytest.raises(InvalidResetTokenError):
        await service.finish_password_reset(token, "eshchyo-odin-2026")


@pytest.mark.anyio
async def test_expired_link_is_refused() -> None:
    settings = _settings()
    user = build_user()
    user.password_digest = hash_password("staryj-parol-2026")
    token = _reset_token(user, settings, minutes=-1)

    with pytest.raises(InvalidResetTokenError):
        await _service(FakeSession(user), settings).finish_password_reset(
            token, "novyj-parol-2026"
        )


@pytest.mark.anyio
async def test_token_signed_with_another_secret_is_refused() -> None:
    """Подпись — единственное, что отличает нашу ссылку от чужой."""
    user = build_user()
    user.password_digest = hash_password("staryj-parol-2026")
    chuzhoj = _reset_token(user, _settings(jwt_secret=SecretStr("chuzhoj-kl")))

    with pytest.raises(InvalidResetTokenError):
        await _service(FakeSession(user)).finish_password_reset(
            chuzhoj, "novyj-parol-2026"
        )


@pytest.mark.anyio
async def test_access_token_does_not_work_as_a_reset_link() -> None:
    """Тип токена проверяется: обычный вход не должен менять пароль."""
    settings = _settings()
    user = build_user()
    user.password_digest = hash_password("staryj-parol-2026")
    access = create_token(
        subject=str(user.id),
        token_type="access",
        expires_delta=timedelta(minutes=15),
        settings=settings,
    )

    with pytest.raises(InvalidResetTokenError):
        await _service(FakeSession(user), settings).finish_password_reset(
            access, "novyj-parol-2026"
        )


@pytest.mark.anyio
async def test_disabled_account_cannot_be_taken_over() -> None:
    settings = _settings()
    user = build_user()
    user.password_digest = hash_password("staryj-parol-2026")
    token = _reset_token(user, settings)
    user.is_active = False

    with pytest.raises(InvalidResetTokenError):
        await _service(FakeSession(user), settings).finish_password_reset(
            token, "novyj-parol-2026"
        )


@pytest.mark.anyio
async def test_reset_closes_every_open_session() -> None:
    """Пароль восстанавливают, когда доступ мог быть у кого-то ещё.

    Оставить чужому живой вход значит сделать восстановление
    бессмысленным.
    """
    settings = _settings()
    user = build_user()
    user.password_digest = hash_password("staryj-parol-2026")
    session = FakeSession(user)

    await _service(session, settings).finish_password_reset(
        _reset_token(user, settings), "novyj-parol-2026"
    )

    assert session.statements, "сеансы не закрывали"


def test_login_names_the_actual_cause() -> None:
    """Четыре разные причины и четыре разных ответа."""
    import inspect

    from app.api.routes import auth as routes

    source = inspect.getsource(routes.login)

    for code in (
        "email_not_registered",
        "wrong_password",
        "password_login_unavailable",
        "account_disabled",
    ):
        assert code in source


def test_letter_says_how_long_the_link_lives() -> None:
    """Открывший письмо назавтра должен понять, почему ссылка мертва."""
    letter = password_reset_letter(
        reset_url="https://vpanfi.su/password/reset?token=abc",
        ttl_minutes=60,
        support_url="https://t.me/Anfikus",
        support_email="anfisa.kovganyuk@gmail.com",
    )

    assert "час" in letter.text
    assert "https://vpanfi.su/password/reset?token=abc" in letter.text
    assert "час" in letter.html


def test_letter_tells_the_innocent_reader_to_do_nothing() -> None:
    """Письмо может прийти тому, кто ничего не просил."""
    letter = password_reset_letter(
        reset_url="https://vpanfi.su/password/reset?token=abc",
        ttl_minutes=60,
        support_url="https://t.me/Anfikus",
        support_email="anfisa.kovganyuk@gmail.com",
    )

    assert "ничего не просили" in letter.text
    assert "ничего не просили" in letter.html


def test_reset_password_is_as_long_as_at_registration() -> None:
    """Восстановление не должно быть щелью для слабого пароля."""
    from pydantic import ValidationError

    from app.schemas.auth import PasswordResetConfirm, RegisterRequest

    reset_min = PasswordResetConfirm.model_fields["password"].metadata
    register_min = RegisterRequest.model_fields["password"].metadata

    assert str(reset_min) == str(register_min)

    with pytest.raises(ValidationError):
        PasswordResetConfirm(token="t" * 20, password="korotko")
