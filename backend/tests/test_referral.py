"""Тесты ядра рефералки: кто получает награду и как она выдаётся.

База данных тестам не нужна: хранилище и оба шлюза здесь поддельные,
классы с теми же методами, которые считают вызовы. Это позволяет
проверить правила начисления без Postgres, которого у проекта нет для
тестов, и без сети.
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.integrations.bedolaga.client import (
    BedolagaUnavailableError,
    BedolagaUserNotFoundError,
)
from app.integrations.remnawave.client import (
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)
from app.models.billing import (
    Payment,
    PaymentPurpose,
    PaymentStatus,
    ReferralReward,
)
from app.services import referral as referral_module
from app.services.referral import (
    CODE_RE,
    ReferralService,
    normalize_code,
)

FRIEND_EMAIL = "friend@example.test"
INVITER_USERNAME = "Alyona_Tutina"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "referral_enabled": True,
        # Размер награды закреплён явно: тесты проверяют правила, а не
        # значение по умолчанию, которое владелец меняет по ситуации.
        "referral_friend_days": 30,
        "referral_inviter_days": 30,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _payment(
    *,
    referral_code: str | None = INVITER_USERNAME,
    email: str | None = FRIEND_EMAIL,
    payment_id: UUID | None = None,
) -> Payment:
    return Payment(
        id=payment_id or uuid4(),
        contact_email=email,
        amount_kopecks=30000,
        purpose=PaymentPurpose.SUBSCRIPTION,
        status=PaymentStatus.SUCCEEDED,
        description="тест",
        referral_code=referral_code,
    )


def _panel_payload(
    *,
    user_id: int,
    username: str,
    status: str = "ACTIVE",
    tag: str | None = "PAID",
    telegram_id: int | None = None,
    expires_at: date = date(2026, 9, 10),
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": user_id,
        "username": username,
        "status": status,
        "expireAt": datetime.combine(
            expires_at, datetime.min.time(), tzinfo=UTC
        ).isoformat(),
    }
    if tag is not None:
        payload["tag"] = tag
    if telegram_id is not None:
        payload["telegramId"] = telegram_id
    return payload


def _reward(
    *,
    payment_id: UUID | None = None,
    friend_email: str = FRIEND_EMAIL,
    friend_panel_user_id: int | None = 900,
    inviter_username: str = INVITER_USERNAME,
    inviter_panel_user_id: int = 500,
    inviter_telegram_id: int | None = None,
    friend_days: int = 30,
    inviter_days: int = 30,
    status: str = "pending",
    friend_granted_at: datetime | None = None,
    inviter_granted_at: datetime | None = None,
    attempts: int = 0,
    last_error: str | None = None,
    created_at: datetime | None = None,
) -> ReferralReward:
    return ReferralReward(
        id=uuid4(),
        payment_id=payment_id or uuid4(),
        friend_email=friend_email,
        friend_panel_user_id=friend_panel_user_id,
        inviter_username=inviter_username,
        inviter_panel_user_id=inviter_panel_user_id,
        inviter_telegram_id=inviter_telegram_id,
        friend_days=friend_days,
        inviter_days=inviter_days,
        status=status,
        friend_granted_at=friend_granted_at,
        inviter_granted_at=inviter_granted_at,
        attempts=attempts,
        last_error=last_error,
        created_at=created_at or datetime.now(UTC),
    )


class FakeRewardStore:
    """Хранилище наград в памяти."""

    def __init__(self) -> None:
        self.rewards: list[ReferralReward] = []
        self.paid_emails: set[str] = set()
        self.save_calls = 0
        self.rollback_calls = 0
        self.raise_on_add: Exception | None = None
        # Ровно на этом по счёту вызове save() бросить исключение
        # (однократно): проверяет сбой сохранения после удачной выдачи.
        self.fail_on_save_call: int | None = None
        # Хук перед возвратом из refresh(): тесты гонки подделывают тут
        # состояние, которое якобы успел записать другой обработчик.
        self.refresh_hook: Any = None
        # Порядок вызовов add()/save(): проверяет, что запись
        # коммитится раньше, чем register() вернёт её вызывающему.
        self.call_order: list[str] = []
        # Сбой самого чтения свежих наград для device_overlaps.
        self.raise_on_recent: Exception | None = None

    async def has_earlier_paid(self, email: str, payment_id: UUID) -> bool:
        return email.lower() in self.paid_emails

    async def reward_exists(self, payment_id: UUID, email: str) -> bool:
        email_lower = email.lower()
        return any(
            r.payment_id == payment_id or r.friend_email.lower() == email_lower
            for r in self.rewards
        )

    async def add(self, reward: ReferralReward) -> None:
        self.call_order.append("add")
        if self.raise_on_add is not None:
            raise self.raise_on_add
        self.rewards.append(reward)

    async def get(self, reward_id: UUID) -> ReferralReward | None:
        for r in self.rewards:
            if r.id == reward_id:
                return r
        return None

    async def counted_in_last_days(
        self, inviter_username: str, days: int
    ) -> int:
        # created_at заполняется server_default'ом в настоящей базе, а
        # у только что созданного в памяти ReferralReward (как в
        # register()) его ещё нет: тут это то же самое, что "прямо
        # сейчас", и такая запись обязана считаться.
        threshold = datetime.now(UTC) - timedelta(days=days)
        return sum(
            1
            for r in self.rewards
            if r.inviter_username == inviter_username
            and r.inviter_days > 0
            and r.status in ("pending", "granted", "failed")
            and (r.created_at is None or r.created_at >= threshold)
        )

    async def due_ids(self, limit: int) -> list[UUID]:
        return [r.id for r in self.rewards if r.status == "pending"][:limit]

    async def save(self) -> None:
        self.call_order.append("save")
        self.save_calls += 1
        if self.fail_on_save_call == self.save_calls:
            raise RuntimeError("сбой сохранения")

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def refresh(self, reward: ReferralReward) -> None:
        if self.refresh_hook is not None:
            self.refresh_hook(reward)

    async def recent(self, since: datetime) -> list[ReferralReward]:
        if self.raise_on_recent is not None:
            raise self.raise_on_recent
        return [
            r
            for r in self.rewards
            if r.created_at is not None
            and r.created_at >= since
            and r.status != "rejected"
            and r.friend_panel_user_id is not None
        ]


class FakePanelGateway:
    """Поддельная панель: считает вызовы, не ходит в сеть."""

    def __init__(
        self,
        *,
        by_username: dict[str, dict[str, Any]] | None = None,
        by_id: dict[int, dict[str, Any]] | None = None,
        fail_set_expiry_for: set[int] | None = None,
        raise_on_set_expiry: Exception | None = None,
        sleep_before_set_expiry: bool = False,
        devices_by_id: dict[int, list[dict[str, Any]]] | None = None,
        fail_list_devices_for: set[int] | None = None,
    ) -> None:
        self.by_username = by_username or {}
        self.by_id = by_id or {}
        self.fail_set_expiry_for = fail_set_expiry_for or set()
        self.raise_on_set_expiry = raise_on_set_expiry
        # Отдаёт управление циклу перед записью вызова: без этой точки
        # переключения два process() никогда бы не пересеклись даже
        # без замка, и гонку было бы нечем проверить.
        self.sleep_before_set_expiry = sleep_before_set_expiry
        self.set_expiry_calls: list[int] = []
        self.devices_by_id = devices_by_id or {}
        self.fail_list_devices_for = fail_list_devices_for or set()
        self.list_devices_calls: list[int] = []

    async def __aenter__(self) -> "FakePanelGateway":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        try:
            return self.by_username[username]
        except KeyError:
            raise RemnawaveUserNotFoundError(username) from None

    async def get_user_by_id(self, user_id: int) -> dict[str, Any]:
        try:
            return self.by_id[user_id]
        except KeyError:
            raise RemnawaveUserNotFoundError(str(user_id)) from None

    async def list_devices(self, user_id: int) -> list[dict[str, Any]]:
        self.list_devices_calls.append(user_id)
        if user_id in self.fail_list_devices_for:
            raise RemnawaveUnavailableError("панель недоступна")
        return self.devices_by_id.get(user_id, [])

    async def set_expiry(
        self, user_id: int, expire_at: datetime, tag: str | None = None
    ) -> dict[str, Any]:
        if self.sleep_before_set_expiry:
            await asyncio.sleep(0)
        self.set_expiry_calls.append(user_id)
        if user_id in self.fail_set_expiry_for or self.raise_on_set_expiry:
            raise self.raise_on_set_expiry or RemnawaveUnavailableError(
                "панель недоступна"
            )
        raw = dict(self.by_id.get(user_id, {}))
        raw["id"] = user_id
        raw["expireAt"] = expire_at.isoformat()
        self.by_id[user_id] = raw
        return raw


class FakeBedolagaGateway:
    """Поддельный бот продаж: считает вызовы, не ходит в сеть."""

    def __init__(
        self,
        *,
        subscription_by_telegram_id: dict[int, int] | None = None,
        not_found_ids: set[int] | None = None,
        fail_extend: bool = False,
    ) -> None:
        self.subscription_by_telegram_id = subscription_by_telegram_id or {}
        self.not_found_ids = not_found_ids or set()
        self.fail_extend = fail_extend
        self.extend_calls: list[tuple[int, int]] = []

    async def __aenter__(self) -> "FakeBedolagaGateway":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def subscription_id_by_telegram_id(self, telegram_id: int) -> int:
        if telegram_id in self.not_found_ids:
            raise BedolagaUserNotFoundError(str(telegram_id))
        return self.subscription_by_telegram_id[telegram_id]

    async def extend(self, subscription_id: int, days: int) -> None:
        self.extend_calls.append((subscription_id, days))
        if self.fail_extend:
            raise BedolagaUnavailableError("бот продаж недоступен")


ServiceBundle = tuple[
    ReferralService, FakeRewardStore, FakePanelGateway, FakeBedolagaGateway
]


def _service(
    *,
    settings: Settings | None = None,
    store: FakeRewardStore | None = None,
    panel: FakePanelGateway | None = None,
    bedolaga: FakeBedolagaGateway | None = None,
    on_terminal: Any = None,
) -> ServiceBundle:
    settings = settings or _settings()
    store = store if store is not None else FakeRewardStore()
    panel = panel if panel is not None else FakePanelGateway()
    bedolaga = bedolaga if bedolaga is not None else FakeBedolagaGateway()
    service = ReferralService(
        settings, store, lambda: panel, lambda: bedolaga, on_terminal
    )
    return service, store, panel, bedolaga


# --- normalize_code ---------------------------------------------------


def test_code_pattern_allows_letters_digits_and_a_few_symbols() -> None:
    assert CODE_RE.match("user_369990765.a-b")
    assert not CODE_RE.match("два слова")


def test_normalize_code_trims_surrounding_whitespace() -> None:
    assert normalize_code("  Alyona_Tutina  ") == "Alyona_Tutina"


def test_normalize_code_keeps_the_original_case() -> None:
    """Панель ищет учётку по точному имени: обрезать регистр нельзя."""
    assert normalize_code("Alyona_Tutina") == "Alyona_Tutina"


def test_normalize_code_rejects_unfitting_text() -> None:
    assert normalize_code("два слова") is None


def test_normalize_code_rejects_none_and_blank() -> None:
    assert normalize_code(None) is None
    assert normalize_code("   ") is None


# --- register: базовые отказы ------------------------------------------


async def test_disabled_program_returns_none() -> None:
    disabled = _settings(referral_enabled=False)
    service, store, _panel, _bedolaga = _service(settings=disabled)

    result = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert result is None
    assert store.rewards == []


async def test_missing_code_returns_none() -> None:
    service, *_ = _service()

    result = await service.register(
        payment=_payment(referral_code=None),
        friend_panel_user_id=900,
        friend_was_paid=False,
    )

    assert result is None


async def test_earlier_successful_payment_blocks_the_reward() -> None:
    """Друг оплачивал и раньше: это не первая покупка."""
    store = FakeRewardStore()
    store.paid_emails.add(FRIEND_EMAIL.lower())
    service, store, *_ = _service(store=store)

    result = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert result is None


async def test_friend_already_had_the_paid_tag_blocks_the_reward() -> None:
    service, store, *_ = _service()

    result = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=True
    )

    assert result is None
    assert store.rewards == []


async def test_repeated_register_for_the_same_payment_returns_none() -> None:
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME
            )
        }
    )
    service, store, _panel, _bedolaga = _service(panel=panel)
    payment = _payment()

    first = await service.register(
        payment=payment, friend_panel_user_id=900, friend_was_paid=False
    )
    second = await service.register(
        payment=payment, friend_panel_user_id=900, friend_was_paid=False
    )

    assert first is not None
    assert second is None
    assert len(store.rewards) == 1


# --- register: пригласивший -------------------------------------------


async def test_unknown_inviter_code_returns_none() -> None:
    service, store, *_ = _service()

    result = await service.register(
        payment=_payment(referral_code="nobody_here"),
        friend_panel_user_id=900,
        friend_was_paid=False,
    )

    assert result is None
    assert store.rewards == []


@pytest.mark.parametrize("tag", ["TRIAL", "UNPAID", None])
async def test_inviter_without_a_paid_tag_is_rejected(tag: str | None) -> None:
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME, tag=tag
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    result = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert result is None
    assert store.rewards == []


async def test_inactive_inviter_subscription_is_rejected() -> None:
    """Дни не могут лечь на мёртвую подписку."""
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME, status="EXPIRED"
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    result = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert result is None
    assert store.rewards == []


async def test_sinergiya_account_is_rejected_even_when_paid() -> None:
    code = "OOO_SINERGIYA_3"
    panel = FakePanelGateway(
        by_username={
            code: _panel_payload(
                user_id=500, username=code, tag="PAID", status="ACTIVE"
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    result = await service.register(
        payment=_payment(referral_code=code),
        friend_panel_user_id=900,
        friend_was_paid=False,
    )

    assert result is None
    assert store.rewards == []


async def test_sinergiya_check_is_case_insensitive() -> None:
    code = "ooo_sinergiya_lowercase"
    panel = FakePanelGateway(
        by_username={
            code: _panel_payload(
                user_id=500, username=code, tag="PAID", status="ACTIVE"
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    result = await service.register(
        payment=_payment(referral_code=code),
        friend_panel_user_id=900,
        friend_was_paid=False,
    )

    assert result is None


async def test_own_code_is_rejected_as_self_invite() -> None:
    """Совпадение id пригласившего и друга это приглашение самого себя."""
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=900, username=INVITER_USERNAME
            )
        },
        by_id={900: _panel_payload(user_id=900, username=INVITER_USERNAME)},
    )
    service, store, *_ = _service(panel=panel)

    result = await service.register(
        payment=_payment(),
        friend_panel_user_id=900,
        friend_was_paid=False,
    )

    assert result is None
    assert store.rewards == []


async def test_svoi_tag_rewards_friend_with_zero_inviter_days() -> None:
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME, tag="SVOI"
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    reward = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert reward is not None
    assert reward.inviter_days == 0
    assert reward.friend_days == 30
    assert reward.status == "pending"


async def test_paid_tag_grants_full_inviter_days() -> None:
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    reward = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert reward is not None
    assert reward.inviter_days == 30
    assert reward.inviter_panel_user_id == 500
    assert reward.status == "pending"


async def test_bot_inviter_keeps_the_telegram_id_on_the_reward() -> None:
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME, telegram_id=100500
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    reward = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert reward is not None
    assert reward.inviter_telegram_id == 100500


# --- register: потолок --------------------------------------------------


async def test_monthly_cap_reached_marks_the_reward_held() -> None:
    settings = _settings(referral_monthly_cap=1)
    store = FakeRewardStore()
    now = datetime.now(UTC)
    store.rewards.append(
        _reward(
            friend_email="earlier-friend@example.test",
            inviter_username=INVITER_USERNAME,
            inviter_granted_at=now,
        )
    )
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME
            )
        }
    )
    service, store, *_ = _service(settings=settings, store=store, panel=panel)

    reward = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert reward is not None
    assert reward.status == "held"
    assert reward.friend_days == 30


async def test_six_registrations_in_a_row_hold_the_sixth() -> None:
    """Без process() между вызовами шестая награда всё равно уходит в held.

    Старый granted_in_last_days считал только уже выданное
    (inviter_granted_at): шесть register() подряд без единого process()
    между ними видели бы там везде ноль, и потолок пробивала бы целая
    пачка одновременных оплат. counted_in_last_days считает заведённое
    (pending/granted/failed), и пятый вызов уже видит пять предыдущих.
    """
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    rewards = [
        await service.register(
            payment=_payment(email=f"friend{i}@example.test"),
            friend_panel_user_id=900 + i,
            friend_was_paid=False,
        )
        for i in range(6)
    ]

    assert all(reward is not None for reward in rewards)
    statuses = [reward.status for reward in rewards if reward is not None]
    assert statuses[:5] == ["pending"] * 5
    assert statuses[5] == "held"


async def test_svoi_inviter_ignores_the_monthly_cap() -> None:
    """Пригласившему без дней потолок ни к чему считать."""
    settings = _settings(referral_monthly_cap=0)
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME, tag="SVOI"
            )
        }
    )
    service, store, *_ = _service(settings=settings, panel=panel)

    reward = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert reward is not None
    assert reward.status == "pending"


# --- process: выдача другу и пригласившему -----------------------------


async def test_process_grants_friend_from_the_later_date() -> None:
    overdue = date.today() - timedelta(days=5)
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(
                user_id=900, username="friend_acc", expires_at=overdue
            ),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    service, store, panel, _bedolaga = _service(panel=panel)
    reward = _reward()

    await service.process(reward)

    assert reward.status == "granted"
    assert reward.friend_granted_at is not None
    friend_calls = [c for c in panel.set_expiry_calls if c == 900]
    assert friend_calls == [900]


async def test_process_extends_from_a_future_expiry_not_from_today() -> None:
    future = date.today() + timedelta(days=10)
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(
                user_id=900, username="friend_acc", expires_at=future
            ),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    service, store, panel, _bedolaga = _service(panel=panel)
    reward = _reward(friend_days=30)

    await service.process(reward)

    saved = panel.by_id[900]
    new_expiry = datetime.fromisoformat(saved["expireAt"]).date()
    assert new_expiry == future + timedelta(days=30)


async def test_site_inviter_is_granted_through_the_panel() -> None:
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    service, store, panel, bedolaga = _service(panel=panel)
    reward = _reward(inviter_telegram_id=None)

    await service.process(reward)

    assert reward.status == "granted"
    assert 500 in panel.set_expiry_calls
    assert bedolaga.extend_calls == []


async def test_bot_inviter_is_granted_through_bedolaga() -> None:
    panel = FakePanelGateway(
        by_id={900: _panel_payload(user_id=900, username="friend_acc")}
    )
    bedolaga = FakeBedolagaGateway(subscription_by_telegram_id={100500: 777})
    service, store, panel, bedolaga = _service(panel=panel, bedolaga=bedolaga)
    reward = _reward(inviter_telegram_id=100500)

    await service.process(reward)

    assert reward.status == "granted"
    assert bedolaga.extend_calls == [(777, 30)]
    assert 500 not in panel.set_expiry_calls


async def test_zero_inviter_days_grants_only_once_friend_is_done() -> None:
    panel = FakePanelGateway(
        by_id={900: _panel_payload(user_id=900, username="friend_acc")}
    )
    service, store, panel, bedolaga = _service(panel=panel)
    reward = _reward(inviter_days=0)

    await service.process(reward)

    assert reward.status == "granted"
    assert reward.inviter_granted_at is None
    assert bedolaga.extend_calls == []
    assert 500 not in panel.set_expiry_calls


# --- process: держатель потолка -----------------------------------------


async def test_held_reward_grants_only_the_friend() -> None:
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    service, store, panel, bedolaga = _service(panel=panel)
    reward = _reward(status="held")

    await service.process(reward)

    assert reward.status == "held"
    assert reward.friend_granted_at is not None
    assert reward.inviter_granted_at is None
    assert 500 not in panel.set_expiry_calls


async def test_releasing_a_held_reward_grants_only_what_is_missing() -> None:
    """После отметки другу снятие потолка не должно выдать дни второй раз."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    service, store, panel, bedolaga = _service(panel=panel)
    reward = _reward(status="held")
    await service.process(reward)
    assert reward.status == "held"

    reward.status = "pending"
    await service.process(reward)

    assert reward.status == "granted"
    friend_calls = [c for c in panel.set_expiry_calls if c == 900]
    assert friend_calls == [900]
    assert 500 in panel.set_expiry_calls


# --- process: защита от двойной выдачи ----------------------------------


async def test_inviter_failure_does_not_regrant_the_friend() -> None:
    panel = FakePanelGateway(
        by_id={900: _panel_payload(user_id=900, username="friend_acc")}
    )
    bedolaga = FakeBedolagaGateway(
        subscription_by_telegram_id={100500: 777}, fail_extend=True
    )
    service, store, panel, bedolaga = _service(panel=panel, bedolaga=bedolaga)
    reward = _reward(inviter_telegram_id=100500)

    await service.process(reward)
    assert reward.status == "pending"
    assert reward.friend_granted_at is not None
    assert reward.attempts == 1
    assert reward.last_error

    await service.process(reward)

    assert reward.status == "pending"
    assert reward.attempts == 2
    friend_calls = [c for c in panel.set_expiry_calls if c == 900]
    assert friend_calls == [900]


async def test_ten_failures_mark_the_reward_failed() -> None:
    panel = FakePanelGateway(
        by_id={900: _panel_payload(user_id=900, username="friend_acc")}
    )
    bedolaga = FakeBedolagaGateway(
        subscription_by_telegram_id={100500: 777}, fail_extend=True
    )
    service, store, panel, bedolaga = _service(panel=panel, bedolaga=bedolaga)
    reward = _reward(inviter_telegram_id=100500)

    for _ in range(10):
        await service.process(reward)

    assert reward.attempts == 10
    assert reward.status == "failed"


async def test_bot_inviter_only_on_trial_does_not_touch_the_panel() -> None:
    """Триал в боте нельзя продлевать: бот перепишет срок своим."""
    panel = FakePanelGateway(
        by_id={900: _panel_payload(user_id=900, username="friend_acc")}
    )
    bedolaga = FakeBedolagaGateway(not_found_ids={100500})
    service, store, panel, bedolaga = _service(panel=panel, bedolaga=bedolaga)
    reward = _reward(inviter_telegram_id=100500)

    await service.process(reward)

    assert reward.status == "pending"
    assert reward.attempts == 1
    assert reward.last_error
    assert 500 not in panel.set_expiry_calls
    assert bedolaga.extend_calls == []


async def test_missing_friend_panel_user_id_is_recorded_as_an_error() -> None:
    service, store, panel, bedolaga = _service()
    reward = _reward(friend_panel_user_id=None)

    await service.process(reward)

    assert reward.status == "pending"
    assert reward.friend_granted_at is None
    assert reward.attempts == 1
    assert reward.last_error
    assert panel.set_expiry_calls == []


# --- process: сбой сохранения после удачной выдачи ----------------------


async def test_friend_grant_survives_but_save_fails_once() -> None:
    """save() падает сразу после выдачи другу: повтор не должен продлить."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    store = FakeRewardStore()
    store.fail_on_save_call = 1
    service, store, panel, bedolaga = _service(store=store, panel=panel)
    reward = _reward()

    await service.process(reward)

    assert reward.status == "failed"
    assert reward.friend_granted_at is not None
    assert reward.last_error is not None
    assert "нужна проверка вручную" in reward.last_error
    assert "friend" in reward.last_error
    assert panel.set_expiry_calls.count(900) == 1

    await service.process(reward)

    assert panel.set_expiry_calls.count(900) == 1
    assert 500 not in panel.set_expiry_calls
    assert bedolaga.extend_calls == []


async def test_inviter_grant_survives_but_save_fails_once() -> None:
    """save() падает сразу после выдачи пригласившему: повтор не продлит."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    store = FakeRewardStore()
    store.fail_on_save_call = 2
    service, store, panel, bedolaga = _service(store=store, panel=panel)
    reward = _reward()

    await service.process(reward)

    assert reward.status == "failed"
    assert reward.friend_granted_at is not None
    assert reward.inviter_granted_at is not None
    assert reward.last_error is not None
    assert "нужна проверка вручную" in reward.last_error
    assert "inviter" in reward.last_error
    assert panel.set_expiry_calls.count(900) == 1
    assert panel.set_expiry_calls.count(500) == 1

    await service.process(reward)

    assert panel.set_expiry_calls.count(900) == 1
    assert panel.set_expiry_calls.count(500) == 1
    assert bedolaga.extend_calls == []


# --- process: одновременная обработка ------------------------------------


async def test_concurrent_process_grants_each_side_exactly_once() -> None:
    """Вебхук и фон дёргают process на одну и ту же запись сразу же."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        },
        sleep_before_set_expiry=True,
    )
    service, store, panel, bedolaga = _service(panel=panel)
    reward = _reward()

    await asyncio.gather(service.process(reward), service.process(reward))

    assert reward.status == "granted"
    assert panel.set_expiry_calls.count(900) == 1
    assert panel.set_expiry_calls.count(500) == 1


async def test_refresh_seeing_another_workers_grant_skips_the_friend() -> None:
    """refresh перечитал: другой обработчик уже выдал дни другу."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    store = FakeRewardStore()
    store.refresh_hook = lambda r: setattr(
        r, "friend_granted_at", datetime.now(UTC)
    )
    service, store, panel, bedolaga = _service(store=store, panel=panel)
    reward = _reward()

    await service.process(reward)

    assert reward.status == "granted"
    assert 900 not in panel.set_expiry_calls
    assert 500 in panel.set_expiry_calls


async def test_lock_registry_drops_entries_for_terminal_rewards() -> None:
    """granted/failed награды не должны копиться в реестре замков."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    service, store, panel, bedolaga = _service(panel=panel)
    granted_reward = _reward()
    await service.process(granted_reward)
    assert granted_reward.status == "granted"

    panel_for_failing = FakePanelGateway(
        by_id={900: _panel_payload(user_id=900, username="friend_acc")}
    )
    bedolaga_failing = FakeBedolagaGateway(
        subscription_by_telegram_id={100500: 777}, fail_extend=True
    )
    service_failed, store_failed, _panel2, _bedolaga2 = _service(
        panel=panel_for_failing, bedolaga=bedolaga_failing
    )
    failing_reward = _reward(inviter_telegram_id=100500)
    for _ in range(referral_module._MAX_ATTEMPTS):
        await service_failed.process(failing_reward)
    assert failing_reward.status == "failed"

    assert granted_reward.id not in referral_module._LOCKS
    assert failing_reward.id not in referral_module._LOCKS


# --- process: итоговое уведомление (on_terminal) ------------------------


async def test_on_terminal_fires_once_when_the_reward_is_granted() -> None:
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    seen: list[ReferralReward] = []
    service, store, panel, bedolaga = _service(
        panel=panel, on_terminal=seen.append
    )
    reward = _reward()

    await service.process(reward)

    assert reward.status == "granted"
    assert len(seen) == 1
    assert seen[0] is reward


async def test_on_terminal_fires_once_after_ten_failures() -> None:
    panel = FakePanelGateway(
        by_id={900: _panel_payload(user_id=900, username="friend_acc")}
    )
    bedolaga = FakeBedolagaGateway(
        subscription_by_telegram_id={100500: 777}, fail_extend=True
    )
    seen: list[ReferralReward] = []
    service, store, panel, bedolaga = _service(
        panel=panel, bedolaga=bedolaga, on_terminal=seen.append
    )
    reward = _reward(inviter_telegram_id=100500)

    for _ in range(referral_module._MAX_ATTEMPTS):
        await service.process(reward)

    assert reward.status == "failed"
    assert len(seen) == 1


async def test_on_terminal_fires_once_after_save_fails_post_grant() -> None:
    """save() падает после выдачи: это тоже переход в failed, а не ошибка."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    store = FakeRewardStore()
    store.fail_on_save_call = 1
    seen: list[ReferralReward] = []
    service, store, panel, bedolaga = _service(
        store=store, panel=panel, on_terminal=seen.append
    )
    reward = _reward()

    await service.process(reward)

    assert reward.status == "failed"
    assert len(seen) == 1


async def test_on_terminal_does_not_fire_again_on_a_second_process() -> None:
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    seen: list[ReferralReward] = []
    service, store, panel, bedolaga = _service(
        panel=panel, on_terminal=seen.append
    )
    reward = _reward()

    await service.process(reward)
    assert reward.status == "granted"
    await service.process(reward)

    assert len(seen) == 1


async def test_on_terminal_exception_does_not_affect_the_status() -> None:
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )

    def broken_callback(_reward: ReferralReward) -> None:
        raise RuntimeError("телеграм недоступен")

    service, store, panel, bedolaga = _service(
        panel=panel, on_terminal=broken_callback
    )
    reward = _reward()

    await service.process(reward)  # не должно бросить исключение

    assert reward.status == "granted"


async def test_on_terminal_does_not_fire_while_held() -> None:
    """held это не терминальный статус: уведомление тут ещё не к месту."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    seen: list[ReferralReward] = []
    service, store, panel, bedolaga = _service(
        panel=panel, on_terminal=seen.append
    )
    reward = _reward(status="held")

    await service.process(reward)

    assert reward.status == "held"
    assert seen == []


# --- process_by_id ---------------------------------------------------------


async def test_process_by_id_processes_the_matching_reward() -> None:
    """Фоновая задача знает только id: process_by_id находит запись сама."""
    panel = FakePanelGateway(
        by_id={
            900: _panel_payload(user_id=900, username="friend_acc"),
            500: _panel_payload(user_id=500, username=INVITER_USERNAME),
        }
    )
    store = FakeRewardStore()
    reward = _reward(friend_panel_user_id=900)
    store.rewards.append(reward)
    service, store, panel, _bedolaga = _service(store=store, panel=panel)

    await service.process_by_id(reward.id)

    assert reward.status == "granted"
    assert 900 in panel.set_expiry_calls


async def test_process_by_id_warns_and_does_nothing_when_missing() -> None:
    """Награда пропала между постановкой задачи и её запуском."""
    service, store, panel, _bedolaga = _service()

    await service.process_by_id(uuid4())  # не должно бросить исключение

    assert panel.set_expiry_calls == []


# --- устойчивость к неожиданным сбоям ------------------------------------


async def test_register_never_raises_even_on_a_broken_store() -> None:
    store = FakeRewardStore()
    store.raise_on_add = RuntimeError("база недоступна")
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME
            )
        }
    )
    service, store, *_ = _service(store=store, panel=panel)

    result = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert result is None


async def test_process_never_raises_on_a_broken_store() -> None:
    """Другу выдано, а сохранить это не удалось: награда уходит в failed.

    Повтор с мёртвым хранилищем не должен продлить другу второй раз:
    единственный безопасный выход тут "сдаться" и подождать человека.
    """

    class BrokenStore(FakeRewardStore):
        async def save(self) -> None:
            raise RuntimeError("база недоступна")

    panel = FakePanelGateway(
        by_id={900: _panel_payload(user_id=900, username="friend_acc")}
    )
    service, store, panel, _bedolaga = _service(
        store=BrokenStore(), panel=panel
    )
    reward = _reward()

    await service.process(reward)  # не должно бросить исключение

    assert reward.status == "failed"
    assert reward.friend_granted_at is not None
    assert reward.last_error is not None
    assert "нужна проверка вручную" in reward.last_error
    assert "friend" in reward.last_error

    friend_calls_before = list(panel.set_expiry_calls)
    await service.process(reward)

    assert panel.set_expiry_calls == friend_calls_before


async def test_record_failure_survives_a_broken_store() -> None:
    """Сама попытка не сохранилась, но process всё равно не падает."""

    class BrokenStore(FakeRewardStore):
        async def save(self) -> None:
            raise RuntimeError("база недоступна")

    service, store, panel, _bedolaga = _service(store=BrokenStore())
    reward = _reward(friend_panel_user_id=None)

    await service.process(reward)  # не должно бросить исключение

    assert reward.attempts == 1
    assert reward.last_error is not None


async def test_register_rolls_back_the_session_after_a_broken_add() -> None:
    """Сбой в register не должен оставить сессию мёртвой для соседей.

    Незакоммиченная ошибка внутри одной сессии портит любое следующее
    действие в ней PendingRollbackError, а обработка одной награды
    делает несколько запросов подряд (другу, потом пригласившему).
    """
    store = FakeRewardStore()
    store.raise_on_add = RuntimeError("база недоступна")
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME
            )
        }
    )
    service, store, *_ = _service(store=store, panel=panel)

    await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert store.rollback_calls == 1


# --- register: коммит награды ------------------------------------------


async def test_register_commits_the_reward_before_returning() -> None:
    """Фоновая задача открывает свою сессию сразу после register.

    Если запись ещё не закоммичена, эта свежая сессия её не увидит:
    ``add`` обязан завершиться сохранением, а не просто добавлением
    в память сессии.
    """
    panel = FakePanelGateway(
        by_username={
            INVITER_USERNAME: _panel_payload(
                user_id=500, username=INVITER_USERNAME
            )
        }
    )
    service, store, *_ = _service(panel=panel)

    reward = await service.register(
        payment=_payment(), friend_panel_user_id=900, friend_was_paid=False
    )

    assert reward is not None
    assert store.call_order == ["add", "save"]
    assert store.save_calls == 1


# --- device_overlaps ---------------------------------------------------


async def test_device_overlaps_finds_a_shared_hwid() -> None:
    reward = _reward(friend_panel_user_id=900, inviter_panel_user_id=500)
    store = FakeRewardStore()
    store.rewards.append(reward)
    panel = FakePanelGateway(
        devices_by_id={
            900: [{"hwid": "aaa"}, {"hwid": "bbb"}],
            500: [{"hwid": "bbb"}, {"hwid": "ccc"}],
        }
    )
    service, *_ = _service(store=store, panel=panel)

    hits = await service.device_overlaps(datetime.now(UTC) - timedelta(days=1))

    assert hits == [(reward, 1)]


async def test_device_overlaps_finds_nothing_without_shared_devices() -> None:
    reward = _reward(friend_panel_user_id=900, inviter_panel_user_id=500)
    store = FakeRewardStore()
    store.rewards.append(reward)
    panel = FakePanelGateway(
        devices_by_id={
            900: [{"hwid": "aaa"}],
            500: [{"hwid": "ccc"}],
        }
    )
    service, *_ = _service(store=store, panel=panel)

    hits = await service.device_overlaps(datetime.now(UTC) - timedelta(days=1))

    assert hits == []


async def test_device_overlaps_ignores_empty_and_missing_hwid() -> None:
    """Пустая строка и отсутствующий hwid не должны считаться совпадением."""
    reward = _reward(friend_panel_user_id=900, inviter_panel_user_id=500)
    store = FakeRewardStore()
    store.rewards.append(reward)
    panel = FakePanelGateway(
        devices_by_id={
            900: [{"hwid": ""}, {"platform": "ios"}],
            500: [{"hwid": ""}, {"platform": "ios"}],
        }
    )
    service, *_ = _service(store=store, panel=panel)

    hits = await service.device_overlaps(datetime.now(UTC) - timedelta(days=1))

    assert hits == []


async def test_device_overlaps_skips_a_reward_when_the_panel_fails() -> None:
    """Сбой панели по одной награде не должен ронять весь обход."""
    broken = _reward(
        payment_id=uuid4(), friend_panel_user_id=901, inviter_panel_user_id=500
    )
    ok = _reward(
        payment_id=uuid4(), friend_panel_user_id=902, inviter_panel_user_id=501
    )
    store = FakeRewardStore()
    store.rewards.extend([broken, ok])
    panel = FakePanelGateway(
        devices_by_id={
            902: [{"hwid": "zzz"}],
            501: [{"hwid": "zzz"}],
        },
        fail_list_devices_for={901},
    )
    service, *_ = _service(store=store, panel=panel)

    hits = await service.device_overlaps(datetime.now(UTC) - timedelta(days=1))

    assert hits == [(ok, 1)]


async def test_device_overlaps_never_raises_when_recent_fails() -> None:
    store = FakeRewardStore()
    store.raise_on_recent = RuntimeError("база недоступна")
    service, *_ = _service(store=store)

    hits = await service.device_overlaps(datetime.now(UTC) - timedelta(days=1))

    assert hits == []


async def test_device_overlaps_fetches_the_shared_inviter_once() -> None:
    """Тот же пригласивший в двух наградах не должен спросить панель дважды."""
    first = _reward(
        payment_id=uuid4(),
        friend_email="one@example.test",
        friend_panel_user_id=901,
        inviter_panel_user_id=500,
    )
    second = _reward(
        payment_id=uuid4(),
        friend_email="two@example.test",
        friend_panel_user_id=902,
        inviter_panel_user_id=500,
    )
    store = FakeRewardStore()
    store.rewards.extend([first, second])
    panel = FakePanelGateway(
        devices_by_id={
            901: [{"hwid": "aaa"}],
            902: [{"hwid": "bbb"}],
            500: [{"hwid": "ccc"}],
        }
    )
    service, *_ = _service(store=store, panel=panel)

    hits = await service.device_overlaps(datetime.now(UTC) - timedelta(days=1))

    assert hits == []
    assert panel.list_devices_calls.count(500) == 1
