"""Ошибки привязки доходят до пользователя понятным кодом."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_subscription_service
from app.models.user import User
from app.schemas.cabinet import SubscriptionLinkResponse
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
