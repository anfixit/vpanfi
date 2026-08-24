from datetime import date

from app.services.letters import subscription_ready_letter

LINK = "https://kovganyuk.duckdns.org/api/sub/kPM7pDoAbc123"


def _letter():
    return subscription_ready_letter(
        subscription_url=LINK,
        expires_at=date(2026, 9, 21),
        support_url="https://t.me/Anfikus",
        support_email="anfisa@example.test",
        max_url="https://max.ru/u/abc",
    )


def test_letter_carries_the_link_itself() -> None:
    """Главное в письме — сама ссылка, а не кнопка «зайдите куда-то».

    Человек, потерявший вкладку после оплаты по СБП, должен получить
    рабочую ссылку прямо в почте: до кабинета он может и не дойти.
    """
    letter = _letter()

    assert LINK in letter.text
    assert LINK in letter.html


def test_letter_never_mentions_the_bot_cabinet() -> None:
    """Кабинет бота живёт на чужом домене и только путает покупателя."""
    letter = _letter()

    assert "vpanfibot" not in letter.text
    assert "vpanfibot" not in letter.html


def test_letter_tells_what_to_do_with_the_link() -> None:
    letter = _letter()

    assert "вставьте" in letter.text.lower()
    assert "INCY" in letter.text
    assert "HAPP" in letter.text


def test_letter_names_the_date_the_subscription_runs_until() -> None:
    letter = _letter()

    assert "21.09.2026" in letter.text
    assert "21.09.2026" in letter.html


def test_subject_says_what_happened() -> None:
    assert _letter().subject == "Ваша подписка VPaNfi готова"


def test_html_escapes_the_support_address() -> None:
    """Адрес поддержки приходит из настроек и попадает в разметку."""
    letter = subscription_ready_letter(
        subscription_url=LINK,
        expires_at=date(2026, 9, 21),
        support_url="https://t.me/Anfikus?a=1&b=2",
        support_email="anfisa@example.test",
        max_url="https://max.ru/u/abc",
    )

    assert "&amp;b=2" in letter.html


def test_letter_offers_a_contact_that_works_without_vpn() -> None:
    """Письмо получает и тот, у кого подписка не заработала.

    Один телеграм в таком письме бесполезен: без VPN он не откроется,
    и человек остаётся без связи ровно тогда, когда она нужнее всего.
    """
    letter = _letter()

    for part in (letter.text, letter.html):
        assert "anfisa@example.test" in part
        assert "max.ru" in part
        assert "t.me/Anfikus" in part
