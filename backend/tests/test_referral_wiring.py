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
from uuid import UUID, uuid4

import pytest

from app.models.billing import ReferralReward
from app.services import referral_wiring
from app.services.notify import TelegramNotifier


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
