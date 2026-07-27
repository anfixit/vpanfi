"""Кабинет закрыт: без действующего токена личных данных не видно."""

from fastapi.testclient import TestClient

PRIVATE_ROUTES = [
    ("get", "/api/v1/cabinet/dashboard"),
    ("get", "/api/v1/cabinet/devices"),
    ("get", "/api/v1/cabinet/payments"),
    ("delete", "/api/v1/cabinet/devices/device_demo"),
]


def test_private_routes_require_a_token(
    anonymous_client: TestClient,
) -> None:
    for method, path in PRIVATE_ROUTES:
        response = getattr(anonymous_client, method)(path)
        assert response.status_code == 401, path
        assert response.json()["detail"]["code"] == "missing_access_token"


def test_private_routes_reject_a_forged_token(
    anonymous_client: TestClient,
) -> None:
    headers = {"Authorization": "Bearer not-a-real-token"}

    for method, path in PRIVATE_ROUTES:
        response = getattr(anonymous_client, method)(path, headers=headers)
        assert response.status_code == 401, path
        assert response.json()["detail"]["code"] == "invalid_access_token"


def test_connection_clients_stay_public(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get("/api/v1/cabinet/connection-clients")

    assert response.status_code == 200
