"""Тесты моста рефералки с ботом продаж: sync_bot и обработка bot-наград.

Отдельный файл от test_referral.py: у моста свои фиктивные объекты
(BotUser, BotPurchase, список клиентов бота), заводить их в общих
FakePanelGateway/FakeBedolagaGateway/FakeRewardStore означало бы
раздувать те подделки полями, которые нужны только здесь. База данных
не нужна и тут: вся логика проверяется хранилищем и обоими шлюзами в
памяти, как и в test_referral.py.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.integrations.bedolaga.client import (
    BedolagaUnavailableError,
    BedolagaUserNotFoundError,
    BotPurchase,
    BotUser,
)
from app.integrations.remnawave.client import (
    RemnawaveUserNotFoundError,
)
from app.models.billing import ReferralReward
from app.services.referral import ReferralService

INVITER_USERNAME = "Alyona_Tutina"
INVITER_BOT_ID = 42
INVITER_PANEL_ID = 500
INVITER_TELEGRAM_ID = 777000
FRIEND_BOT_ID = 99
FRIEND_TELEGRAM_ID = 555000


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "referral_enabled": True,
        "referral_bot_enabled": True,
        # Пустой токен выключил бы мост через is_bedolaga_configured:
        # тестам моста он всегда нужен, если тест не проверяет именно
        # выключение.
        "bedolaga_api_token": "test-bedolaga-token",
        "referral_friend_days": 15,
        "referral_inviter_days": 15,
        "referral_renewal_days": 10,
        "referral_renewal_min_gap_days": 20,
        "referral_monthly_cap": 5,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _panel_payload(
    *,
    user_id: int,
    username: str,
    status: str = "ACTIVE",
    tag: str | None = "PAID",
    telegram_id: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": user_id,
        "username": username,
        "status": status,
    }
    if tag is not None:
        payload["tag"] = tag
    if telegram_id is not None:
        payload["telegramId"] = telegram_id
    return payload


def _bot_user(
    *,
    user_id: int = FRIEND_BOT_ID,
    telegram_id: int | None = FRIEND_TELEGRAM_ID,
    referred_by_id: int | None = INVITER_BOT_ID,
    has_had_paid_subscription: bool = True,
) -> BotUser:
    return BotUser(
        id=user_id,
        telegram_id=telegram_id,
        referral_code=None,
        referred_by_id=referred_by_id,
        has_had_paid_subscription=has_had_paid_subscription,
    )


def _purchase(purchase_id: int, *, completed_at: datetime) -> BotPurchase:
    return BotPurchase(
        id=purchase_id, user_id=FRIEND_BOT_ID, completed_at=completed_at
    )


def _bot_reward(
    *,
    friend_key: str,
    friend_telegram_id: int = FRIEND_TELEGRAM_ID,
    bot_transaction_id: int | None,
    inviter_username: str = INVITER_USERNAME,
    inviter_panel_user_id: int = INVITER_PANEL_ID,
    inviter_telegram_id: int | None = None,
    friend_days: int = 15,
    inviter_days: int = 15,
    kind: str = "first",
    status: str = "granted",
    friend_granted_at: datetime | None = None,
    inviter_granted_at: datetime | None = None,
    attempts: int = 0,
    last_error: str | None = None,
    created_at: datetime | None = None,
) -> ReferralReward:
    """Собрать уже существующую bot-награду, минуя sync_bot.

    Нужна тестам, которые проверяют реакцию на уже заведённую запись
    (продление, повторный проход, обработку в process), а не сам её
    завод.
    """
    return ReferralReward(
        id=uuid4(),
        payment_id=None,
        source="bot",
        friend_email=friend_key,
        friend_telegram_id=friend_telegram_id,
        friend_panel_user_id=None,
        bot_transaction_id=bot_transaction_id,
        inviter_username=inviter_username,
        inviter_panel_user_id=inviter_panel_user_id,
        inviter_telegram_id=inviter_telegram_id,
        friend_days=friend_days,
        inviter_days=inviter_days,
        kind=kind,
        status=status,
        friend_granted_at=friend_granted_at,
        inviter_granted_at=inviter_granted_at,
        attempts=attempts,
        last_error=last_error,
        created_at=created_at or datetime.now(UTC),
    )


class FakeStore:
    """Хранилище наград в памяти для тестов моста.

    ``add`` подставляет id и created_at, которые в настоящей базе
    появляются только после flush/commit (server_default и клиентский
    default недоступны без сессии): без этого schedule(reward.id) и
    сравнение разрыва дат по created_at работали бы с пустыми полями.
    """

    def __init__(self) -> None:
        self.rewards: list[ReferralReward] = []
        self.save_calls = 0
        self.rollback_calls = 0
        # Одноразовый флаг: следующий save() бросит IntegrityError,
        # как бросила бы настоящая база на повторной вставке той же
        # транзакции бота.
        self.raise_integrity_on_next_save = False
        self._last_added: ReferralReward | None = None

    async def first_reward_for(self, email: str) -> ReferralReward | None:
        email_lower = email.lower()
        for reward in self.rewards:
            if (
                reward.friend_email.lower() == email_lower
                and reward.kind == "first"
                and reward.status in ("granted", "held")
            ):
                return reward
        return None

    async def renewal_exists(self, email: str) -> bool:
        email_lower = email.lower()
        return any(
            reward.friend_email.lower() == email_lower
            and reward.kind == "renewal"
            for reward in self.rewards
        )

    async def bot_reward_exists(self, transaction_id: int) -> bool:
        return any(
            reward.bot_transaction_id == transaction_id
            for reward in self.rewards
        )

    async def add(self, reward: ReferralReward) -> None:
        if reward.id is None:
            reward.id = uuid4()
        if reward.created_at is None:
            reward.created_at = datetime.now(UTC)
        self._last_added = reward
        self.rewards.append(reward)

    async def get(self, reward_id: UUID) -> ReferralReward | None:
        for reward in self.rewards:
            if reward.id == reward_id:
                return reward
        return None

    async def counted_in_last_days(
        self, inviter_username: str, days: int
    ) -> int:
        threshold = datetime.now(UTC) - timedelta(days=days)

        def _aware(moment: datetime) -> datetime:
            return moment if moment.tzinfo is not None else moment.replace(
                tzinfo=UTC
            )

        return sum(
            1
            for reward in self.rewards
            if reward.inviter_username == inviter_username
            and reward.inviter_days > 0
            and reward.status in ("pending", "granted", "failed")
            and _aware(reward.created_at) >= threshold
        )

    async def save(self) -> None:
        self.save_calls += 1
        if self.raise_integrity_on_next_save:
            self.raise_integrity_on_next_save = False
            if self._last_added is not None and self._last_added in (
                self.rewards
            ):
                self.rewards.remove(self._last_added)
            raise IntegrityError("duplicate", None, None)

    async def rollback(self) -> None:
        self.rollback_calls += 1

    async def refresh(self, reward: ReferralReward) -> None:
        return None


class FakePanel:
    """Поддельная панель для моста: считает вызовы, не ходит в сеть."""

    def __init__(
        self,
        *,
        by_telegram_id: dict[int, dict[str, Any]] | None = None,
        by_id: dict[int, dict[str, Any]] | None = None,
        fail_set_expiry_for: set[int] | None = None,
    ) -> None:
        self.by_telegram_id = by_telegram_id or {}
        self.by_id = by_id or {}
        self.fail_set_expiry_for = fail_set_expiry_for or set()
        self.entered = False
        self.get_user_by_telegram_id_calls: list[int] = []
        self.set_expiry_calls: list[int] = []

    async def __aenter__(self) -> "FakePanel":
        self.entered = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def get_user_by_telegram_id(
        self, telegram_id: int
    ) -> dict[str, Any]:
        self.get_user_by_telegram_id_calls.append(telegram_id)
        try:
            return self.by_telegram_id[telegram_id]
        except KeyError:
            raise RemnawaveUserNotFoundError(str(telegram_id)) from None

    async def get_user_by_id(self, user_id: int) -> dict[str, Any]:
        try:
            return self.by_id[user_id]
        except KeyError:
            raise RemnawaveUserNotFoundError(str(user_id)) from None

    async def set_expiry(
        self, user_id: int, expire_at: datetime, tag: str | None = None
    ) -> dict[str, Any]:
        self.set_expiry_calls.append(user_id)
        raw = dict(self.by_id.get(user_id, {}))
        raw["id"] = user_id
        raw["expireAt"] = expire_at.isoformat()
        self.by_id[user_id] = raw
        return raw


class FakeBedolaga:
    """Поддельный бот продаж для моста: считает вызовы, не ходит в сеть."""

    def __init__(
        self,
        *,
        users: list[BotUser] | None = None,
        users_by_id: dict[int, BotUser] | None = None,
        purchases_by_user: dict[int, list[BotPurchase]] | None = None,
        raise_on_purchases_for: set[int] | None = None,
        subscription_by_telegram_id: dict[int, int] | None = None,
        not_found_subscription_ids: set[int] | None = None,
        fail_extend_for: set[int] | None = None,
        page_size: int = 200,
    ) -> None:
        self.users = users or []
        self.users_by_id = users_by_id or {}
        self.purchases_by_user = purchases_by_user or {}
        self.raise_on_purchases_for = raise_on_purchases_for or set()
        self.subscription_by_telegram_id = subscription_by_telegram_id or {}
        self.not_found_subscription_ids = not_found_subscription_ids or set()
        self.fail_extend_for = fail_extend_for or set()
        self.page_size = page_size
        self.entered = False
        self.list_users_calls: list[tuple[int, int]] = []
        self.user_by_id_calls: list[int] = []
        self.purchases_calls: list[int] = []
        self.extend_calls: list[tuple[int, int]] = []

    async def __aenter__(self) -> "FakeBedolaga":
        self.entered = True
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def list_users(
        self, *, limit: int = 200, offset: int = 0
    ) -> tuple[list[BotUser], int]:
        self.list_users_calls.append((limit, offset))
        total = len(self.users)
        return list(self.users[offset : offset + limit]), total

    async def user_by_id(self, user_id: int) -> BotUser:
        self.user_by_id_calls.append(user_id)
        try:
            return self.users_by_id[user_id]
        except KeyError:
            raise BedolagaUserNotFoundError(str(user_id)) from None

    async def purchases(self, user_id: int) -> list[BotPurchase]:
        self.purchases_calls.append(user_id)
        if user_id in self.raise_on_purchases_for:
            raise BedolagaUnavailableError("бот продаж недоступен")
        return list(self.purchases_by_user.get(user_id, []))

    async def subscription_id_by_telegram_id(self, telegram_id: int) -> int:
        if telegram_id in self.not_found_subscription_ids:
            raise BedolagaUserNotFoundError(str(telegram_id))
        return self.subscription_by_telegram_id[telegram_id]

    async def extend(self, subscription_id: int, days: int) -> None:
        self.extend_calls.append((subscription_id, days))
        if subscription_id in self.fail_extend_for:
            raise BedolagaUnavailableError("бот продаж недоступен")


ServiceBundle = tuple[ReferralService, FakeStore, FakePanel, FakeBedolaga]


def _service(
    *,
    settings: Settings | None = None,
    store: FakeStore | None = None,
    panel: FakePanel | None = None,
    bedolaga: FakeBedolaga | None = None,
    on_terminal: Any = None,
    on_registered: Any = None,
) -> ServiceBundle:
    settings = settings or _settings()
    store = store if store is not None else FakeStore()
    panel = panel if panel is not None else FakePanel()
    bedolaga = bedolaga if bedolaga is not None else FakeBedolaga()
    service = ReferralService(
        settings,
        store,
        lambda: panel,
        lambda: bedolaga,
        on_terminal,
        on_registered,
    )
    return service, store, panel, bedolaga


def _default_bedolaga(
    *, purchase_ids: list[int] | None = None
) -> FakeBedolaga:
    """Бот продаж с одним валидным кандидатом и валидным пригласившим."""
    now = datetime.now(UTC)
    purchase_ids = purchase_ids if purchase_ids is not None else [1001]
    return FakeBedolaga(
        users=[_bot_user()],
        users_by_id={
            INVITER_BOT_ID: BotUser(
                id=INVITER_BOT_ID,
                telegram_id=INVITER_TELEGRAM_ID,
                referral_code="Alyona_Tutina",
                referred_by_id=None,
                has_had_paid_subscription=True,
            )
        },
        purchases_by_user={
            FRIEND_BOT_ID: [
                _purchase(pid, completed_at=now) for pid in purchase_ids
            ]
        },
        subscription_by_telegram_id={
            FRIEND_TELEGRAM_ID: 9001,
            INVITER_TELEGRAM_ID: 9002,
        },
    )


def _default_panel() -> FakePanel:
    return FakePanel(
        by_telegram_id={
            INVITER_TELEGRAM_ID: _panel_payload(
                user_id=INVITER_PANEL_ID,
                username=INVITER_USERNAME,
                telegram_id=INVITER_TELEGRAM_ID,
            )
        }
    )


# --- sync_bot: включение моста -------------------------------------------


async def test_sync_bot_does_nothing_when_referral_is_disabled() -> None:
    settings = _settings(referral_enabled=False)
    service, store, panel, bedolaga = _service(
        settings=settings, panel=_default_panel(), bedolaga=_default_bedolaga()
    )

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []
    assert bedolaga.entered is False
    assert panel.entered is False


async def test_sync_bot_does_nothing_when_bot_bridge_is_disabled() -> None:
    settings = _settings(referral_bot_enabled=False)
    service, store, panel, bedolaga = _service(
        settings=settings, panel=_default_panel(), bedolaga=_default_bedolaga()
    )

    created = await service.sync_bot()

    assert created == 0
    assert bedolaga.entered is False
    assert panel.entered is False


async def test_sync_bot_does_nothing_when_bedolaga_is_not_configured() -> None:
    settings = _settings(bedolaga_api_token=None)
    service, store, panel, bedolaga = _service(
        settings=settings, panel=_default_panel(), bedolaga=_default_bedolaga()
    )

    created = await service.sync_bot()

    assert created == 0
    assert bedolaga.entered is False
    assert panel.entered is False


# --- sync_bot: отбор кандидатов -------------------------------------------


async def test_sync_bot_skips_users_who_are_not_candidates() -> None:
    """Без referred_by_id, без оплаты или без телеграм-id: не кандидат."""
    users = [
        _bot_user(user_id=1, referred_by_id=None),
        _bot_user(user_id=2, has_had_paid_subscription=False),
        _bot_user(user_id=3, telegram_id=None),
    ]
    bedolaga = FakeBedolaga(users=users)
    service, store, panel, bedolaga = _service(bedolaga=bedolaga)

    created = await service.sync_bot()

    assert created == 0
    assert bedolaga.purchases_calls == []


async def test_sync_bot_skips_a_candidate_without_purchases() -> None:
    """Только пополнял баланс: пополнение наградой не является."""
    bedolaga = FakeBedolaga(
        users=[_bot_user()],
        purchases_by_user={FRIEND_BOT_ID: []},
    )
    service, store, panel, bedolaga = _service(bedolaga=bedolaga)

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []


# --- sync_bot: первая покупка ---------------------------------------------


async def test_sync_bot_creates_a_first_reward_with_every_field() -> None:
    service, store, panel, bedolaga = _service(
        panel=_default_panel(), bedolaga=_default_bedolaga(purchase_ids=[1001])
    )

    created = await service.sync_bot()

    assert created == 1
    assert len(store.rewards) == 1
    reward = store.rewards[0]
    assert reward.source == "bot"
    assert reward.payment_id is None
    assert reward.friend_email == f"tg:{FRIEND_TELEGRAM_ID}"
    assert reward.friend_telegram_id == FRIEND_TELEGRAM_ID
    assert reward.friend_panel_user_id is None
    assert reward.bot_transaction_id == 1001
    assert reward.kind == "first"
    assert reward.friend_days == 15
    assert reward.inviter_days == 15
    assert reward.inviter_username == INVITER_USERNAME
    assert reward.inviter_panel_user_id == INVITER_PANEL_ID
    assert reward.inviter_telegram_id == INVITER_TELEGRAM_ID
    assert reward.status == "pending"
    assert reward.attempts == 0
    assert reward.last_error is None
    assert reward.friend_granted_at is None
    assert reward.inviter_granted_at is None


async def test_second_sync_bot_pass_is_a_no_op() -> None:
    """Повторный обход того же клиента не заводит вторую первую награду."""
    service, store, panel, bedolaga = _service(
        panel=_default_panel(), bedolaga=_default_bedolaga()
    )
    first_pass = await service.sync_bot()
    assert first_pass == 1

    second_pass = await service.sync_bot()

    assert second_pass == 0
    assert len(store.rewards) == 1


# --- sync_bot: продление ---------------------------------------------------


async def test_renewal_purchase_before_the_gap_creates_nothing() -> None:
    now = datetime.now(UTC)
    first_created = now - timedelta(days=25)
    store = FakeStore()
    store.rewards.append(
        _bot_reward(
            friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
            bot_transaction_id=1001,
            status="granted",
            created_at=first_created,
        )
    )
    bedolaga = _default_bedolaga(purchase_ids=[])
    bedolaga.purchases_by_user[FRIEND_BOT_ID] = [
        _purchase(1001, completed_at=first_created),
        # Разрыв меньше настройки (20 дней): не продление.
        _purchase(1002, completed_at=first_created + timedelta(days=5)),
    ]
    service, store, panel, bedolaga = _service(
        store=store, panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 0
    assert not any(r.kind == "renewal" for r in store.rewards)


async def test_renewal_purchase_after_the_gap_creates_a_renewal() -> None:
    now = datetime.now(UTC)
    first_created = now - timedelta(days=25)
    store = FakeStore()
    store.rewards.append(
        _bot_reward(
            friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
            bot_transaction_id=1001,
            status="granted",
            created_at=first_created,
        )
    )
    bedolaga = _default_bedolaga(purchase_ids=[])
    bedolaga.purchases_by_user[FRIEND_BOT_ID] = [
        _purchase(1001, completed_at=first_created),
        _purchase(1002, completed_at=first_created + timedelta(days=5)),
        # 21 день после первой покупки: разрыв (20) выдержан.
        _purchase(1003, completed_at=first_created + timedelta(days=21)),
    ]
    service, store, panel, bedolaga = _service(
        store=store, panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 1
    renewal = next(r for r in store.rewards if r.kind == "renewal")
    assert renewal.bot_transaction_id == 1003
    assert renewal.friend_days == 0
    assert renewal.inviter_days == 10
    assert renewal.source == "bot"


async def test_a_third_purchase_does_not_create_a_second_renewal() -> None:
    now = datetime.now(UTC)
    first_created = now - timedelta(days=60)
    store = FakeStore()
    store.rewards.append(
        _bot_reward(
            friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
            bot_transaction_id=1001,
            status="granted",
            created_at=first_created,
        )
    )
    store.rewards.append(
        _bot_reward(
            friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
            bot_transaction_id=1002,
            kind="renewal",
            friend_days=0,
            status="granted",
            created_at=first_created + timedelta(days=25),
        )
    )
    bedolaga = _default_bedolaga(purchase_ids=[])
    bedolaga.purchases_by_user[FRIEND_BOT_ID] = [
        _purchase(1001, completed_at=first_created),
        _purchase(1002, completed_at=first_created + timedelta(days=25)),
        _purchase(1003, completed_at=first_created + timedelta(days=50)),
    ]
    service, store, panel, bedolaga = _service(
        store=store, panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 0
    assert sum(1 for r in store.rewards if r.kind == "renewal") == 1


async def test_pending_first_reward_blocks_renewal() -> None:
    """Первая покупка ещё не отработала (pending): продлять рано."""
    now = datetime.now(UTC)
    first_created = now - timedelta(days=60)
    store = FakeStore()
    store.rewards.append(
        _bot_reward(
            friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
            bot_transaction_id=1001,
            status="pending",
            created_at=first_created,
        )
    )
    bedolaga = _default_bedolaga(purchase_ids=[])
    bedolaga.purchases_by_user[FRIEND_BOT_ID] = [
        _purchase(1001, completed_at=first_created),
        _purchase(1002, completed_at=first_created + timedelta(days=30)),
    ]
    service, store, panel, bedolaga = _service(
        store=store, panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 0
    assert len(store.rewards) == 1


async def test_failed_first_reward_blocks_renewal() -> None:
    now = datetime.now(UTC)
    first_created = now - timedelta(days=60)
    store = FakeStore()
    store.rewards.append(
        _bot_reward(
            friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
            bot_transaction_id=1001,
            status="failed",
            created_at=first_created,
        )
    )
    bedolaga = _default_bedolaga(purchase_ids=[])
    bedolaga.purchases_by_user[FRIEND_BOT_ID] = [
        _purchase(1001, completed_at=first_created),
        _purchase(1002, completed_at=first_created + timedelta(days=30)),
    ]
    service, store, panel, bedolaga = _service(
        store=store, panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 0
    assert len(store.rewards) == 1


async def test_rejected_first_reward_blocks_renewal_forever() -> None:
    """Отклонённая первая покупка блокирует так же навсегда, как на сайте."""
    now = datetime.now(UTC)
    first_created = now - timedelta(days=60)
    store = FakeStore()
    store.rewards.append(
        _bot_reward(
            friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
            bot_transaction_id=1001,
            status="rejected",
            created_at=first_created,
        )
    )
    bedolaga = _default_bedolaga(purchase_ids=[])
    bedolaga.purchases_by_user[FRIEND_BOT_ID] = [
        _purchase(1001, completed_at=first_created),
        _purchase(1002, completed_at=first_created + timedelta(days=30)),
    ]
    service, store, panel, bedolaga = _service(
        store=store, panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 0
    assert len(store.rewards) == 1


async def test_one_reward_per_candidate_per_pass() -> None:
    """Один проход одного клиента не должен завести две записи разом."""
    service, store, panel, bedolaga = _service(
        panel=_default_panel(),
        bedolaga=_default_bedolaga(purchase_ids=[1001, 1002, 1003]),
    )

    created = await service.sync_bot()

    assert created == 1
    assert len(store.rewards) == 1


# --- sync_bot: приём пригласившего -----------------------------------------


async def test_inviter_without_telegram_id_creates_nothing() -> None:
    bedolaga = _default_bedolaga()
    bedolaga.users_by_id[INVITER_BOT_ID] = BotUser(
        id=INVITER_BOT_ID,
        telegram_id=None,
        referral_code=None,
        referred_by_id=None,
        has_had_paid_subscription=True,
    )
    service, store, panel, bedolaga = _service(
        panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []


async def test_inviter_missing_in_bedolaga_creates_nothing() -> None:
    bedolaga = _default_bedolaga()
    bedolaga.users_by_id = {}
    service, store, panel, bedolaga = _service(
        panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []


async def test_inviter_missing_in_panel_creates_nothing() -> None:
    service, store, panel, bedolaga = _service(
        panel=FakePanel(), bedolaga=_default_bedolaga()
    )

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []


async def test_inviter_with_trial_tag_creates_nothing() -> None:
    panel = FakePanel(
        by_telegram_id={
            INVITER_TELEGRAM_ID: _panel_payload(
                user_id=INVITER_PANEL_ID,
                username=INVITER_USERNAME,
                tag="TRIAL",
                telegram_id=INVITER_TELEGRAM_ID,
            )
        }
    )
    service, store, panel, bedolaga = _service(
        panel=panel, bedolaga=_default_bedolaga()
    )

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []


async def test_inviter_with_expired_status_creates_nothing() -> None:
    panel = FakePanel(
        by_telegram_id={
            INVITER_TELEGRAM_ID: _panel_payload(
                user_id=INVITER_PANEL_ID,
                username=INVITER_USERNAME,
                status="EXPIRED",
                telegram_id=INVITER_TELEGRAM_ID,
            )
        }
    )
    service, store, panel, bedolaga = _service(
        panel=panel, bedolaga=_default_bedolaga()
    )

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []


async def test_ooo_sinergiya_inviter_creates_nothing() -> None:
    panel = FakePanel(
        by_telegram_id={
            INVITER_TELEGRAM_ID: _panel_payload(
                user_id=INVITER_PANEL_ID,
                username="OOO_SINERGIYA_777",
                telegram_id=INVITER_TELEGRAM_ID,
            )
        }
    )
    service, store, panel, bedolaga = _service(
        panel=panel, bedolaga=_default_bedolaga()
    )

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []


async def test_svoi_inviter_gets_zero_days_and_never_a_renewal() -> None:
    """SVOI: другу бонус, пригласившему нуль дней, продления не бывает."""
    panel = FakePanel(
        by_telegram_id={
            INVITER_TELEGRAM_ID: _panel_payload(
                user_id=INVITER_PANEL_ID,
                username=INVITER_USERNAME,
                tag="SVOI",
                telegram_id=INVITER_TELEGRAM_ID,
            )
        }
    )
    service, store, panel, bedolaga = _service(
        panel=panel, bedolaga=_default_bedolaga(purchase_ids=[1001])
    )

    created = await service.sync_bot()

    assert created == 1
    first = store.rewards[0]
    assert first.kind == "first"
    assert first.inviter_days == 0
    assert first.friend_days == 15

    # Дальше как если бы process() уже выдал дни другу и закрыл награду:
    # только в granted её видит first_reward_for, и только оттуда может
    # начаться продление.
    first.status = "granted"

    bedolaga.purchases_by_user[FRIEND_BOT_ID] = [
        _purchase(1001, completed_at=first.created_at),
        _purchase(
            1002, completed_at=first.created_at + timedelta(days=30)
        ),
    ]

    second_pass = await service.sync_bot()

    assert second_pass == 0
    assert not any(r.kind == "renewal" for r in store.rewards)


async def test_self_invite_creates_nothing() -> None:
    """Пригласивший и друг совпали по телеграм-id: сам себя не наградит."""
    bedolaga = _default_bedolaga()
    bedolaga.users_by_id[INVITER_BOT_ID] = BotUser(
        id=INVITER_BOT_ID,
        telegram_id=FRIEND_TELEGRAM_ID,
        referral_code=None,
        referred_by_id=None,
        has_had_paid_subscription=True,
    )
    service, store, panel, bedolaga = _service(
        panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 0
    assert store.rewards == []


async def test_cap_reached_creates_a_held_reward() -> None:
    settings = _settings(referral_monthly_cap=1)
    store = FakeStore()
    # Уже одна засчитанная награда этому же пригласившему в этом же
    # окне: следующая должна упереться в потолок.
    store.rewards.append(
        _bot_reward(
            friend_key="tg:1",
            friend_telegram_id=1,
            bot_transaction_id=500,
            inviter_days=15,
            status="pending",
        )
    )
    service, store, panel, bedolaga = _service(
        settings=settings, store=store, panel=_default_panel(),
        bedolaga=_default_bedolaga(),
    )

    created = await service.sync_bot()

    assert created == 1
    new_reward = next(r for r in store.rewards if r.bot_transaction_id == 1001)
    assert new_reward.status == "held"


# --- sync_bot: устойчивость обхода -----------------------------------------


async def test_one_failing_candidate_does_not_stop_the_next() -> None:
    other_user = _bot_user(user_id=7, telegram_id=888)
    bedolaga = _default_bedolaga()
    bedolaga.users = [_bot_user(), other_user]
    bedolaga.raise_on_purchases_for = {FRIEND_BOT_ID}
    bedolaga.users_by_id[INVITER_BOT_ID] = BotUser(
        id=INVITER_BOT_ID,
        telegram_id=INVITER_TELEGRAM_ID,
        referral_code=None,
        referred_by_id=None,
        has_had_paid_subscription=True,
    )
    bedolaga.purchases_by_user[7] = [
        _purchase(2001, completed_at=datetime.now(UTC))
    ]
    service, store, panel, bedolaga = _service(
        panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 1
    assert store.rewards[0].friend_telegram_id == 888


async def test_pagination_walks_two_pages() -> None:
    """200 клиентов заполняют страницу целиком, второй кандидат на второй."""
    filler = [
        _bot_user(user_id=100 + i, telegram_id=None) for i in range(199)
    ]
    second_candidate = _bot_user(user_id=999, telegram_id=222)
    users = [_bot_user(), *filler, second_candidate]
    bedolaga = _default_bedolaga()
    bedolaga.users = users
    bedolaga.purchases_by_user[999] = [
        _purchase(3001, completed_at=datetime.now(UTC))
    ]
    bedolaga.users_by_id[INVITER_BOT_ID] = BotUser(
        id=INVITER_BOT_ID,
        telegram_id=INVITER_TELEGRAM_ID,
        referral_code=None,
        referred_by_id=None,
        has_had_paid_subscription=True,
    )
    service, store, panel, bedolaga = _service(
        panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 2
    assert bedolaga.list_users_calls == [(200, 0), (200, 200)]


async def test_schedule_is_called_once_with_the_new_reward_id() -> None:
    scheduled: list[UUID] = []
    service, store, panel, bedolaga = _service(
        panel=_default_panel(), bedolaga=_default_bedolaga()
    )

    created = await service.sync_bot(schedule=scheduled.append)

    assert created == 1
    assert scheduled == [store.rewards[0].id]


async def test_on_registered_is_called_and_its_failure_is_contained() -> None:
    calls: list[ReferralReward] = []

    def _on_registered(reward: ReferralReward) -> None:
        calls.append(reward)
        raise RuntimeError("телеграм недоступен")

    service, store, panel, bedolaga = _service(
        panel=_default_panel(),
        bedolaga=_default_bedolaga(),
        on_registered=_on_registered,
    )

    created = await service.sync_bot()

    assert created == 1
    assert len(calls) == 1
    assert calls[0] is store.rewards[0]


async def test_unique_violation_on_save_continues_the_walk() -> None:
    """Другой проход уже завёл эту же транзакцию: продолжаем со следующего."""
    other_user = _bot_user(user_id=7, telegram_id=888)
    bedolaga = _default_bedolaga()
    bedolaga.users = [_bot_user(), other_user]
    bedolaga.purchases_by_user[7] = [
        _purchase(2001, completed_at=datetime.now(UTC))
    ]
    bedolaga.users_by_id[INVITER_BOT_ID] = BotUser(
        id=INVITER_BOT_ID,
        telegram_id=INVITER_TELEGRAM_ID,
        referral_code=None,
        referred_by_id=None,
        has_had_paid_subscription=True,
    )
    store = FakeStore()
    store.raise_integrity_on_next_save = True
    service, store, panel, bedolaga = _service(
        store=store, panel=_default_panel(), bedolaga=bedolaga
    )

    created = await service.sync_bot()

    assert created == 1
    assert store.rollback_calls == 1
    assert len(store.rewards) == 1
    assert store.rewards[0].friend_telegram_id == 888


# --- process: друг и пригласивший из бота продаж ---------------------------


async def test_process_grants_a_bot_first_reward_through_the_bot() -> None:
    bedolaga = FakeBedolaga(
        subscription_by_telegram_id={
            FRIEND_TELEGRAM_ID: 9001,
            INVITER_TELEGRAM_ID: 9002,
        }
    )
    panel = FakePanel()
    service, store, panel, bedolaga = _service(panel=panel, bedolaga=bedolaga)
    reward = _bot_reward(
        friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
        bot_transaction_id=1001,
        inviter_telegram_id=INVITER_TELEGRAM_ID,
        status="pending",
    )

    await service.process(reward)

    assert reward.status == "granted"
    assert (9001, 15) in bedolaga.extend_calls
    assert (9002, 15) in bedolaga.extend_calls
    assert panel.set_expiry_calls == []
    assert reward.friend_granted_at is not None
    assert reward.inviter_granted_at is not None


async def test_process_does_not_re_extend_friend_after_inviter_fails() -> (
    None
):
    bedolaga = FakeBedolaga(
        subscription_by_telegram_id={
            FRIEND_TELEGRAM_ID: 9001,
            INVITER_TELEGRAM_ID: 9002,
        },
        fail_extend_for={9002},
    )
    service, store, panel, bedolaga = _service(bedolaga=bedolaga)
    reward = _bot_reward(
        friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
        bot_transaction_id=1001,
        inviter_telegram_id=INVITER_TELEGRAM_ID,
        status="pending",
    )

    await service.process(reward)

    assert reward.status == "pending"
    assert reward.friend_granted_at is not None
    friend_calls = [c for c in bedolaga.extend_calls if c[0] == 9001]
    assert len(friend_calls) == 1

    # Пригласивший теперь получает своё продление без сбоя.
    bedolaga.fail_extend_for.clear()
    await service.process(reward)

    assert reward.status == "granted"
    friend_calls = [c for c in bedolaga.extend_calls if c[0] == 9001]
    assert len(friend_calls) == 1


async def test_process_records_a_failed_attempt_for_a_missing_friend() -> (
    None
):
    bedolaga = FakeBedolaga(
        subscription_by_telegram_id={INVITER_TELEGRAM_ID: 9002},
        not_found_subscription_ids={FRIEND_TELEGRAM_ID},
    )
    service, store, panel, bedolaga = _service(bedolaga=bedolaga)
    reward = _bot_reward(
        friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
        bot_transaction_id=1001,
        inviter_telegram_id=INVITER_TELEGRAM_ID,
        status="pending",
    )

    await service.process(reward)

    assert reward.status == "pending"
    assert reward.attempts == 1
    assert reward.last_error is not None
    assert reward.friend_granted_at is None
    assert bedolaga.extend_calls == []


async def test_process_extends_only_the_inviter_for_a_bot_renewal() -> None:
    bedolaga = FakeBedolaga(
        subscription_by_telegram_id={
            FRIEND_TELEGRAM_ID: 9001,
            INVITER_TELEGRAM_ID: 9002,
        }
    )
    service, store, panel, bedolaga = _service(bedolaga=bedolaga)
    reward = _bot_reward(
        friend_key=f"tg:{FRIEND_TELEGRAM_ID}",
        bot_transaction_id=1003,
        inviter_telegram_id=INVITER_TELEGRAM_ID,
        kind="renewal",
        friend_days=0,
        inviter_days=10,
        status="pending",
    )

    await service.process(reward)

    assert reward.status == "granted"
    assert reward.friend_granted_at is None
    assert bedolaga.extend_calls == [(9002, 10)]
