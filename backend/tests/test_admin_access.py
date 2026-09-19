"""Административный раздел закрыт для обычного пользователя.

Флаг is_admin существовал в модели и попадал в токен, но его никто не
проверял: раздел был доступен любому вошедшему.

Награды за приглашение (release/reject) проверяются здесь же, поддельным
хранилищем в памяти: у проекта нет тестовой базы, и SqlRewardStore
проверять было бы нечем.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_admin_service,
    get_current_user,
    get_referral_scheduler,
    get_reward_store,
)
from app.models.billing import ReferralReward
from app.schemas.admin import AdminOverviewResponse
from tests.conftest import build_user

ADMIN_ROUTES = [
    ("get", "/api/v1/admin/overview", None),
    ("get", "/api/v1/admin/users", None),
    ("get", "/api/v1/admin/referral-rewards", None),
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
    (
        "/api/v1/admin/referral-rewards/"
        "11111111-2222-3333-4444-555555555555/release",
        {},
    ),
    (
        "/api/v1/admin/referral-rewards/"
        "11111111-2222-3333-4444-555555555555/reject",
        {},
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


# --- release/reject наград за приглашение -------------------------------


def _reward(*, status: str = "held") -> ReferralReward:
    return ReferralReward(
        id=uuid4(),
        payment_id=uuid4(),
        friend_email="friend@example.com",
        friend_panel_user_id=900,
        inviter_username="Alyona_Tutina",
        inviter_panel_user_id=500,
        friend_days=30,
        inviter_days=30,
        status=status,
        created_at=datetime.now(UTC),
    )


class FakeAdminRewardStore:
    """Хранилище наград в памяти для маршрутов release/reject/list."""

    def __init__(self, rewards: list[ReferralReward] | None = None) -> None:
        self.rewards: dict[UUID, ReferralReward] = {
            reward.id: reward for reward in (rewards or [])
        }
        self.save_calls = 0

    async def get(self, reward_id: UUID) -> ReferralReward | None:
        return self.rewards.get(reward_id)

    async def save(self) -> None:
        self.save_calls += 1

    async def list_recent(
        self, status: str | None, limit: int
    ) -> list[ReferralReward]:
        items = list(self.rewards.values())
        if status is not None:
            items = [item for item in items if item.status == status]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[:limit]


def _clear_overrides(app: FastAPI) -> None:
    for dependency in (
        get_current_user,
        get_reward_store,
        get_referral_scheduler,
    ):
        app.dependency_overrides.pop(dependency, None)


def test_release_unknown_reward_is_not_found(app: FastAPI) -> None:
    app.dependency_overrides[get_current_user] = build_admin
    app.dependency_overrides[get_reward_store] = lambda: FakeAdminRewardStore()

    with TestClient(app) as admin_client:
        response = admin_client.post(
            f"/api/v1/admin/referral-rewards/{uuid4()}/release"
        )

    assert response.status_code == 404
    _clear_overrides(app)


def test_release_from_held_moves_to_pending_and_schedules_once(
    app: FastAPI,
) -> None:
    reward = _reward(status="held")
    store = FakeAdminRewardStore([reward])
    scheduled: list[UUID] = []

    app.dependency_overrides[get_current_user] = build_admin
    app.dependency_overrides[get_reward_store] = lambda: store
    app.dependency_overrides[get_referral_scheduler] = (
        lambda: scheduled.append
    )

    with TestClient(app) as admin_client:
        response = admin_client.post(
            f"/api/v1/admin/referral-rewards/{reward.id}/release"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert store.rewards[reward.id].status == "pending"
    assert store.save_calls == 1
    assert scheduled == [reward.id]
    _clear_overrides(app)


def test_release_from_granted_is_a_conflict(app: FastAPI) -> None:
    reward = _reward(status="granted")
    store = FakeAdminRewardStore([reward])

    app.dependency_overrides[get_current_user] = build_admin
    app.dependency_overrides[get_reward_store] = lambda: store

    with TestClient(app) as admin_client:
        response = admin_client.post(
            f"/api/v1/admin/referral-rewards/{reward.id}/release"
        )

    assert response.status_code == 409
    assert store.rewards[reward.id].status == "granted"
    _clear_overrides(app)


def test_reject_from_pending_is_rejected(app: FastAPI) -> None:
    reward = _reward(status="pending")
    store = FakeAdminRewardStore([reward])

    app.dependency_overrides[get_current_user] = build_admin
    app.dependency_overrides[get_reward_store] = lambda: store

    with TestClient(app) as admin_client:
        response = admin_client.post(
            f"/api/v1/admin/referral-rewards/{reward.id}/reject"
        )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert store.rewards[reward.id].status == "rejected"
    _clear_overrides(app)


def test_reject_from_granted_is_a_conflict(app: FastAPI) -> None:
    reward = _reward(status="granted")
    store = FakeAdminRewardStore([reward])

    app.dependency_overrides[get_current_user] = build_admin
    app.dependency_overrides[get_reward_store] = lambda: store

    with TestClient(app) as admin_client:
        response = admin_client.post(
            f"/api/v1/admin/referral-rewards/{reward.id}/reject"
        )

    assert response.status_code == 409
    assert store.rewards[reward.id].status == "granted"
    _clear_overrides(app)


def test_list_referral_rewards_filters_by_status(app: FastAPI) -> None:
    held = _reward(status="held")
    granted = _reward(status="granted")
    store = FakeAdminRewardStore([held, granted])

    app.dependency_overrides[get_current_user] = build_admin
    app.dependency_overrides[get_reward_store] = lambda: store

    with TestClient(app) as admin_client:
        response = admin_client.get(
            "/api/v1/admin/referral-rewards", params={"status": "held"}
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(held.id)
    assert body[0]["status"] == "held"
    assert body[0]["friendEmail"] == held.friend_email
    _clear_overrides(app)


def test_list_referral_rewards_without_status_returns_everything(
    app: FastAPI,
) -> None:
    held = _reward(status="held")
    granted = _reward(status="granted")
    store = FakeAdminRewardStore([held, granted])

    app.dependency_overrides[get_current_user] = build_admin
    app.dependency_overrides[get_reward_store] = lambda: store

    with TestClient(app) as admin_client:
        response = admin_client.get("/api/v1/admin/referral-rewards")

    assert response.status_code == 200
    assert {row["id"] for row in response.json()} == {
        str(held.id),
        str(granted.id),
    }
    _clear_overrides(app)
