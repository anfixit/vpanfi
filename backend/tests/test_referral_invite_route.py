"""Тесты открытого маршрута ``GET /api/v1/referral/invite``.

Резолвер здесь поддельный: правила самого резолвера уже проверены в
test_referral_invite.py, а этому тесту важно только то, что маршрут
не требует токена, отдаёт форму ответа и превращает любой сбой
резолвера в тот же самый ответ с пустой ссылкой, а не в 500.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_invite_resolver
from app.core.config import Settings, get_settings
from app.main import create_app
from app.services.referral_invite import InviteResolver

INVITE_PATH = "/api/v1/referral/invite"


class FakeResolver:
    def __init__(self, url: str | None = None) -> None:
        self.url = url
        self.calls: list[str | None] = []

    async def resolve(
        self, code: str | None, settings: Settings
    ) -> str | None:
        self.calls.append(code)
        return self.url


class _BrokenPanel:
    """Панель, которая падает при входе: имитирует настоящий сбой сети."""

    async def __aenter__(self) -> "_BrokenPanel":
        raise RuntimeError("панель не отвечает")

    async def __aexit__(self, *exc_info: object) -> None:
        return None


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as instance:
        yield instance
    app.dependency_overrides.clear()


def test_invite_requires_no_token(app: FastAPI, client: TestClient) -> None:
    app.dependency_overrides[get_invite_resolver] = lambda: FakeResolver(
        "https://t.me/VPaNfi_bot?start=abc"
    )

    response = client.get(INVITE_PATH, params={"ref": "Alyona_Tutina"})

    assert response.status_code == 200
    assert response.json() == {
        "telegramUrl": "https://t.me/VPaNfi_bot?start=abc"
    }


def test_invite_without_ref_gives_null(
    app: FastAPI, client: TestClient
) -> None:
    resolver = FakeResolver(None)
    app.dependency_overrides[get_invite_resolver] = lambda: resolver

    response = client.get(INVITE_PATH)

    assert response.status_code == 200
    assert response.json() == {"telegramUrl": None}
    assert resolver.calls == [None]


def test_invite_returns_null_shape_when_resolver_finds_nothing(
    app: FastAPI, client: TestClient
) -> None:
    app.dependency_overrides[get_invite_resolver] = lambda: FakeResolver(None)

    response = client.get(INVITE_PATH, params={"ref": "no-such-user"})

    assert response.status_code == 200
    assert response.json() == {"telegramUrl": None}


def test_invite_gives_null_on_a_real_lookup_failure(
    app: FastAPI, client: TestClient
) -> None:
    """Настоящий сбой похода в панель не должен долетать до маршрута.

    Резолвер тут настоящий, а не поддельный: сама гарантия "не
    бросает исключений" уже проверена в test_referral_invite.py, а
    здесь важно только то, что маршрут не заворачивает вызов резолвера
    во что-то своё, что могло бы эту гарантию сломать.
    """
    resolver = InviteResolver(panel_factory=lambda settings: _BrokenPanel())
    app.dependency_overrides[get_invite_resolver] = lambda: resolver
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        referral_enabled=True,
        referral_bot_enabled=True,
        bedolaga_api_token="test-token",
    )

    response = client.get(INVITE_PATH, params={"ref": "Alyona_Tutina"})

    assert response.status_code == 200
    assert response.json() == {"telegramUrl": None}
