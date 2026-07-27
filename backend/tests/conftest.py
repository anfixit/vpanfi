from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.main import create_app
from app.models.user import User

TEST_USER_ID = UUID("11111111-2222-3333-4444-555555555555")


def build_user() -> User:
    """Пользователь в памяти: тестам кабинета база не нужна."""
    return User(
        id=TEST_USER_ID,
        email="anfisa@vpanfi.ru",
        display_name="Тестовая Анфиса",
        password_digest="unused",
        is_active=True,
        is_admin=False,
    )


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
def anonymous_client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as client:
        yield client


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    app.dependency_overrides[get_current_user] = build_user
    with TestClient(app) as authenticated:
        yield authenticated
    app.dependency_overrides.clear()
