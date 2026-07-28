"""Административный раздел закрыт для обычного пользователя.

Флаг is_admin существовал в модели и попадал в токен, но его никто не
проверял: раздел был доступен любому вошедшему.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_admin_service, get_current_user
from app.schemas.admin import AdminOverviewResponse
from tests.conftest import build_user

ADMIN_ROUTES = [
    ("get", "/api/v1/admin/overview", None),
    ("get", "/api/v1/admin/users", None),
]
ADMIN_WRITES = [
    (
        "/api/v1/admin/users/"
        "11111111-2222-3333-4444-555555555555/subscription/extend",
        {"days": 30},
    ),
    (
        "/api/v1/admin/users/"
        "11111111-2222-3333-4444-555555555555/subscription/trial",
        {"username": "anfisa", "days": 7},
    ),
]


def build_admin():
    admin = build_user()
    admin.is_admin = True
    return admin


def test_admin_routes_reject_anonymous(anonymous_client: TestClient) -> None:
    for method, path, _ in ADMIN_ROUTES:
        response = getattr(anonymous_client, method)(path)
        assert response.status_code == 401, path


def test_admin_routes_reject_a_signed_in_user(client: TestClient) -> None:
    for method, path, _ in ADMIN_ROUTES:
        response = getattr(client, method)(path)
        assert response.status_code == 403, path
        assert response.json()["detail"]["code"] == "admin_required"


def test_admin_writes_reject_a_signed_in_user(client: TestClient) -> None:
    for path, body in ADMIN_WRITES:
        response = client.post(path, json=body)
        assert response.status_code == 403, path
        assert response.json()["detail"]["code"] == "admin_required"


class StubAdminService:
    """Подменяет базу: проверяется только проход через права доступа."""

    async def overview(self) -> AdminOverviewResponse:
        return AdminOverviewResponse(
            total_users=7,
            linked_users=3,
            admins=1,
            registered_last_30_days=2,
        )


def test_admin_flag_opens_the_section(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = build_admin
    app.dependency_overrides[get_admin_service] = StubAdminService

    with TestClient(app) as admin_client:
        response = admin_client.get("/api/v1/admin/overview")

    assert response.status_code == 200
    assert response.json()["totalUsers"] == 7
    assert response.json()["registeredLast30Days"] == 2

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_admin_service, None)


def test_extension_length_is_validated(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = build_admin

    with TestClient(app) as admin_client:
        path = ADMIN_WRITES[0][0]
        too_long = admin_client.post(path, json={"days": 5000})
        too_short = admin_client.post(path, json={"days": 0})

    assert too_long.status_code == 422
    assert too_short.status_code == 422
    app.dependency_overrides.pop(get_current_user, None)


def test_panel_username_is_validated(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = build_admin

    with TestClient(app) as admin_client:
        response = admin_client.post(
            ADMIN_WRITES[1][0],
            json={"username": "не латиница", "days": 7},
        )

    assert response.status_code == 422
    app.dependency_overrides.pop(get_current_user, None)
