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


def test_return_url_points_at_an_existing_page() -> None:
    """Возврат ведёт на /buy: страницы /pay на сайте нет.

    Проверка глазами тут не работает — 404 виден только тому, кто уже
    заплатил, а это худший момент для сюрприза.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.start)

    assert "/buy?token=" in source
    assert "/pay/" not in source


def test_new_user_gets_a_squad_a_tag_and_a_device_limit() -> None:
    """Без сквада ноды не видят пользователя, и подписка пуста.

    24.08.2026 так прошла первая живая продажа: деньги списались,
    учётка завелась, а подключиться человек не мог. Проверка держит
    все три поля вместе — порознь они бесполезны.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.deliver)

    assert "active_internal_squads=[squad]" in source
    assert 'tag="PAID"' in source
    assert "hwid_device_limit=" in source


def test_delivery_refuses_to_create_a_user_without_a_squad() -> None:
    """Тихая выдача битой учётки хуже отказа: деньги уже приняты."""
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.deliver)

    assert "CheckoutNotConfiguredError" in source
    assert "remnawave_squad_uuid" in source
