"""Кнопка «7 дней бесплатно» должна выдавать семь дней.

С 13 по 25 августа 2026 она их не выдавала: регистрация заводила запись
и на этом всё, а человек попадал в кабинет с прайсом. Тесты держат три
вещи, порознь бесполезные: доступ вообще появляется, появляется со
сквадом, и регистрация переживает недоступную панель.
"""

from typing import Any

import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.remnawave.client import (
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)
from app.services import trial as trial_module
from app.services.checkout import panel_username
from app.services.trial import TrialService
from tests.conftest import build_user

SQUAD = "b5732868-7bcf-4014-b68d-223b49d085a3"


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "remnawave_base_url": "https://panel.example.test",
        "remnawave_api_token": SecretStr("token"),
        "remnawave_squad_uuid": SQUAD,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakePanel:
    """Панель, которой ещё не знаком такой пользователь."""

    def __init__(self, existing: dict[str, Any] | None = None) -> None:
        self.existing = existing
        self.created: dict[str, Any] | None = None

    async def __aenter__(self) -> "FakePanel":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        if self.existing is None:
            raise RemnawaveUserNotFoundError(username)
        return self.existing

    async def create_user(self, **kwargs: Any) -> dict[str, Any]:
        self.created = kwargs
        return {
            "id": 141,
            "username": kwargs["username"],
            "expireAt": "2026-09-03T00:00:00.000Z",
            "subscriptionUrl": "https://panel.example.test/api/sub/abc",
        }


class DeadPanel(FakePanel):
    async def __aenter__(self) -> "DeadPanel":
        raise RemnawaveUnavailableError("панель не отвечает")


def _use(monkeypatch: pytest.MonkeyPatch, panel: FakePanel) -> None:
    monkeypatch.setattr(
        trial_module, "RemnawaveGateway", lambda _settings: panel
    )


@pytest.mark.anyio
async def test_registration_grants_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Главное: после регистрации доступ есть, а не прайс-лист."""
    panel = FakePanel()
    _use(monkeypatch, panel)
    user = build_user()
    session = FakeSession()

    granted = await TrialService(session, _settings()).grant(user)  # type: ignore[arg-type]

    assert granted is True
    assert user.remnawave_user_id == 141
    assert user.remnawave_username == panel_username(user.email)
    assert session.commits == 1


@pytest.mark.anyio
async def test_trial_user_lands_in_a_squad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Без сквада подписка отдаёт пустой список серверов.

    Учётка при этом заводится и выглядит здоровой, поэтому проверка
    смотрит именно на переданные поля, а не на факт создания.
    """
    panel = FakePanel()
    _use(monkeypatch, panel)

    await TrialService(FakeSession(), _settings()).grant(build_user())  # type: ignore[arg-type]

    assert panel.created is not None
    assert panel.created["active_internal_squads"] == [SQUAD]
    assert panel.created["tag"] == "TRIAL"
    assert panel.created["hwid_device_limit"] == 3


@pytest.mark.anyio
async def test_without_a_squad_nothing_is_created(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Пустая учётка хуже отсутствия: человек не поймёт, что сломалось."""
    panel = FakePanel()
    _use(monkeypatch, panel)

    granted = await TrialService(
        FakeSession(),  # type: ignore[arg-type]
        _settings(remnawave_squad_uuid=None),
    ).grant(build_user())

    assert granted is False
    assert panel.created is None


@pytest.mark.anyio
async def test_dead_panel_does_not_break_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Аккаунт заводят один раз, триал можно довыдать руками."""
    _use(monkeypatch, DeadPanel())
    user = build_user()

    granted = await TrialService(FakeSession(), _settings()).grant(user)  # type: ignore[arg-type]

    assert granted is False
    assert user.remnawave_user_id is None


@pytest.mark.anyio
async def test_existing_panel_user_is_linked_not_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Имя выводится из почты, поэтому учётка может уже быть.

    Второй пользователь в панели на ту же почту означал бы две
    подписки и путаницу при продлении.
    """
    panel = FakePanel(
        existing={
            "id": 137,
            "username": "oksana_l_07_ef3005e8",
            "expireAt": "2026-09-30T23:59:59.000Z",
        }
    )
    _use(monkeypatch, panel)
    user = build_user()

    granted = await TrialService(FakeSession(), _settings()).grant(user)  # type: ignore[arg-type]

    assert granted is True
    assert panel.created is None
    assert user.remnawave_user_id == 137


@pytest.mark.anyio
async def test_already_linked_user_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Повторный вызов не должен трогать того, у кого доступ уже есть."""
    panel = FakePanel()
    _use(monkeypatch, panel)
    user = build_user()
    user.remnawave_user_id = 99

    granted = await TrialService(FakeSession(), _settings()).grant(user)  # type: ignore[arg-type]

    assert granted is False
    assert user.remnawave_user_id == 99


@pytest.mark.anyio
async def test_zero_days_switches_the_trial_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Выключатель на случай, если раздавать станет нечем."""
    panel = FakePanel()
    _use(monkeypatch, panel)

    granted = await TrialService(
        FakeSession(),  # type: ignore[arg-type]
        _settings(trial_days=0),
    ).grant(build_user())

    assert granted is False
    assert panel.created is None


def test_registration_calls_the_trial() -> None:
    """Сервис без вызова из регистрации бесполезен ровно так же."""
    import inspect

    from app.services import auth

    source = inspect.getsource(auth.AuthService.register)

    assert "TrialService" in source
    assert ".grant(user)" in source
