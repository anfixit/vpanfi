from fastapi.testclient import TestClient

from app.main import create_app


def test_healthcheck() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_unlink_device_returns_no_content() -> None:
    with TestClient(create_app()) as client:
        response = client.delete("/api/v1/cabinet/devices/device_demo")

    assert response.status_code == 204
    assert response.content == b""
