"""Ссылка на приглашение друга в кабинете и её счётчики.

Хранилище наград здесь поддельное: у проекта нет тестовой базы, а
маршрут проверяется независимо от того, как считает сама рефералка
(это Task 3, test_referral.py).
"""

from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_reward_store
from app.core.config import Settings, get_settings
from app.main import create_app
from app.models.user import User

REFERRAL_PATH = "/api/v1/cabinet/referral"
TEST_USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def _user(remnawave_username: str | None) -> User:
    return User(
        id=TEST_USER_ID,
        email="anfisa@vpanfi.ru",
        display_name="Тестовая Анфиса",
        password_digest="unused",
        is_active=True,
        is_admin=False,
        remnawave_username=remnawave_username,
    )


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"_env_file": None}
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class FakeRewardStore:
    """Считает, вызвали ли счётчики, и отдаёт заготовленный ответ."""

    def __init__(self, friends: int = 0, days_earned: int = 0) -> None:
        self._friends = friends
        self._days_earned = days_earned
        self.calls: list[str] = []

    async def inviter_stats(self, inviter_username: str) -> tuple[int, int]:
        self.calls.append(inviter_username)
        return self._friends, self._days_earned


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as instance:
        yield instance
    app.dependency_overrides.clear()


def test_referral_requires_a_token(client: TestClient) -> None:
    response = client.get(REFERRAL_PATH)

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_access_token"


def test_disabled_program_gives_no_link_and_skips_the_store(
    app: FastAPI, client: TestClient
) -> None:
    store = FakeRewardStore(friends=99, days_earned=99)
    app.dependency_overrides[get_current_user] = lambda: _user("Alyona_Tutina")
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=False
    )
    app.dependency_overrides[get_reward_store] = lambda: store

    response = client.get(REFERRAL_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "link": None,
        "friends": 0,
        "daysEarned": 0,
        "friendDays": 15,
        "inviterDays": 15,
    }
    assert store.calls == []


def test_enabled_program_without_a_panel_account_has_no_link(
    app: FastAPI, client: TestClient
) -> None:
    store = FakeRewardStore(friends=5, days_earned=150)
    app.dependency_overrides[get_current_user] = lambda: _user(None)
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=True
    )
    app.dependency_overrides[get_reward_store] = lambda: store

    response = client.get(REFERRAL_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["link"] is None
    assert body["friends"] == 0
    assert body["daysEarned"] == 0
    assert store.calls == []


def test_enabled_program_returns_the_encoded_link_and_counters(
    app: FastAPI, client: TestClient
) -> None:
    store = FakeRewardStore(friends=3, days_earned=90)
    app.dependency_overrides[get_current_user] = lambda: _user(
        "Alyona Tutina"
    )
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=True,
        referral_friend_days=30,
        referral_inviter_days=30,
        frontend_origin="https://vpanfi.su",
    )
    app.dependency_overrides[get_reward_store] = lambda: store

    response = client.get(REFERRAL_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["link"] == "https://vpanfi.su/?ref=Alyona%20Tutina"
    assert body["friends"] == 3
    assert body["daysEarned"] == 90
    assert body["friendDays"] == 30
    assert body["inviterDays"] == 30
    assert store.calls == ["Alyona Tutina"]
