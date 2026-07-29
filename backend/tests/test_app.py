from fastapi.testclient import TestClient

DEMO_ORIGIN = "http://localhost:5173"


def test_healthcheck(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "development",
    }


def test_healthcheck_carries_security_headers(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get("/healthz")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in (
        response.headers["Content-Security-Policy"]
    )


def test_cors_allows_the_configured_origin(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get(
        "/healthz", headers={"Origin": DEMO_ORIGIN}
    )

    assert response.headers["access-control-allow-origin"] == DEMO_ORIGIN


def test_cors_rejects_an_unknown_origin(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get(
        "/healthz",
        headers={"Origin": "https://attacker.example"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_documentation_is_available_outside_production(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get("/docs")

    assert response.status_code == 200


def test_dashboard_without_a_subscription_shows_the_real_profile(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/cabinet/dashboard")

    assert response.status_code == 200
    payload = response.json()
    # Ни имени, ни платежей демонстрационного «Алексея» здесь быть не
    # должно: это данные конкретного вошедшего человека.
    assert payload["subscription"] is None
    assert payload["recentPayments"] == []
    assert payload["profile"]["displayName"] == "Тестовая Анфиса"
    assert payload["profile"]["email"] == "anfisa@vpanfi.ru"
    assert payload["countries"]


def test_devices_are_empty_without_a_linked_subscription(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/cabinet/devices")

    assert response.status_code == 200
    # Раньше здесь появлялись три придуманных устройства, которых у
    # человека нет.
    assert response.json() == []


def test_connection_clients_offer_one_recommendation_per_platform(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.get("/api/v1/cabinet/connection-clients")

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


def test_unlink_device_returns_no_content(client: TestClient) -> None:
    response = client.delete("/api/v1/cabinet/devices/device_demo")

    assert response.status_code == 204
    assert response.content == b""


def test_unknown_route_returns_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/cabinet/does-not-exist")

    assert response.status_code == 404


def test_me_returns_the_signed_in_profile(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 200
    payload = response.json()
    assert payload["displayName"] == "Тестовая Анфиса"
    assert payload["email"] == "anfisa@vpanfi.ru"


def test_me_requires_a_token(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_profile_update_requires_a_token(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.patch(
        "/api/v1/auth/me",
        json={"displayName": "Кто-то", "email": "someone@vpanfi.ru"},
    )

    assert response.status_code == 401


def test_profile_update_validates_the_name(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/auth/me",
        json={"displayName": "", "email": "anfisa@vpanfi.ru"},
    )

    assert response.status_code == 422


def test_profile_update_validates_the_email(client: TestClient) -> None:
    response = client.patch(
        "/api/v1/auth/me",
        json={"displayName": "Анфиса", "email": "not-an-email"},
    )

    assert response.status_code == 422


def test_password_change_requires_a_token(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.post(
        "/api/v1/auth/password",
        json={"currentPassword": "old", "newPassword": "new-password-1"},
    )

    assert response.status_code == 401


def test_password_change_rejects_a_short_password(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/password",
        json={"currentPassword": "whatever", "newPassword": "short"},
    )

    assert response.status_code == 422


def test_account_deletion_requires_a_token(
    anonymous_client: TestClient,
) -> None:
    response = anonymous_client.request(
        "DELETE",
        "/api/v1/auth/me",
        json={"password": "whatever"},
    )

    assert response.status_code == 401


def test_countries_are_public_and_real(anonymous_client: TestClient) -> None:
    response = anonymous_client.get("/api/v1/cabinet/countries")

    assert response.status_code == 200
    names = {country["name"] for country in response.json()}
    # Витрина обещала Японию и Испанию, которых у сервиса нет.
    assert "Япония" not in names
    assert "Испания" not in names
    assert {"Германия", "Финляндия", "Швеция"} <= names
