from app.services.checkout import panel_username


def test_username_is_a_pure_function_of_the_email() -> None:
    """Одна почта — одно имя всегда. Иначе вторая покупка заведёт дубль."""
    assert panel_username("Guest@Example.COM") == panel_username(
        "guest@example.com"
    )


def test_username_survives_awkward_emails() -> None:
    name = panel_username("имя.фамилия+метка@example.com")

    assert name
    assert " " not in name
    assert len(name) <= 64


def test_different_domains_do_not_collide() -> None:
    """Один и тот же логин на разных почтах — разные люди."""
    assert panel_username("anfisa@one.example") != panel_username(
        "anfisa@two.example"
    )
