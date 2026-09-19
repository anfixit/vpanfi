"""Тесты фоновой постановки обработки наград: без базы и без сети.

``obrabotat_nagradu`` и ``obojti_ozhidayushchie`` открывают настоящую
сессию через ``async_session_factory`` и здесь не проверяются: у
проекта нет тестовой Postgres. Эти тесты только про
``zapustit_obrabotku`` - что задача держится живой до своего конца.
"""

import asyncio
from uuid import UUID, uuid4

import pytest

from app.services import referral_wiring


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
