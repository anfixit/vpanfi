import httpx
import pytest
import respx

from app.core.config import Settings
from app.models.user import ExternalIdentity, IdentityProvider, User
from app.services.wallet import WalletService

BASE_URL = "https://bedolaga.example.test/api"
TELEGRAM_ID = 355251045
SHORT_UUID = "9Pt-SNvQp-pMNRbZ"
SUBSCRIPTION_URL = f"https://panel.example.test/api/sub/{SHORT_UUID}"


def _settings(*, token: str | None = "s3cret") -> Settings:
    return Settings(
        _env_file=None,
        bedolaga_api_url=BASE_URL,
        bedolaga_api_token=token,
    )


def _user(*, telegram_id: int | None = None) -> User:
    """Пользователь кабинета, при надобности с привязанным Telegram."""
    user = User(
        email="anfisa@vpanfi.ru",
        display_name="Тестовая Анфиса",
        password_digest="unused",
    )
    user.identities = []
    if telegram_id is not None:
        user.identities.append(
            ExternalIdentity(
                provider=IdentityProvider.TELEGRAM,
                provider_user_id=str(telegram_id),
            )
        )
    return user


def _bot_user(
    *,
    balance_kopeks: int | None = 40_000,
    subscription_url: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"id": 42, "telegram_id": TELEGRAM_ID}
    if balance_kopeks is not None:
        payload["balance_kopeks"] = balance_kopeks
    if subscription_url is not None:
        payload["subscription"] = {
            "id": 777,
            "is_trial": False,
            "subscription_url": subscription_url,
        }
    return payload


@respx.mock
async def test_balance_comes_from_the_bot_by_telegram_id() -> None:
    route = respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(200, json=_bot_user())
    )

    wallet = WalletService(_settings())
    balance = await wallet.balance_kopeks(_user(telegram_id=TELEGRAM_ID))

    assert balance == 40_000
    assert route.called


@respx.mock
async def test_subscription_link_finds_a_person_without_telegram() -> None:
    """Сайт нужен тем, у кого Telegram недоступен: их ищем по подписке."""
    respx.get(f"{BASE_URL}/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    _bot_user(
                        balance_kopeks=15_050,
                        subscription_url=SUBSCRIPTION_URL,
                    )
                ],
                "total": 1,
            },
        )
    )

    wallet = WalletService(_settings())
    balance = await wallet.balance_kopeks(
        _user(), subscription_url=SUBSCRIPTION_URL
    )

    assert balance == 15_050


@respx.mock
async def test_subscription_link_rescues_an_unknown_telegram_id() -> None:
    """Telegram привязан, а в боте человека нет: спасает ссылка."""
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )
    respx.get(f"{BASE_URL}/users").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    _bot_user(subscription_url=SUBSCRIPTION_URL),
                ],
                "total": 1,
            },
        )
    )

    wallet = WalletService(_settings())
    balance = await wallet.balance_kopeks(
        _user(telegram_id=TELEGRAM_ID), subscription_url=SUBSCRIPTION_URL
    )

    assert balance == 40_000


@respx.mock
async def test_no_account_in_the_bot_means_no_balance() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(404, json={"detail": "not found"})
    )

    wallet = WalletService(_settings())
    balance = await wallet.balance_kopeks(_user(telegram_id=TELEGRAM_ID))

    assert balance is None


@respx.mock
async def test_subscription_unknown_to_the_bot_means_no_balance() -> None:
    respx.get(f"{BASE_URL}/users").mock(
        return_value=httpx.Response(200, json={"items": [], "total": 0})
    )

    wallet = WalletService(_settings())
    balance = await wallet.balance_kopeks(
        _user(), subscription_url=SUBSCRIPTION_URL
    )

    assert balance is None


@respx.mock
async def test_unreachable_bot_means_no_balance() -> None:
    """Молчащий бот не ломает кабинет и не превращается в ноль рублей."""
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        side_effect=httpx.ConnectError("boom")
    )

    wallet = WalletService(_settings())
    balance = await wallet.balance_kopeks(_user(telegram_id=TELEGRAM_ID))

    assert balance is None


@respx.mock
async def test_bot_error_means_no_balance() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(500, text="oops")
    )

    wallet = WalletService(_settings())
    balance = await wallet.balance_kopeks(_user(telegram_id=TELEGRAM_ID))

    assert balance is None


@respx.mock
async def test_balance_missing_in_the_answer_is_not_zero() -> None:
    respx.get(f"{BASE_URL}/users/by-telegram-id/{TELEGRAM_ID}").mock(
        return_value=httpx.Response(
            200, json=_bot_user(balance_kopeks=None)
        )
    )

    wallet = WalletService(_settings())
    balance = await wallet.balance_kopeks(_user(telegram_id=TELEGRAM_ID))

    assert balance is None


async def test_no_keys_means_no_request_to_the_bot() -> None:
    """Ни Telegram, ни ссылки: искать нечем, и бота мы не трогаем."""
    with respx.mock:
        wallet = WalletService(_settings())
        assert await wallet.balance_kopeks(_user()) is None


async def test_bridge_without_a_token_is_silent() -> None:
    wallet = WalletService(_settings(token=None))
    balance = await wallet.balance_kopeks(_user(telegram_id=TELEGRAM_ID))

    assert balance is None


@pytest.mark.parametrize("stored", ["", "не число", "tg:123"])
async def test_unreadable_telegram_binding_is_ignored(stored: str) -> None:
    user = _user()
    user.identities.append(
        ExternalIdentity(
            provider=IdentityProvider.TELEGRAM,
            provider_user_id=stored,
        )
    )

    with respx.mock:
        wallet = WalletService(_settings())
        assert await wallet.balance_kopeks(user) is None
