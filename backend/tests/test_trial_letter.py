"""Пробный доступ выдавался молча, и человек о нём не узнавал.

Регистрация заводила учётку в панели, открывала бесплатные дни и
отправляла уведомление владельцу сервиса. Самому человеку не уходило
ничего: ссылка лежала в кабинете, куда он больше не возвращался.

На 03.09.2026 таких было четверо из четверых: Алексей, Виктор, Игорь и
Егор зарегистрировались 13, 13, 15 и 25 августа, получили доступ и ни
разу не запросили подписку. Ноль устройств, ноль запросов.
"""

from datetime import date
from typing import Any

from app.core.config import Settings
from app.services.letters import trial_ready_letter


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {"_env_file": None}
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _letter(days: int = 7):
    return trial_ready_letter(
        subscription_url="https://panel.example.test/api/sub/abc",
        expires_at=date(2026, 9, 10),
        days=days,
        support_url="https://t.me/Anfikus",
        support_email="anfisa.kovganyuk@gmail.com",
        max_url="https://max.ru/u/xxx",
    )


def test_letter_carries_the_link_itself() -> None:
    """Приглашение зайти в кабинет уже не сработало четыре раза подряд."""
    letter = _letter()

    assert "https://panel.example.test/api/sub/abc" in letter.text
    assert "https://panel.example.test/api/sub/abc" in letter.html


def test_letter_names_the_apps() -> None:
    """Ссылка без приложения бесполезна, а искать его человек не станет."""
    letter = _letter()

    assert "incy" in letter.text
    assert "Happ" in letter.text


def test_letter_says_nothing_will_be_charged() -> None:
    """Иначе бесплатные дни читаются как начало платной подписки."""
    letter = _letter()

    assert "не спишется" in letter.text
    assert "не спишется" in letter.html


def test_letter_states_the_deadline() -> None:
    letter = _letter()

    assert "10.09.2026" in letter.text
    assert "10.09.2026" in letter.html


def test_letter_counts_the_days_it_was_given() -> None:
    """Срок берём из настройки, а не зашиваем: он менялся уже дважды."""
    assert "7 дней" in _letter(7).subject
    assert "30 дней" in _letter(30).subject


def test_letter_explains_pasting() -> None:
    """Ссылку набирают руками и ошибаются. Нужно сказать про буфер."""
    letter = _letter()

    assert "буфера обмена" in letter.text


def test_no_em_dashes_in_the_letter() -> None:
    """Анфиса просила их не использовать в текстах клиентам."""
    letter = _letter()

    assert "—" not in letter.text
    assert "—" not in letter.html


def test_registration_actually_sends_it() -> None:
    """Письмо без вызова из кода бесполезно ровно так же."""
    import inspect

    from app.services import auth

    source = inspect.getsource(auth.AuthService.register)

    assert "_pismo_o_triale" in source


def test_letter_never_breaks_the_registration() -> None:
    """Аккаунт и дни у человека уже есть, терять их из-за почты нельзя."""
    import inspect

    from app.services import auth

    source = inspect.getsource(auth.AuthService._pismo_o_triale)

    assert "except" in source
    assert "logger" in source


def test_trial_returns_the_link_not_just_a_flag() -> None:
    """Раньше grant отдавал bool, и писать письмо было нечем."""
    import inspect

    from app.services import trial

    source = inspect.getsource(trial.TrialService.grant)

    assert "TrialGranted(" in source
    assert "subscription_url=panel_user.subscription_url" in source


def test_no_letter_when_the_trial_did_not_happen() -> None:
    """Панель могла не ответить. Обещать доступ, которого нет, нельзя."""
    import inspect

    from app.services import auth

    source = inspect.getsource(auth.AuthService._pismo_o_triale)

    assert "if trial is None or not trial.subscription_url:" in source
