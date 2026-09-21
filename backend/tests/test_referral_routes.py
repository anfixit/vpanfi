"""Ссылка на приглашение друга в кабинете и её счётчики.

Хранилище наград здесь поддельное: у проекта нет тестовой базы, а
маршрут проверяется независимо от того, как считает сама рефералка
(это Task 3, test_referral.py).
"""

from collections.abc import Callable, Iterator
from types import TracebackType
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_user,
    get_panel_gateway_factory,
    get_reward_store,
)
from app.core.config import Settings, get_settings
from app.integrations.remnawave.client import (
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)
from app.main import create_app
from app.models.user import User

REFERRAL_PATH = "/api/v1/cabinet/referral"
TEST_USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def _user(
    remnawave_username: str | None,
    remnawave_user_id: int | None = None,
) -> User:
    return User(
        id=TEST_USER_ID,
        email="anfisa@vpanfi.ru",
        display_name="Тестовая Анфиса",
        password_digest="unused",
        is_active=True,
        is_admin=False,
        remnawave_username=remnawave_username,
        remnawave_user_id=remnawave_user_id,
    )


class FakePanelGateway:
    """Поддельный шлюз панели: отдаёт заготовленного пользователя или
    падает."""

    def __init__(
        self,
        *,
        status: str = "ACTIVE",
        tag: str | None = "PAID",
        not_found: bool = False,
        error: Exception | None = None,
    ) -> None:
        self._payload = {"status": status, "tag": tag}
        self._not_found = not_found
        self._error = error

    async def __aenter__(self) -> "FakePanelGateway":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def get_user_by_id(self, user_id: int) -> dict[str, Any]:
        return await self._respond()

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        return await self._respond()

    async def _respond(self) -> dict[str, Any]:
        if self._error is not None:
            raise self._error
        if self._not_found:
            raise RemnawaveUserNotFoundError("not found")
        return self._payload


def _panel_factory(gateway: FakePanelGateway) -> Any:
    """Override для get_panel_gateway_factory: без параметров, как оригинал.

    Возвращает саму фабрику Settings -> шлюз, а не шлюз напрямую:
    FastAPI подставляет эту функцию вместо зависимости и разбирает её
    сигнатуру, поэтому лишний параметр здесь означал бы для него
    новое поле запроса.
    """

    def factory(settings: Settings) -> FakePanelGateway:
        return gateway

    def provide_factory() -> Callable[[Settings], FakePanelGateway]:
        return factory

    return provide_factory


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
        "Alyona Tutina", remnawave_user_id=1
    )
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=True,
        referral_friend_days=30,
        referral_inviter_days=30,
        frontend_origin="https://vpanfi.su",
    )
    app.dependency_overrides[get_reward_store] = lambda: store
    app.dependency_overrides[get_panel_gateway_factory] = _panel_factory(
        FakePanelGateway(status="ACTIVE", tag="PAID")
    )

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


def test_trial_user_gets_no_card_and_store_is_not_touched(
    app: FastAPI, client: TestClient
) -> None:
    store = FakeRewardStore(friends=7, days_earned=70)
    app.dependency_overrides[get_current_user] = lambda: _user(
        "Novichok", remnawave_user_id=2
    )
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=True
    )
    app.dependency_overrides[get_reward_store] = lambda: store
    app.dependency_overrides[get_panel_gateway_factory] = _panel_factory(
        FakePanelGateway(status="ACTIVE", tag="TRIAL")
    )

    response = client.get(REFERRAL_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["link"] is None
    assert store.calls == []


def test_expired_paid_user_gets_no_card(
    app: FastAPI, client: TestClient
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(
        "Byvshiy", remnawave_user_id=3
    )
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=True
    )
    app.dependency_overrides[get_reward_store] = lambda: FakeRewardStore()
    app.dependency_overrides[get_panel_gateway_factory] = _panel_factory(
        FakePanelGateway(status="EXPIRED", tag="PAID")
    )

    response = client.get(REFERRAL_PATH)

    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_svoi_user_gets_the_card(
    app: FastAPI, client: TestClient
) -> None:
    store = FakeRewardStore(friends=1, days_earned=15)
    app.dependency_overrides[get_current_user] = lambda: _user(
        "Svoi_Chelovek", remnawave_user_id=4
    )
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=True,
        frontend_origin="https://vpanfi.su",
    )
    app.dependency_overrides[get_reward_store] = lambda: store
    app.dependency_overrides[get_panel_gateway_factory] = _panel_factory(
        FakePanelGateway(status="ACTIVE", tag="SVOI")
    )

    response = client.get(REFERRAL_PATH)

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["link"] == "https://vpanfi.su/?ref=Svoi_Chelovek"


def test_panel_unavailable_disables_the_card_without_a_5xx(
    app: FastAPI, client: TestClient
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(
        "Kto_To", remnawave_user_id=5
    )
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=True
    )
    app.dependency_overrides[get_reward_store] = lambda: FakeRewardStore()
    app.dependency_overrides[get_panel_gateway_factory] = _panel_factory(
        FakePanelGateway(error=RemnawaveUnavailableError("панель легла"))
    )

    response = client.get(REFERRAL_PATH)

    assert response.status_code == 200
    assert response.json()["enabled"] is False


def test_unknown_panel_user_disables_the_card(
    app: FastAPI, client: TestClient
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(
        "Prizrak", remnawave_user_id=6
    )
    app.dependency_overrides[get_settings] = lambda: _settings(
        referral_enabled=True
    )
    app.dependency_overrides[get_reward_store] = lambda: FakeRewardStore()
    app.dependency_overrides[get_panel_gateway_factory] = _panel_factory(
        FakePanelGateway(not_found=True)
    )

    response = client.get(REFERRAL_PATH)

    assert response.status_code == 200
    assert response.json()["enabled"] is False
