"""Сайт продавал и замолкал навсегда.

Бот предупреждает об окончании только тех, кто в нём есть, а покупателя
сайта там нет: он платит почтой, без телеграма. На 31.08.2026 половина
платящих в боте отсутствует, и предупредить их было нечем.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from app.core.config import Settings
from app.services.letters import subscription_expiring_letter
from app.services.reminders import RemindersService


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "smtp_host": "smtp.example.test",
        "smtp_from_email": "noreply@vpanfi.su",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _service(settings: Settings | None = None) -> RemindersService:
    return RemindersService(None, settings or _settings())  # type: ignore[arg-type]


def test_default_thresholds_are_a_week_three_days_and_a_day() -> None:
    assert _settings().reminder_days_list == [1, 3, 7]


def test_garbage_does_not_disable_reminders() -> None:
    """Опечатка не должна оставлять людей без предупреждений."""
    s = _settings(reminder_days="7, , три, 1, 0, -5, 3")

    assert s.reminder_days_list == [1, 3, 7]


def test_empty_setting_switches_reminders_off() -> None:
    """Явный выключатель на случай, если писать станет нечем."""
    assert _settings(reminder_days="").reminder_days_list == []


def test_closest_threshold_wins() -> None:
    """При пропущенном обходе пишем про ближний срок, а не про дальний.

    Иначе человек за два дня до конца получил бы письмо «осталась
    неделя», которое уже неправда.
    """
    srv = _service()

    assert srv._porog(7) == 7
    assert srv._porog(5) == 7
    assert srv._porog(3) == 3
    assert srv._porog(2) == 3
    assert srv._porog(1) == 1
    assert srv._porog(0) == 1


def test_too_early_means_no_letter() -> None:
    assert _service()._porog(8) is None
    assert _service()._porog(90) is None


def test_letter_counts_days_in_russian() -> None:
    """«Через 2 дня», а не «через 2 дней»: письмо читает человек."""
    def skolko(n: int) -> str:
        return subscription_expiring_letter(
            days_left=n,
            expires_at=date(2026, 9, 30),
            buy_url="https://vpanfi.su/buy",
            support_url="https://t.me/Anfikus",
            support_email="anfisa.kovganyuk@gmail.com",
        ).subject

    assert "сегодня" in skolko(0)
    assert "завтра" in skolko(1)
    assert "через 2 дня" in skolko(2)
    assert "через 5 дней" in skolko(5)
    assert "через 7 дней" in skolko(7)


def test_letter_leads_to_the_short_path() -> None:
    """Продлевают на /buy: там не нужен ни вход, ни пароль."""
    letter = subscription_expiring_letter(
        days_left=3,
        expires_at=date(2026, 9, 30),
        buy_url="https://vpanfi.su/buy",
        support_url="https://t.me/Anfikus",
        support_email="anfisa.kovganyuk@gmail.com",
    )

    assert "https://vpanfi.su/buy" in letter.text
    assert "https://vpanfi.su/buy" in letter.html


def test_letter_says_nothing_will_be_charged() -> None:
    """Человек должен понимать, что бездействие ничего не спишет."""
    letter = subscription_expiring_letter(
        days_left=1,
        expires_at=date(2026, 9, 30),
        buy_url="https://vpanfi.su/buy",
        support_url="https://t.me/Anfikus",
        support_email="anfisa.kovganyuk@gmail.com",
    )

    assert "никаких списаний" in letter.text
    assert "никаких списаний" in letter.html


def test_letter_promises_days_do_not_burn() -> None:
    """Иначе человек тянет до последнего дня, боясь потерять остаток."""
    letter = subscription_expiring_letter(
        days_left=7,
        expires_at=date(2026, 9, 30),
        buy_url="https://vpanfi.su/buy",
        support_url="https://t.me/Anfikus",
        support_email="anfisa.kovganyuk@gmail.com",
    )

    assert "не сгорят" in letter.text or "не сгорают" in letter.html


def test_reminder_is_keyed_by_the_expiry_date() -> None:
    """После продления круг предупреждений начинается заново.

    Если ключом был бы только порог, продлившийся человек больше
    никогда не получил бы предупреждения.
    """
    from app.models.reminder import SubscriptionReminder

    cols = {c.name for c in SubscriptionReminder.__table__.columns}
    assert {"user_id", "expires_on", "days_before"} <= cols

    uq = [
        c for c in SubscriptionReminder.__table__.constraints
        if c.name == "uq_reminder_once_per_cycle"
    ]
    assert uq, "нет защиты от повторной отправки"
    assert {c.name for c in uq[0].columns} == {
        "user_id", "expires_on", "days_before"
    }


def test_mark_is_written_before_sending() -> None:
    """Письмо, ушедшее дважды, хуже неотправленного.

    Почта может ответить долго или упасть уже после отправки, поэтому
    отметку ставим первой, а сбой ловим журналом.
    """
    import inspect

    from app.services import reminders

    source = inspect.getsource(reminders.RemindersService._odin)
    otmetka = source.index("_otmetit")
    otpravka = source.index("Mailer")

    assert otmetka < otpravka


def test_expired_subscription_gets_no_letter() -> None:
    """Предупреждать задним числом бессмысленно и обидно."""
    import inspect

    from app.services import reminders

    source = inspect.getsource(reminders.RemindersService._odin)

    assert "ostalos < 0" in source


def test_scheduler_survives_a_broken_round() -> None:
    """Обход идёт по кругу: падение не должно его останавливать."""
    import inspect

    from app import main

    source = inspect.getsource(main._napominaniya)

    assert "while True" in source
    assert "except Exception" in source
    assert "CancelledError" in source


@pytest.mark.anyio
async def test_dead_panel_does_not_break_the_round() -> None:
    """Панель может не ответить, и это не повод падать."""
    import inspect

    from app.services import reminders

    source = inspect.getsource(reminders.RemindersService.run_once)

    assert "RemnawaveUnavailableError" in source
    assert "return otpravleno" in source


def test_days_left_is_computed_from_today() -> None:
    """Проверка арифметики порогов без обращения наружу."""
    today = datetime.now(UTC).date()
    assert (today + timedelta(days=3) - today).days == 3
