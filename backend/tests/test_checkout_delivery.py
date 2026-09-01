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


def test_purchase_finds_the_already_linked_account() -> None:
    """Иначе старому клиенту заведут вторую учётку вместо продления.

    Имя в панели у перенесённых и заведённых вручную людей не выводится
    из почты: Alyona_Tutina, user_369990765, greyppm_62771416. Поиск
    только по почте их не находит, покупка создаёт дубль, а оплаченный
    срок остаётся на первой учётке. На 01.09.2026 таких было восемь
    из шестнадцати связанных кабинетов.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.deliver)

    assert "_privyazannaya_uchyotka" in source
    assert "get_user_by_id(privyazannaya)" in source


def test_linked_account_wins_over_the_email_guess() -> None:
    """Связь из кабинета точнее догадки по почте и должна идти первой."""
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.deliver)
    po_svyazi = source.index("get_user_by_id(privyazannaya)")
    po_pochte = source.index("get_user_by_username(username)")

    assert po_svyazi < po_pochte


def test_guest_purchase_is_matched_by_email() -> None:
    """Покупка без входа не имеет владельца, но кабинет может быть."""
    import inspect

    from app.services import checkout

    source = inspect.getsource(
        checkout.CheckoutService._privyazannaya_uchyotka
    )

    assert "payment.user_id" in source
    assert "payment.contact_email" in source
    assert "func.lower(User.email)" in source
