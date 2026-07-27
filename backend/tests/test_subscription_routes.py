"""Ошибки привязки доходят до пользователя понятным кодом."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_subscription_service
from app.models.user import User
from app.schemas.cabinet import (
    DeviceResponse,
    SubscriptionLinkResponse,
    SubscriptionResponse,
    SubscriptionStatus,
)
from app.services.subscription import (
    PanelUnavailableError,
    SubscriptionAlreadyClaimedError,
    SubscriptionLinkInvalidError,
    SubscriptionNotFoundError,
)

LINK_PATH = "/api/v1/cabinet/subscription/link"


class StubSubscriptionService:
    """Подменяет панель: проверяем только перевод ошибок в ответы."""

    def __init__(self, error: Exception | None = None) -> None:
        self._error = error
        self.unlinked = False

    async def describe(self, user: User) -> SubscriptionLinkResponse:
        if self._error is not None:
            raise self._error
        return SubscriptionLinkResponse(linked=False)

    async def link(
        self,
        user: User,
        subscription_link: str,
    ) -> SubscriptionLinkResponse:
        if self._error is not None:
            raise self._error
        return SubscriptionLinkResponse(
            linked=True,
            panel_username="anfisa",
        )

    async def unlink(self, user: User) -> None:
        self.unlinked = True


@pytest.fixture
def stub(app: FastAPI) -> Iterator[StubSubscriptionService]:
    service = StubSubscriptionService()
    app.dependency_overrides[get_subscription_service] = lambda: service
    yield service
    app.dependency_overrides.pop(get_subscription_service, None)


def use_error(app: FastAPI, error: Exception) -> None:
    app.dependency_overrides[get_subscription_service] = (
        lambda: StubSubscriptionService(error)
    )


def test_linking_returns_the_panel_username(
    client: TestClient,
    stub: StubSubscriptionService,
) -> None:
    response = client.post(
        LINK_PATH,
        json={"subscriptionLink": "https://panel.example/sub/abcd1234efgh"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "linked": True,
        "panelUsername": "anfisa",
        "subscription": None,
    }


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (
            SubscriptionLinkInvalidError("bad"),
            422,
            "invalid_subscription_link",
        ),
        (
            SubscriptionNotFoundError("missing"),
            404,
            "subscription_not_found",
        ),
        (
            SubscriptionAlreadyClaimedError("taken"),
            409,
            "subscription_already_claimed",
        ),
        (PanelUnavailableError("down"), 503, "panel_unavailable"),
    ],
)
def test_link_failures_reach_the_user_as_clear_codes(
    app: FastAPI,
    client: TestClient,
    error: Exception,
    expected_status: int,
    expected_code: str,
) -> None:
    use_error(app, error)

    response = client.post(
        LINK_PATH,
        json={"subscriptionLink": "whatever"},
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]["code"] == expected_code
    app.dependency_overrides.pop(get_subscription_service, None)


def test_unlink_returns_no_content(
    client: TestClient,
    stub: StubSubscriptionService,
) -> None:
    response = client.delete(LINK_PATH)

    assert response.status_code == 204
    assert stub.unlinked is True


def test_link_requires_a_token(anonymous_client: TestClient) -> None:
    response = anonymous_client.post(
        LINK_PATH,
        json={"subscriptionLink": "https://panel.example/sub/abcd1234efgh"},
    )

    assert response.status_code == 401


class LinkedSubscriptionService:
    """Аккаунт с привязанной подпиской: данные приходят из панели."""

    def __init__(self, subscription: SubscriptionResponse) -> None:
        self._subscription = subscription

    async def describe(self, user: User) -> SubscriptionLinkResponse:
        return SubscriptionLinkResponse(
            linked=True,
            panel_username="anfisa",
            subscription=self._subscription,
        )

    async def list_devices(self, user: User) -> list[DeviceResponse]:
        return [
            DeviceResponse(
                id="hwid-1",
                name="Galaxy S23",
                platform="Android 14",
                last_seen_at=None,
                created_at=datetime.now(UTC),
            )
        ]


def test_dashboard_shows_the_panel_subscription(
    app: FastAPI,
    client: TestClient,
) -> None:
    subscription = SubscriptionResponse(
        status=SubscriptionStatus.ACTIVE,
        plan_name="Подписка",
        days_left=12,
        expires_at=date.today() + timedelta(days=12),
        traffic_label="50 ГБ",
        devices_used=1,
        devices_limit=5,
        auto_renew_enabled=False,
        balance_rub=0,
    )
    app.dependency_overrides[get_subscription_service] = (
        lambda: LinkedSubscriptionService(subscription)
    )

    response = client.get("/api/v1/cabinet/dashboard")

    assert response.status_code == 200
    payload = response.json()
    # Демонстрационные "6 месяцев" и "Без лимита" сюда попасть не должны.
    assert payload["subscription"]["daysLeft"] == 12
    assert payload["subscription"]["trafficLabel"] == "50 ГБ"
    assert payload["subscription"]["devicesLimit"] == 5
    assert payload["profile"]["email"] == "anfisa@vpanfi.ru"

    app.dependency_overrides.pop(get_subscription_service, None)
