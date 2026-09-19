from typing import Any

import app.services.checkout as checkout_module
from app.core.config import Settings, get_settings
from app.models.billing import Payment, PaymentPurpose, PaymentStatus
from app.services.checkout import CheckoutService, panel_username


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


def test_extension_also_marks_the_buyer_as_paid() -> None:
    """Продление без тега оставляло покупателя с триальной разметкой.

    07.09.2026 shur_vlad_ead77bf0 пришёл с триала и купил месяц: срок
    продлился до 07.10, а тег остался TRIAL. Выручку считают по PAID,
    и такая покупка в подсчёт не попадала.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.deliver)
    _, prodlenie = source.split("panel_user = read_panel_user(existing)", 1)

    assert "set_expiry" in prodlenie
    assert 'tag="PAID"' in prodlenie


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


def test_referral_bonus_is_credited_after_the_letter() -> None:
    """Письмо покупателю важнее наград.

    Человек должен получить ссылку раньше, чем сайт займётся начислением
    бонусов за приглашение: рефералка может упасть, письмо не должно.
    """
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.deliver)
    novaya, prodlenie = source.split(
        "panel_user = read_panel_user(existing)", 1
    )

    for chunk in (novaya, prodlenie):
        pismo = chunk.index("_notify(")
        nagrada = chunk.index("_nachislit_za_priglashenie(")
        assert pismo < nagrada


def test_extension_reads_the_tag_before_set_expiry() -> None:
    """set_expiry всегда ставит PAID: узнать прежний тег после него нельзя."""
    import inspect

    from app.services import checkout

    source = inspect.getsource(checkout.CheckoutService.deliver)
    _, prodlenie = source.split(
        "panel_user = read_panel_user(existing)", 1
    )

    chtenie_tega = prodlenie.index('existing.get("tag")')
    prodlenie_sroka = prodlenie.index("set_expiry")
    assert chtenie_tega < prodlenie_sroka


class _BrokenReferral:
    """Поддельный сервис рефералки, который всегда падает.

    Настоящий ReferralService исключений не бросает, но метод выдачи
    награды обязан переживать даже такой сервис: деньги уже приняты,
    и падать из-за награды нельзя.
    """

    async def register(self, **_kwargs: Any) -> None:
        raise RuntimeError("рефералка упала")

    async def process(self, _reward: object) -> None:
        raise AssertionError("process не должен звать после падения register")


class _CountingReferral:
    """Поддельный сервис рефералки, который считает вызовы register."""

    def __init__(self) -> None:
        self.register_calls = 0

    async def register(self, **_kwargs: Any) -> None:
        self.register_calls += 1
        return None

    async def process(self, _reward: object) -> None:
        raise AssertionError("register вернул None, process звать незачем")


def _payment_with_code(referral_code: str | None) -> Payment:
    return Payment(
        user_id=None,
        contact_email="friend@example.test",
        amount_kopecks=30000,
        status=PaymentStatus.SUCCEEDED,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="platega",
        description="30 дней",
        tariff_id=2,
        period_days=30,
        referral_code=referral_code,
    )


async def test_referral_failure_does_not_escape_delivery() -> None:
    """Сбой рефералки не должен ронять ответ вебхуку."""
    service = CheckoutService(
        object(), get_settings(), _BrokenReferral()  # type: ignore[arg-type]
    )

    await service._nachislit_za_priglashenie(
        _payment_with_code("Alyona_Tutina"),
        friend_panel_user_id=42,
        friend_was_paid=False,
    )  # не должно ничего бросить


async def test_referral_step_is_skipped_without_a_service() -> None:
    """Без сервиса рефералки шаг должен просто ничего не делать."""
    service = CheckoutService(object(), get_settings())  # type: ignore[arg-type]

    await service._nachislit_za_priglashenie(
        _payment_with_code("Alyona_Tutina"),
        friend_panel_user_id=42,
        friend_was_paid=False,
    )  # не должно ничего бросить


async def test_referral_step_is_skipped_without_a_code() -> None:
    """Без кода у платежа рефералку звать незачем, даже если сервис есть."""
    referral = _CountingReferral()
    service = CheckoutService(object(), get_settings(), referral)  # type: ignore[arg-type]

    await service._nachislit_za_priglashenie(
        _payment_with_code(None),
        friend_panel_user_id=42,
        friend_was_paid=False,
    )

    assert referral.register_calls == 0


class _FakeShop:
    """Витрина без сети: start() интересует только код рефералки."""

    async def __aenter__(self) -> "_FakeShop":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def price_kopecks(self, _tariff_id: int, _period_days: int) -> int:
        return 30000

    async def tariff_name(self, _tariff_id: int) -> str:
        return "Тест"


class _FakeCreatedPayment:
    id = "tx-1"
    redirect_url = "https://platega.example/pay/tx-1"


class _FakePlatega:
    """Platega без сети: create_payment всегда отвечает одинаково."""

    async def __aenter__(self) -> "_FakePlatega":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def create_payment(self, **_kwargs: Any) -> _FakeCreatedPayment:
        return _FakeCreatedPayment()


class _StartSession:
    """Сессия без базы: start() только кладёт платёж и коммитит."""

    def __init__(self) -> None:
        self.added: list[Payment] = []

    def add(self, obj: Payment) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        return None


def _platega_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "platega_merchant_id": "m-1",
        "platega_secret": "s-1",
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


async def _start_with_code(
    monkeypatch: Any, *, referral_enabled: bool, referral_code: str | None
) -> Payment:
    monkeypatch.setattr(
        checkout_module, "ShopCatalogue", lambda _settings: _FakeShop()
    )
    monkeypatch.setattr(
        checkout_module, "PlategaGateway", lambda _settings: _FakePlatega()
    )
    session = _StartSession()
    service = CheckoutService(
        session, _platega_settings(referral_enabled=referral_enabled)
    )

    await service.start(
        email="guest@example.com",
        tariff_id=2,
        period_days=30,
        referral_code=referral_code,
    )

    return session.added[0]


async def test_start_normalizes_the_code_when_the_program_is_on(
    monkeypatch: Any,
) -> None:
    payment = await _start_with_code(
        monkeypatch,
        referral_enabled=True,
        referral_code="  Alyona_Tutina  ",
    )

    assert payment.referral_code == "Alyona_Tutina"


async def test_start_writes_none_for_a_garbage_referral_code(
    monkeypatch: Any,
) -> None:
    payment = await _start_with_code(
        monkeypatch,
        referral_enabled=True,
        referral_code="совсем не похоже на имя!!",
    )

    assert payment.referral_code is None


async def test_start_ignores_a_valid_code_when_the_program_is_off(
    monkeypatch: Any,
) -> None:
    """Выключенная рефералка не должна менять ни одной колонки платежа."""
    payment = await _start_with_code(
        monkeypatch,
        referral_enabled=False,
        referral_code="Alyona_Tutina",
    )

    assert payment.referral_code is None
