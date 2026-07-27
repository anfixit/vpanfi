from fastapi.testclient import TestClient

from app.main import create_app

DEMO_ORIGIN = "http://localhost:5173"


def test_healthcheck() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "development",
    }


def test_healthcheck_carries_security_headers() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in (
        response.headers["Content-Security-Policy"]
    )


def test_cors_allows_the_configured_origin() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz", headers={"Origin": DEMO_ORIGIN})

    assert response.headers["access-control-allow-origin"] == DEMO_ORIGIN


def test_cors_rejects_an_unknown_origin() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/healthz",
            headers={"Origin": "https://attacker.example"},
        )

    assert "access-control-allow-origin" not in response.headers


def test_documentation_is_available_outside_production() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/docs")

    assert response.status_code == 200


def test_dashboard_contract_uses_frontend_aliases() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/cabinet/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["subscription"]["planName"] == "6 месяцев"
    assert payload["subscription"]["trafficLabel"] == "Без лимита"
    assert payload["subscription"]["devicesLimit"] == 3
    assert payload["recentPayments"]
    assert payload["profile"]["telegramLinked"] is True


def test_devices_contract_matches_the_frontend() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/cabinet/devices")

    assert response.status_code == 200
    devices = response.json()
    assert devices
    assert {"id", "name", "platform", "current"} <= set(devices[0])


def test_connection_clients_offer_one_recommendation_per_platform() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/cabinet/connection-clients")

    assert response.status_code == 200
    clients = response.json()
    platforms = {client["platform"] for client in clients}
    for platform in platforms:
        recommended = [
            client
            for client in clients
            if client["platform"] == platform and client["recommended"]
        ]
        assert len(recommended) == 1


def test_unlink_device_returns_no_content() -> None:
    with TestClient(create_app()) as client:
        response = client.delete("/api/v1/cabinet/devices/device_demo")

    assert response.status_code == 204
    assert response.content == b""


def test_unknown_route_returns_not_found() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/cabinet/does-not-exist")

    assert response.status_code == 404
