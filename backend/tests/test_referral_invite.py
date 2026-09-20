"""Тесты резолвера ссылки на бота продаж для друга по коду приглашения.

Как и у ядра рефералки, здесь нет ни базы, ни сети: панель и бот
продаж поддельные, а время для проверки TTL и очереди вытеснения
подаётся своими часами, а не настоящим ``time.monotonic``.
"""

from typing import Any

from app.core.config import Settings
from app.integrations.bedolaga.client import (
    BedolagaUserNotFoundError,
    BotUser,
)
from app.integrations.remnawave.client import RemnawaveUserNotFoundError
from app.services.referral_invite import InviteResolver

INVITER_USERNAME = "Alyona_Tutina"
INVITER_TELEGRAM_ID = 555000111
BOT_USERNAME = "VPaNfi_bot"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "referral_enabled": True,
        "referral_bot_enabled": True,
        "bedolaga_api_token": "test-token",
        "telegram_sales_bot_username": BOT_USERNAME,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _panel_payload(
    *,
    username: str = INVITER_USERNAME,
    status: str = "ACTIVE",
    telegram_id: int | None = INVITER_TELEGRAM_ID,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"username": username, "status": status}
    if telegram_id is not None:
        payload["telegramId"] = telegram_id
    return payload


class _CountingFactory:
    """Считает, сколько раз резолвер попросил шлюз, не открывая сеть."""

    def __init__(self, gateway: Any) -> None:
        self._gateway = gateway
        self.calls = 0

    def __call__(self, settings: Settings) -> Any:
        self.calls += 1
        return self._gateway


class FakePanel:
    def __init__(self, users: dict[str, dict[str, Any]] | None = None) -> None:
        self.users = users or {}
        self.calls: list[str] = []

    async def __aenter__(self) -> "FakePanel":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        self.calls.append(username)
        try:
            return self.users[username]
        except KeyError:
            raise RemnawaveUserNotFoundError(username) from None


class FakeBedolaga:
    def __init__(self, users: dict[int, BotUser] | None = None) -> None:
        self.users = users or {}
        self.calls: list[int] = []

    async def __aenter__(self) -> "FakeBedolaga":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None

    async def user_by_telegram_id(self, telegram_id: int) -> BotUser:
        self.calls.append(telegram_id)
        try:
            return self.users[telegram_id]
        except KeyError:
            raise BedolagaUserNotFoundError(str(telegram_id)) from None


def _bot_user(referral_code: str | None = "bot-code-1") -> BotUser:
    return BotUser(
        id=1,
        telegram_id=INVITER_TELEGRAM_ID,
        referral_code=referral_code,
        referred_by_id=None,
        has_had_paid_subscription=True,
    )


def _resolver(
    *, panel: FakePanel | None = None, bedolaga: FakeBedolaga | None = None
) -> tuple[InviteResolver, _CountingFactory, _CountingFactory]:
    panel_factory = _CountingFactory(panel or FakePanel())
    bedolaga_factory = _CountingFactory(bedolaga or FakeBedolaga())
    resolver = InviteResolver(
        panel_factory=panel_factory, bedolaga_factory=bedolaga_factory
    )
    return resolver, panel_factory, bedolaga_factory


async def test_disabled_bridge_gives_null_without_any_remote_call() -> None:
    resolver, panel_factory, bedolaga_factory = _resolver()

    url = await resolver.resolve(
        INVITER_USERNAME, _settings(referral_bot_enabled=False)
    )

    assert url is None
    assert panel_factory.calls == 0
    assert bedolaga_factory.calls == 0


async def test_missing_bedolaga_token_gives_null_no_remote_call() -> None:
    resolver, panel_factory, bedolaga_factory = _resolver()

    url = await resolver.resolve(
        INVITER_USERNAME, _settings(bedolaga_api_token=None)
    )

    assert url is None
    assert panel_factory.calls == 0
    assert bedolaga_factory.calls == 0


async def test_junk_code_gives_null_without_any_remote_call() -> None:
    resolver, panel_factory, bedolaga_factory = _resolver()

    url = await resolver.resolve("../etc/passwd not a code", _settings())

    assert url is None
    assert panel_factory.calls == 0
    assert bedolaga_factory.calls == 0


async def test_missing_code_gives_null() -> None:
    resolver, _, _ = _resolver()

    assert await resolver.resolve(None, _settings()) is None


async def test_unknown_panel_user_gives_null() -> None:
    resolver, _, _ = _resolver(panel=FakePanel())

    url = await resolver.resolve(INVITER_USERNAME, _settings())

    assert url is None


async def test_inactive_inviter_gives_null() -> None:
    panel = FakePanel(
        {INVITER_USERNAME: _panel_payload(status="DISABLED")}
    )
    resolver, _, _ = _resolver(panel=panel)

    url = await resolver.resolve(INVITER_USERNAME, _settings())

    assert url is None


async def test_inviter_without_telegram_id_gives_null() -> None:
    panel = FakePanel(
        {INVITER_USERNAME: _panel_payload(telegram_id=None)}
    )
    resolver, _, _ = _resolver(panel=panel)

    url = await resolver.resolve(INVITER_USERNAME, _settings())

    assert url is None


async def test_integration_account_gives_null() -> None:
    panel = FakePanel(
        {
            "OOO_SINERGIYA_1": _panel_payload(
                username="OOO_SINERGIYA_1"
            )
        }
    )
    resolver, _, _ = _resolver(panel=panel)

    url = await resolver.resolve("OOO_SINERGIYA_1", _settings())

    assert url is None


async def test_bot_user_not_found_gives_null() -> None:
    panel = FakePanel({INVITER_USERNAME: _panel_payload()})
    resolver, _, _ = _resolver(panel=panel, bedolaga=FakeBedolaga())

    url = await resolver.resolve(INVITER_USERNAME, _settings())

    assert url is None


async def test_bot_user_without_referral_code_gives_null() -> None:
    panel = FakePanel({INVITER_USERNAME: _panel_payload()})
    bedolaga = FakeBedolaga(
        {INVITER_TELEGRAM_ID: _bot_user(referral_code=None)}
    )
    resolver, _, _ = _resolver(panel=panel, bedolaga=bedolaga)

    url = await resolver.resolve(INVITER_USERNAME, _settings())

    assert url is None


async def test_success_encodes_the_bot_referral_code() -> None:
    panel = FakePanel({INVITER_USERNAME: _panel_payload()})
    bedolaga = FakeBedolaga(
        {INVITER_TELEGRAM_ID: _bot_user(referral_code="a b+c/d")}
    )
    resolver, panel_factory, bedolaga_factory = _resolver(
        panel=panel, bedolaga=bedolaga
    )

    url = await resolver.resolve(INVITER_USERNAME, _settings())

    assert url == f"https://t.me/{BOT_USERNAME}?start=a%20b%2Bc%2Fd"
    assert panel_factory.calls == 1
    assert bedolaga_factory.calls == 1


async def test_any_exception_gives_null() -> None:
    class BrokenPanel:
        async def __aenter__(self) -> "BrokenPanel":
            raise RuntimeError("панель не отвечает")

        async def __aexit__(self, *exc_info: object) -> None:
            return None

    resolver = InviteResolver(panel_factory=lambda settings: BrokenPanel())

    url = await resolver.resolve(INVITER_USERNAME, _settings())

    assert url is None


async def test_cache_hit_makes_no_second_remote_call() -> None:
    panel = FakePanel({INVITER_USERNAME: _panel_payload()})
    bedolaga = FakeBedolaga({INVITER_TELEGRAM_ID: _bot_user()})
    resolver, panel_factory, bedolaga_factory = _resolver(
        panel=panel, bedolaga=bedolaga
    )
    settings = _settings()

    first = await resolver.resolve(INVITER_USERNAME, settings)
    second = await resolver.resolve(INVITER_USERNAME, settings)

    assert first == second
    assert first is not None
    assert panel.calls == [INVITER_USERNAME]
    assert bedolaga.calls == [INVITER_TELEGRAM_ID]
    assert panel_factory.calls == 1
    assert bedolaga_factory.calls == 1


async def test_cache_also_holds_a_null_result() -> None:
    resolver, panel_factory, _ = _resolver(panel=FakePanel())
    settings = _settings()

    first = await resolver.resolve(INVITER_USERNAME, settings)
    second = await resolver.resolve(INVITER_USERNAME, settings)

    assert first is None
    assert second is None
    assert panel_factory.calls == 1


async def test_cache_expires_after_its_ttl_using_an_injected_clock() -> None:
    panel = FakePanel({INVITER_USERNAME: _panel_payload()})
    bedolaga = FakeBedolaga({INVITER_TELEGRAM_ID: _bot_user()})
    panel_factory = _CountingFactory(panel)
    bedolaga_factory = _CountingFactory(bedolaga)
    now = [1000.0]
    resolver = InviteResolver(
        panel_factory=panel_factory,
        bedolaga_factory=bedolaga_factory,
        clock=lambda: now[0],
    )
    settings = _settings()

    await resolver.resolve(INVITER_USERNAME, settings)
    assert panel_factory.calls == 1

    now[0] += 599.0
    await resolver.resolve(INVITER_USERNAME, settings)
    assert panel_factory.calls == 1, "внутри TTL кэш не должен трогать сеть"

    now[0] += 2.0
    await resolver.resolve(INVITER_USERNAME, settings)
    assert panel_factory.calls == 2, "после TTL кэш обязан обновиться"


async def test_cache_evicts_the_oldest_entry_past_500() -> None:
    # Часы идут вперёд на каждом обращении: иначе 501 поход за одно
    # мгновение упёрся бы в ограничитель походов наружу, а тест про кэш.
    ticks = iter(range(10**9))
    resolver = InviteResolver(
        panel_factory=_CountingFactory(FakePanel()),
        bedolaga_factory=_CountingFactory(FakeBedolaga()),
        clock=lambda: next(ticks) * 1.5,
    )
    settings = _settings()

    for i in range(500):
        await resolver.resolve(f"user{i}", settings)
    assert len(resolver._cache) == 500
    assert "user0" in resolver._cache

    await resolver.resolve("user500", settings)

    assert len(resolver._cache) == 500
    assert "user0" not in resolver._cache
    assert "user500" in resolver._cache


async def test_lookups_are_capped_per_minute_and_recover_afterwards() -> None:
    """Перебор кодов не должен заваливать панель и бота запросами.

    Сверх лимита ответ пустой, наружу никто не ходит и в кэш пустота
    не пишется: настоящая ссылка заработает, как только окно освободится.
    """
    now = [1000.0]
    panel = FakePanel({INVITER_USERNAME: _panel_payload()})
    bedolaga = FakeBedolaga({INVITER_TELEGRAM_ID: _bot_user()})
    resolver = InviteResolver(
        panel_factory=_CountingFactory(panel),
        bedolaga_factory=_CountingFactory(bedolaga),
        clock=lambda: now[0],
    )
    settings = _settings()

    for index in range(30):
        assert await resolver.resolve(f"stranger_{index}", settings) is None
    assert len(panel.calls) == 30

    assert await resolver.resolve(INVITER_USERNAME, settings) is None
    assert len(panel.calls) == 30

    now[0] += 61.0
    url = await resolver.resolve(INVITER_USERNAME, settings)

    assert url is not None
    assert len(panel.calls) == 31
