"""Тесты фоновой постановки обработки наград: без базы и без сети.

``obrabotat_nagradu`` и ``obojti_ozhidayushchie`` открывают настоящую
сессию через ``async_session_factory`` и здесь не проверяются: у
проекта нет тестовой Postgres. Тесты ``zapustit_obrabotku`` проверяют,
что задача держится живой до своего конца. Тесты ``sverit_ustrojstva``
подменяют и сессию, и сам сервис рефералки: реальная сверка устройств
уже проверена в test_referral.py поддельным хранилищем и панелью, а
здесь важно только то, что сверка идёт в своей сессии и не поднимает
исключений наружу.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.config import Settings
from app.models.billing import ReferralReward
from app.services import referral_wiring
from app.services.notify import TelegramNotifier


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {"_env_file": None}
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


async def test_zapustit_obrabotku_keeps_the_task_referenced_until_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Без сильной ссылки задачу могло бы собрать раньше её конца.

    Подменяем ``obrabotat_nagradu`` корутиной, которая ждёт свой
    ``Event``: пока она не отпущена, задача обязана оставаться в
    ``_ZADACHI``, а после завершения done-callback должен убрать её
    сам, без ручной очистки снаружи.
    """
    started = asyncio.Event()
    released = asyncio.Event()
    seen: list[UUID] = []

    async def fake_obrabotat_nagradu(reward_id: UUID) -> None:
        seen.append(reward_id)
        started.set()
        await released.wait()

    monkeypatch.setattr(
        referral_wiring, "obrabotat_nagradu", fake_obrabotat_nagradu
    )

    reward_id = uuid4()
    referral_wiring.zapustit_obrabotku(reward_id)
    await started.wait()

    assert seen == [reward_id]
    assert len(referral_wiring._ZADACHI) == 1
    task = next(iter(referral_wiring._ZADACHI))

    released.set()
    await task

    assert not referral_wiring._ZADACHI


class _FakeSession:
    """Сессия-пустышка: тестам сверки устройств запросов в неё не нужно."""

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def _reward() -> ReferralReward:
    return ReferralReward(
        id=uuid4(),
        payment_id=uuid4(),
        friend_email="friend@example.test",
        friend_panel_user_id=900,
        inviter_username="Alyona_Tutina",
        inviter_panel_user_id=500,
        friend_days=30,
        inviter_days=30,
        status="pending",
    )


async def test_sverit_ustrojstva_sends_one_message_per_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reward = _reward()
    sent: list[str] = []

    class FakeService:
        async def device_overlaps(
            self, since: object
        ) -> list[tuple[ReferralReward, int]]:
            return [(reward, 2)]

    monkeypatch.setattr(
        referral_wiring,
        "build_referral_service",
        lambda session, settings: FakeService(),
    )
    monkeypatch.setattr(
        referral_wiring, "async_session_factory", _FakeSession
    )
    monkeypatch.setattr(
        TelegramNotifier,
        "send_later",
        lambda self, text: sent.append(text),
    )

    count = await referral_wiring.sverit_ustrojstva()

    assert count == 1
    assert len(sent) == 1
    assert "2" in sent[0]
    assert chr(0x2014) not in sent[0]


async def test_sverit_ustrojstva_sends_nothing_without_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []

    class FakeService:
        async def device_overlaps(
            self, since: object
        ) -> list[tuple[ReferralReward, int]]:
            return []

    monkeypatch.setattr(
        referral_wiring,
        "build_referral_service",
        lambda session, settings: FakeService(),
    )
    monkeypatch.setattr(
        referral_wiring, "async_session_factory", _FakeSession
    )
    monkeypatch.setattr(
        TelegramNotifier,
        "send_later",
        lambda self, text: sent.append(text),
    )

    count = await referral_wiring.sverit_ustrojstva()

    assert count == 0
    assert sent == []


async def test_sverit_ustrojstva_never_raises_on_a_broken_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сбой при открытии сессии не должен ронять фоновый цикл в main.py."""

    def broken_factory() -> None:
        raise RuntimeError("нет соединения с базой")

    monkeypatch.setattr(
        referral_wiring, "async_session_factory", broken_factory
    )

    result = await referral_wiring.sverit_ustrojstva()

    assert result == 0


async def test_sinhronizirovat_bota_returns_the_created_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeService:
        async def sync_bot(self, schedule: object = None) -> int:
            assert schedule is referral_wiring.zapustit_obrabotku
            return 3

    monkeypatch.setattr(
        referral_wiring,
        "build_referral_service",
        lambda session, settings: FakeService(),
    )
    monkeypatch.setattr(
        referral_wiring, "async_session_factory", _FakeSession
    )

    result = await referral_wiring.sinhronizirovat_bota()

    assert result == 3


async def test_sinhronizirovat_bota_never_raises_on_a_broken_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Сбой при открытии сессии не должен ронять цикл в main.py."""

    def broken_factory() -> None:
        raise RuntimeError("нет соединения с базой")

    monkeypatch.setattr(
        referral_wiring, "async_session_factory", broken_factory
    )

    result = await referral_wiring.sinhronizirovat_bota()

    assert result == 0


async def test_sinhronizirovat_bota_never_raises_on_a_broken_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenService:
        async def sync_bot(self, schedule: object = None) -> int:
            raise RuntimeError("бот продаж не отвечает")

    monkeypatch.setattr(
        referral_wiring,
        "build_referral_service",
        lambda session, settings: BrokenService(),
    )
    monkeypatch.setattr(
        referral_wiring, "async_session_factory", _FakeSession
    )

    result = await referral_wiring.sinhronizirovat_bota()

    assert result == 0


def test_on_registered_from_build_referral_service_sends_one_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_referral_service`` обязана отдать ``sync_bot`` рабочий callback.

    Сама рассылка при новой награде из бота продаж уже проверена на
    уровне ``sync_bot`` (test_referral_bot.py) поддельным callback'ом.
    Здесь важно только то, что сборка для прода подставляет функцию,
    которая реально шлёт то же сообщение, что и checkout.py для сайта,
    с отметкой источника "бот".
    """
    sent: list[str] = []
    monkeypatch.setattr(
        TelegramNotifier,
        "send_later",
        lambda self, text: sent.append(text),
    )

    settings = _settings()
    service = referral_wiring.build_referral_service(
        object(),  # type: ignore[arg-type]
        settings,
    )
    reward = _reward()

    service._on_registered(reward)  # noqa: SLF001

    assert len(sent) == 1
    assert "бот" in sent[0].lower()
    assert chr(0x2014) not in sent[0]


def test_on_registered_respects_alert_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        TelegramNotifier,
        "send_later",
        lambda self, text: sent.append(text),
    )

    settings = _settings(telegram_alert_events="registration,login")
    service = referral_wiring.build_referral_service(
        object(),  # type: ignore[arg-type]
        settings,
    )

    service._on_registered(_reward())  # noqa: SLF001

    assert sent == []


def test_bot_sync_period_never_shorter_than_five_minutes() -> None:
    assert referral_wiring.bot_sync_period(
        _settings(referral_bot_sync_minutes=1)
    ) == timedelta(minutes=5)
    assert referral_wiring.bot_sync_period(
        _settings(referral_bot_sync_minutes=45)
    ) == timedelta(minutes=45)


def test_bot_sync_next_run_uses_a_short_delay_on_the_first_run() -> None:
    now = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)

    next_run = referral_wiring.bot_sync_next_run(
        poslednij_zapusk=None, seichas=now, period=timedelta(minutes=30)
    )

    assert next_run == now + referral_wiring._BOT_SYNC_PERVYJ_ZAPUSK
    assert next_run < now + timedelta(minutes=30)


def test_bot_sync_next_run_counts_from_the_last_run_afterwards() -> None:
    last_run = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    much_later = last_run + timedelta(hours=5)

    next_run = referral_wiring.bot_sync_next_run(
        poslednij_zapusk=last_run,
        seichas=much_later,
        period=timedelta(minutes=30),
    )

    assert next_run == last_run + timedelta(minutes=30)
