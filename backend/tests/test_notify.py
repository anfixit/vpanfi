"""Владелец должен узнавать о движениях на сайте в тот же день.

О шести ушедших в августе людях стало известно спустя две недели, и
только потому, что за ними полезли в базу руками. Сайт молчал обо всём:
о регистрациях, о входах, об оплатах и о том, что деньги приняли, а
доступ не выдали.
"""

from datetime import date
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services import notify as notify_module
from app.services.notify import (
    TelegramNotifier,
    pokupka_soobshchenie,
    registraciya_soobshchenie,
    sboj_vydachi_soobshchenie,
    vhod_soobshchenie,
)


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "telegram_alert_bot_token": SecretStr("123:token"),
        "telegram_alert_chat_id": "1577231",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_notifier_is_silent_without_settings() -> None:
    """Ненастроенные уведомления не должны мешать работать сайту."""
    quiet = TelegramNotifier(
        _settings(telegram_alert_bot_token=None, telegram_alert_chat_id=None)
    )

    assert quiet.is_configured is False


def test_notifier_wakes_up_when_configured() -> None:
    assert TelegramNotifier(_settings()).is_configured is True


class DeadTelegram:
    """Телеграм, который не отвечает."""

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "DeadTelegram":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, *_args: Any, **_kwargs: Any) -> Any:
        raise httpx.ConnectError("телеграм недоступен")


@pytest.mark.anyio
async def test_send_swallows_a_dead_telegram(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Телеграм не должен ронять покупку: деньги уже приняты."""
    monkeypatch.setattr(notify_module.httpx, "AsyncClient", DeadTelegram)

    ushlo = await TelegramNotifier(_settings()).send("проверка")

    assert ushlo is False


def test_background_send_is_silent_when_not_configured() -> None:
    """Иначе фоновая задача создавалась бы впустую на каждый вход."""
    quiet = TelegramNotifier(
        _settings(telegram_alert_bot_token=None, telegram_alert_chat_id=None)
    )

    quiet.send_later("проверка")  # не должно ничего бросить


def test_events_can_be_narrowed() -> None:
    """Входов сильно больше остального, и их убавят первыми."""
    only = _settings(telegram_alert_events="registration,payment")

    assert only.alert_events == {"registration", "payment"}
    assert "login" not in only.alert_events


def test_all_three_events_are_on_by_default() -> None:
    assert _settings().alert_events == {"registration", "login", "payment"}


def test_registration_message_says_whether_the_trial_worked() -> None:
    """Молчаливо невыданный триал уже стоил шести человек."""
    good = registraciya_soobshchenie(
        email="guest@example.com", display_name="Гость", trial_granted=True
    )
    bad = registraciya_soobshchenie(
        email="guest@example.com", display_name="Гость", trial_granted=False
    )

    assert "выданы" in good
    assert "НЕ выданы" in bad
    assert "guest@example.com" in good


def test_login_message_names_the_person() -> None:
    text = vhod_soobshchenie(
        email="guest@example.com", display_name="Гость"
    )

    assert "guest@example.com" in text
    assert "Гость" in text


def test_purchase_message_warns_about_an_empty_subscription() -> None:
    """Пустая ссылка означает, что человек заплатил и не подключится.

    24.08.2026 так и вышло: подписку выдали без сквада, в ней не было
    ни одного сервера, и сутки этого никто не видел.
    """
    beznogo = pokupka_soobshchenie(
        email="guest@example.com",
        amount_kopecks=30000,
        description="30 дней",
        expires_at=date(2026, 9, 30),
        is_new=True,
        subscription_url=None,
    )

    assert "⚠️" in beznogo
    assert "проверь панель" in beznogo


def test_purchase_message_shows_roubles_not_kopecks() -> None:
    text = pokupka_soobshchenie(
        email="guest@example.com",
        amount_kopecks=150000,
        description="180 дней",
        expires_at=date(2027, 2, 28),
        is_new=False,
        subscription_url="https://panel.example.test/api/sub/abc",
    )

    assert "1 500" in text
    assert "150000" not in text


def test_failed_delivery_message_says_what_to_do() -> None:
    """Это единственный случай, когда человек заплатил и остался ни с чем."""
    text = sboj_vydachi_soobshchenie(
        email="guest@example.com",
        amount_kopecks=30000,
        prichina="панель не отвечает",
    )

    assert "НЕ ВЫДАН" in text
    assert "вручную" in text


def test_markup_in_a_name_cannot_break_the_message() -> None:
    """Имя человек вводит сам, а сообщение уходит с разметкой HTML."""
    text = registraciya_soobshchenie(
        email="guest@example.com",
        display_name="<b>жирный</b>",
        trial_granted=True,
    )

    assert "<b>жирный</b>" not in text
    assert "&lt;b&gt;" in text


def test_registration_and_login_are_wired_in() -> None:
    """Сообщения без вызова из кода бесполезны ровно так же."""
    import inspect

    from app.services import auth

    source = inspect.getsource(auth.AuthService)

    assert "registraciya_soobshchenie" in source
    assert "vhod_soobshchenie" in source


def test_purchase_and_failure_are_wired_in() -> None:
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService)

    assert "pokupka_soobshchenie" in source
    assert "sboj_vydachi_soobshchenie" in source


def test_failed_delivery_cannot_be_switched_off() -> None:
    """Выключить можно шум, но не сообщение о неполученном доступе."""
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService._soobshchit_o_sboe)

    assert "alert_events" not in source
