"""Купивший в один шаг оставался без кабинета, а значит без напоминаний.

Обход напоминаний ищет владельцев кабинетов. Тот, кто купил коротким
путём с /buy, кабинета не заводил, и предупредить его об окончании срока
было нечем. 01.09.2026 так купила Алёна Тутина сразу на три месяца:
до 30.11.2026 её не предупредил бы никто.

Короткий путь при этом трогать нельзя, он приносит покупки. Поэтому
кабинет заводится сам, а пароль человек ставит через восстановление.
"""

from datetime import date
from typing import Any

from app.core.config import Settings
from app.services.letters import subscription_ready_letter


def _settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {"_env_file": None}
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _letter(cabinet_url: str | None):
    return subscription_ready_letter(
        subscription_url="https://panel.example.test/api/sub/abc",
        expires_at=date(2026, 11, 30),
        support_url="https://t.me/Anfikus",
        support_email="anfisa.kovganyuk@gmail.com",
        max_url="https://max.ru/u/xxx",
        cabinet_url=cabinet_url,
    )


def test_letter_stays_silent_when_no_cabinet_was_created() -> None:
    """Старому клиенту про кабинет писать нечего, он у него уже есть."""
    letter = _letter(None)

    assert "кабинет" not in letter.text.lower()
    assert "Забыли пароль" not in letter.html


def test_letter_tells_about_the_new_cabinet() -> None:
    """Молча заведённый кабинет хуже незаведённого.

    Человек не знает, что вход есть, и при попытке зарегистрироваться
    получит «почта уже занята», не понимая почему.
    """
    letter = _letter("https://vpanfi.su")

    assert "кабинет" in letter.text.lower()
    assert "https://vpanfi.su" in letter.text
    assert "https://vpanfi.su" in letter.html


def test_letter_explains_how_to_get_in() -> None:
    """Пароля мы не присылаем, значит надо сказать, где его поставить."""
    letter = _letter("https://vpanfi.su")

    assert "Забыли пароль" in letter.text
    assert "Забыли пароль" in letter.html


def test_password_never_travels_by_email() -> None:
    """Пароль в письме живёт в чужом ящике вечно.

    Учётка заводится без пароля, человек ставит свой сам. Проверяем,
    что выдача его и не придумывает.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService._zavesti_kabinet)

    assert "password_digest=None" in source
    assert "hash_password" not in source
    assert "secrets" not in source


def test_cabinet_is_created_on_delivery() -> None:
    """Заводить надо после выдачи, а не после оплаты.

    Если подписку выдать не удалось, кабинет без подписки человеку
    не нужен, а связь с панелью проставить всё равно нечем.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.deliver)

    assert source.count("_kabinet_bezopasno") == 2, (
        "кабинет должен заводиться в обеих ветках: и новой учётке, "
        "и продлению существующей"
    )


def test_panel_link_is_what_makes_reminders_work() -> None:
    """Кабинет без связи с панелью для напоминаний бесполезен.

    Обход берёт только тех, у кого remnawave_user_id заполнен.
    """
    import inspect

    from app.services import checkout, reminders

    obhod = inspect.getsource(reminders.RemindersService.run_once)
    zavod = inspect.getsource(checkout.CheckoutService._zavesti_kabinet)

    assert "remnawave_user_id.is_not(None)" in obhod
    assert "user.remnawave_user_id = panel_user_id" in zavod


def test_someone_elses_panel_account_is_left_alone() -> None:
    """Один id панели не может принадлежать двум кабинетам.

    Поле уникально, и попытка присвоить занятый id уронила бы выдачу
    уже после того, как деньги приняты.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService._zavesti_kabinet)

    assert "zanyato" in source
    assert "User.email != pochta" in source


def test_a_broken_cabinet_never_breaks_the_delivery() -> None:
    """Подписка это то, за что заплатили. Кабинет только удобство."""
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService._kabinet_bezopasno)

    assert "except Exception" in source
    assert "rollback" in source
    assert "return False" in source


def test_existing_cabinet_is_reused_not_duplicated() -> None:
    """Вторая покупка с той же почты не должна ронять выдачу.

    Почта в users уникальна: слепое создание разошлось бы об это
    ограничение на второй покупке того же человека.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService._zavesti_kabinet)

    assert "func.lower(User.email) == pochta" in source
    assert "novyj = user is None" in source
