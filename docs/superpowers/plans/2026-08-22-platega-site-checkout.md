# Своя касса Platega на сайте — план работ

> **Для агентов:** ОБЯЗАТЕЛЬНЫЙ СУБ-НАВЫК: выполнять этот план задача за задачей через superpowers:subagent-driven-development (рекомендуется) или superpowers:executing-plans. Шаги помечены чекбоксами (`- [ ]`).

**Цель:** сайт vpanfi.su принимает оплату своим мерчантом Platega и сам выдаёт подписку в панели Remnawave.

**Архитектура:** клиент Platega изолирован так же, как клиент панели, и не знает ни про подписки, ни про пользователей. Платёж фиксируется в таблице `payments` сайта до похода в Platega; подписку выдаёт вебхук, и только тот его вызов, который перевёл платёж из `pending` в `succeeded`. Цену считает сервер, читая витрину бота, — сумме из браузера не верим.

**Стек:** FastAPI, SQLAlchemy 2 (async), Alembic, httpx, pytest + respx, React 19 + Vite.

## Общие ограничения

- Питон 3.12; тесты запускаются `\.venv/bin/python -m pytest -q backend/tests` из корня репозитория.
- Проверки, обязательные перед пушем: `ruff check backend`, `pytest -q backend/tests`, `npm run typecheck && npm run build`, `docker compose config --quiet`.
- Комментарии и сообщения коммитов — по-русски, как в остальном репозитории. Комментарий объясняет причину, а не пересказывает код.
- Секреты никогда не попадают в лог, в текст ошибки и в ответ API.
- Мерчант сайта: `cf9fe88f-8258-4527-8070-5f91c3b8d3cb`. Мерчант бота `2fe558b4-…` — чужой, использовать нельзя.
- API сайта живёт под префиксом `/api/v1`, проверено на бою: `/api/v1/cabinet/dashboard` отвечает 401, `/api/cabinet/dashboard` — 404.
- Контракт Platega, снятый с рабочего кода бота: `POST /transaction/process`, заголовки `X-MerchantId` и `X-Secret`, тело `{"paymentMethod": <int>, "paymentDetails": {"amount": <рубли, float>, "currency": "RUB"}, "description": <≤64 символов>, "return": <url>, "failedUrl": <url>, "payload": <наш id>}`. Ответ содержит `id` (или `transactionId`) и `redirect`. Статус — `GET /transaction/{id}`. Успех в вебхуке — статус `CONFIRMED`.
- **Сумма в Platega передаётся в рублях с двумя знаками**, а в базе сайта хранится в копейках. Переводить в одном месте — в сервисе, не в клиенте и не в роутере.

---

### Задача 1: Настройки кассы

**Файлы:**
- Изменить: `backend/app/core/config.py`
- Изменить: `.env.example`
- Изменить: `docker-compose.yml` (передать переменные в сервис `api`)
- Тест: `backend/tests/test_config.py`

**Интерфейсы:**
- Отдаёт: `Settings.platega_merchant_id: SecretStr | None`, `Settings.platega_secret: SecretStr | None`, `Settings.platega_base_url: AnyHttpUrl`, `Settings.platega_timeout_seconds: float`, `Settings.platega_payment_method: int`, `Settings.shop_base_url: AnyHttpUrl`, `Settings.shop_slug: str`, `Settings.is_platega_configured: bool`

- [ ] **Шаг 1: Написать падающий тест**

```python
# backend/tests/test_config.py — дописать в конец
from pydantic import SecretStr

from app.core.config import Settings


def test_platega_is_not_configured_without_both_values() -> None:
    """Одного мерчанта без секрета мало: касса или настроена целиком, или нет."""
    only_merchant = Settings(_env_file=None, platega_merchant_id="cf9fe88f")

    assert only_merchant.is_platega_configured is False


def test_platega_is_configured_when_both_values_are_present() -> None:
    settings = Settings(
        _env_file=None,
        platega_merchant_id="cf9fe88f",
        platega_secret=SecretStr("secret"),
    )

    assert settings.is_platega_configured is True
    assert str(settings.platega_base_url).rstrip("/") == "https://app.platega.io"
    assert settings.platega_payment_method == 2
```

- [ ] **Шаг 2: Убедиться, что тест падает**

Запустить: `.venv/bin/python -m pytest backend/tests/test_config.py -q`
Ожидается: FAIL — у `Settings` нет поля `platega_merchant_id`.

- [ ] **Шаг 3: Добавить настройки**

```python
# backend/app/core/config.py — рядом с настройками панели
    # Касса сайта. Мерчант отдельный от бота: у бота свой, и путать их
    # нельзя — деньги уйдут не на тот счёт.
    platega_merchant_id: str | None = None
    platega_secret: SecretStr | None = None
    platega_base_url: AnyHttpUrl = AnyHttpUrl("https://app.platega.io")
    platega_timeout_seconds: float = 15.0
    # 2 — СБП. Тот же метод, что бот показывает на витрине.
    platega_payment_method: int = 2

    # Витрина бота: сайт читает оттуда тарифы и цены, чтобы они не
    # разъехались с ботом.
    shop_base_url: AnyHttpUrl = AnyHttpUrl("https://vpanfibot.ru/cabinet/landing")
    shop_slug: str = "vpanfi"

    @property
    def is_platega_configured(self) -> bool:
        """Касса готова, только когда есть и мерчант, и секрет."""
        return bool(self.platega_merchant_id and self.platega_secret)
```

- [ ] **Шаг 4: Убедиться, что тесты проходят**

Запустить: `.venv/bin/python -m pytest backend/tests/test_config.py -q`
Ожидается: PASS.

- [ ] **Шаг 5: Описать переменные в `.env.example`**

```bash
# Касса сайта. Мерчант выдан Platega отдельно от бота: у бота свой, и
# перепутать их значит увести деньги на чужой счёт.
VPANFI_PLATEGA_MERCHANT_ID=
VPANFI_PLATEGA_SECRET=
```

- [ ] **Шаг 6: Передать переменные контейнеру**

```yaml
# docker-compose.yml, сервис api, блок environment
      VPANFI_PLATEGA_MERCHANT_ID: ${VPANFI_PLATEGA_MERCHANT_ID:-}
      VPANFI_PLATEGA_SECRET: ${VPANFI_PLATEGA_SECRET:-}
```

- [ ] **Шаг 7: Проверить сборку и закоммитить**

```bash
docker compose config --quiet && .venv/bin/python -m ruff check backend
git add backend/app/core/config.py backend/tests/test_config.py .env.example docker-compose.yml
git commit -m "feat: описать настройки своей кассы Platega"
```

---

### Задача 2: Клиент Platega

**Файлы:**
- Создать: `backend/app/integrations/platega/__init__.py`
- Создать: `backend/app/integrations/platega/client.py`
- Тест: `backend/tests/test_platega_gateway.py`

**Интерфейсы:**
- Использует: `Settings` из задачи 1.
- Отдаёт: `PlategaGateway(settings)` с `async create_payment(*, amount_rubles: float, description: str, payload: str, return_url: str, failed_url: str) -> PlategaPayment` и `async get_payment(payment_id: str) -> Mapping[str, Any]`; датакласс `PlategaPayment(id: str, redirect_url: str)`; ошибки `PlategaNotConfiguredError`, `PlategaUnavailableError`.

- [ ] **Шаг 1: Написать падающие тесты**

```python
# backend/tests/test_platega_gateway.py
import httpx
import pytest
import respx
from pydantic import SecretStr

from app.core.config import Settings
from app.integrations.platega.client import (
    PlategaGateway,
    PlategaNotConfiguredError,
    PlategaUnavailableError,
)

PLATEGA_URL = "https://platega.example.test"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        platega_base_url=PLATEGA_URL,
        platega_merchant_id="merchant-1",
        platega_secret=SecretStr("secret-1"),
    )


def test_gateway_requires_credentials() -> None:
    with pytest.raises(PlategaNotConfiguredError):
        PlategaGateway(Settings(_env_file=None))


@respx.mock
async def test_create_payment_sends_the_documented_body() -> None:
    route = respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(
            200,
            json={"id": "tx-1", "redirect": "https://pay.platega.io?id=tx-1"},
        )
    )

    async with PlategaGateway(_settings()) as gateway:
        payment = await gateway.create_payment(
            amount_rubles=300.0,
            description="Подписка на 30 дней",
            payload="payment-uuid",
            return_url="https://vpanfi.su/pay/done",
            failed_url="https://vpanfi.su/pay/failed",
        )

    request = route.calls.last.request
    body = request.content.decode()
    assert request.headers["X-MerchantId"] == "merchant-1"
    assert request.headers["X-Secret"] == "secret-1"
    assert '"paymentMethod":2' in body
    assert '"amount":300.0' in body
    assert '"currency":"RUB"' in body
    assert '"payload":"payment-uuid"' in body
    assert payment.id == "tx-1"
    assert payment.redirect_url == "https://pay.platega.io?id=tx-1"


@respx.mock
async def test_transaction_id_is_accepted_instead_of_id() -> None:
    """Platega называет идентификатор двумя способами — принимаем оба."""
    respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(
            200, json={"transactionId": "tx-2", "redirect": "https://pay/2"}
        )
    )

    async with PlategaGateway(_settings()) as gateway:
        payment = await gateway.create_payment(
            amount_rubles=800.0,
            description="Подписка",
            payload="p",
            return_url="https://vpanfi.su/done",
            failed_url="https://vpanfi.su/failed",
        )

    assert payment.id == "tx-2"


@respx.mock
async def test_answer_without_redirect_is_an_error() -> None:
    """Платёж без ссылки бесполезен: человеку некуда идти платить."""
    respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(200, json={"id": "tx-3"})
    )

    async with PlategaGateway(_settings()) as gateway:
        with pytest.raises(PlategaUnavailableError):
            await gateway.create_payment(
                amount_rubles=300.0,
                description="Подписка",
                payload="p",
                return_url="https://vpanfi.su/done",
                failed_url="https://vpanfi.su/failed",
            )


@respx.mock
async def test_description_is_cut_to_the_limit() -> None:
    """Platega принимает не длиннее 64 символов и иначе отвечает ошибкой."""
    route = respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(200, json={"id": "t", "redirect": "https://p"})
    )

    async with PlategaGateway(_settings()) as gateway:
        await gateway.create_payment(
            amount_rubles=300.0,
            description="я" * 200,
            payload="p",
            return_url="https://vpanfi.su/done",
            failed_url="https://vpanfi.su/failed",
        )

    sent = route.calls.last.request.content.decode("unicode_escape")
    assert "я" * 65 not in sent


@respx.mock
async def test_panel_error_becomes_domain_error() -> None:
    respx.post(f"{PLATEGA_URL}/transaction/process").mock(
        return_value=httpx.Response(500)
    )

    async with PlategaGateway(_settings()) as gateway:
        with pytest.raises(PlategaUnavailableError):
            await gateway.create_payment(
                amount_rubles=300.0,
                description="Подписка",
                payload="p",
                return_url="https://vpanfi.su/done",
                failed_url="https://vpanfi.su/failed",
            )
```

- [ ] **Шаг 2: Убедиться, что тесты падают**

Запустить: `.venv/bin/python -m pytest backend/tests/test_platega_gateway.py -q`
Ожидается: FAIL — модуля `app.integrations.platega.client` нет.

- [ ] **Шаг 3: Написать клиент**

```python
# backend/app/integrations/platega/__init__.py
"""Изолированный клиент платёжной системы Platega."""
```

```python
# backend/app/integrations/platega/client.py
"""Единственная точка входа сайта в API Platega.

Клиент знает только про платежи: он не ходит в панель, ничего не пишет в
базу и не решает, что делать после оплаты. Так его можно проверить целиком
на замоканных ответах.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "PlategaError",
    "PlategaGateway",
    "PlategaNotConfiguredError",
    "PlategaPayment",
    "PlategaUnavailableError",
]

CREATE_PATH = "/transaction/process"
# Длину описания ограничивает сама Platega: более длинное она отвергает.
DESCRIPTION_LIMIT = 64


class PlategaError(RuntimeError):
    """Базовая ошибка интеграции с Platega."""


class PlategaNotConfiguredError(PlategaError):
    """Мерчант или секрет не заданы."""


class PlategaUnavailableError(PlategaError):
    """Platega недоступна или ответила непригодным ответом."""


@dataclass(frozen=True)
class PlategaPayment:
    """Созданный платёж: его идентификатор и ссылка на оплату."""

    id: str
    redirect_url: str


class PlategaGateway:
    def __init__(self, settings: Settings) -> None:
        if not settings.is_platega_configured:
            raise PlategaNotConfiguredError(
                "Platega merchant id and secret are required"
            )

        assert settings.platega_secret is not None
        self._payment_method = settings.platega_payment_method
        self._client = httpx.AsyncClient(
            base_url=str(settings.platega_base_url).rstrip("/"),
            headers={
                "X-MerchantId": settings.platega_merchant_id or "",
                "X-Secret": settings.platega_secret.get_secret_value(),
                "Accept": "application/json",
            },
            timeout=settings.platega_timeout_seconds,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_payment(
        self,
        *,
        amount_rubles: float,
        description: str,
        payload: str,
        return_url: str,
        failed_url: str,
    ) -> PlategaPayment:
        """Создать платёж и получить ссылку, по которой человек заплатит."""
        body: dict[str, Any] = {
            "paymentMethod": self._payment_method,
            "paymentDetails": {
                "amount": round(amount_rubles, 2),
                "currency": "RUB",
            },
            "description": description[:DESCRIPTION_LIMIT],
            "return": return_url,
            "failedUrl": failed_url,
            "payload": payload,
        }

        answer = await self._request("POST", CREATE_PATH, json=body)

        # Platega называет идентификатор то id, то transactionId.
        identifier = answer.get("transactionId") or answer.get("id")
        redirect = answer.get("redirect")
        if not identifier or not redirect:
            logger.warning("Platega ответила без ссылки на оплату")
            raise PlategaUnavailableError(
                "Platega returned a payment without a redirect link"
            )

        return PlategaPayment(id=str(identifier), redirect_url=str(redirect))

    async def get_payment(self, payment_id: str) -> Mapping[str, Any]:
        """Спросить состояние платежа у самой Platega."""
        return await self._request("GET", f"/transaction/{payment_id}")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        try:
            response = await self._client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            logger.warning(
                "Platega %s %s недоступна: %s", method, path, type(exc).__name__
            )
            raise PlategaUnavailableError("Platega is unreachable") from exc

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # Тело ответа не логируем: в нём может оказаться наш секрет.
            logger.warning(
                "Platega %s %s ответила %s",
                method,
                path,
                exc.response.status_code,
            )
            raise PlategaUnavailableError(
                f"Platega responded with {exc.response.status_code}"
            ) from exc

        try:
            answer = response.json()
        except ValueError as exc:
            raise PlategaUnavailableError(
                "Platega returned a non-JSON response"
            ) from exc

        if not isinstance(answer, Mapping):
            raise PlategaUnavailableError("Platega returned an unexpected body")
        return answer
```

- [ ] **Шаг 4: Убедиться, что тесты проходят**

Запустить: `.venv/bin/python -m pytest backend/tests/test_platega_gateway.py -q`
Ожидается: PASS, 5 тестов.

- [ ] **Шаг 5: Закоммитить**

```bash
.venv/bin/python -m ruff check backend
git add backend/app/integrations/platega backend/tests/test_platega_gateway.py
git commit -m "feat: научить сайт разговаривать с Platega"
```

---

### Задача 3: Цену считает сервер

**Файлы:**
- Создать: `backend/app/services/shop.py`
- Тест: `backend/tests/test_shop_catalogue.py`

**Интерфейсы:**
- Использует: `Settings.shop_base_url`, `Settings.shop_slug` из задачи 1.
- Отдаёт: `ShopCatalogue(settings)` с `async price_kopecks(tariff_id: int, period_days: int) -> int` и `async tariff_name(tariff_id: int) -> str`; ошибки `UnknownTariffError`, `ShopUnavailableError`.

- [ ] **Шаг 1: Написать падающие тесты**

```python
# backend/tests/test_shop_catalogue.py
import httpx
import pytest
import respx

from app.core.config import Settings
from app.services.shop import (
    ShopCatalogue,
    ShopUnavailableError,
    UnknownTariffError,
)

SHOP_URL = "https://bot.example.test/cabinet/landing"

CATALOGUE = {
    "title": "VPaNfi",
    "tariffs": [
        {
            "id": 2,
            "name": "30 дней",
            "device_limit": 3,
            "traffic_limit_gb": 0,
            "periods": [{"days": 30, "price_kopeks": 30000}],
        },
        {
            "id": 3,
            "name": "90 дней",
            "device_limit": 3,
            "traffic_limit_gb": 0,
            "periods": [{"days": 90, "price_kopeks": 80000}],
        },
    ],
    "payment_methods": [{"method_id": "platega"}],
}


def _settings() -> Settings:
    return Settings(_env_file=None, shop_base_url=SHOP_URL, shop_slug="vpanfi")


@respx.mock
async def test_price_comes_from_the_shop_not_from_the_client() -> None:
    respx.get(f"{SHOP_URL}/vpanfi").mock(
        return_value=httpx.Response(200, json=CATALOGUE)
    )

    async with ShopCatalogue(_settings()) as shop:
        assert await shop.price_kopecks(2, 30) == 30000
        assert await shop.tariff_name(3) == "90 дней"


@respx.mock
async def test_unknown_tariff_is_rejected() -> None:
    """Неизвестный тариф — попытка купить то, чего не продаём."""
    respx.get(f"{SHOP_URL}/vpanfi").mock(
        return_value=httpx.Response(200, json=CATALOGUE)
    )

    async with ShopCatalogue(_settings()) as shop:
        with pytest.raises(UnknownTariffError):
            await shop.price_kopecks(99, 30)


@respx.mock
async def test_unknown_period_is_rejected() -> None:
    respx.get(f"{SHOP_URL}/vpanfi").mock(
        return_value=httpx.Response(200, json=CATALOGUE)
    )

    async with ShopCatalogue(_settings()) as shop:
        with pytest.raises(UnknownTariffError):
            await shop.price_kopecks(2, 31)


@respx.mock
async def test_broken_shop_becomes_domain_error() -> None:
    respx.get(f"{SHOP_URL}/vpanfi").mock(return_value=httpx.Response(502))

    async with ShopCatalogue(_settings()) as shop:
        with pytest.raises(ShopUnavailableError):
            await shop.price_kopecks(2, 30)
```

- [ ] **Шаг 2: Убедиться, что тесты падают**

Запустить: `.venv/bin/python -m pytest backend/tests/test_shop_catalogue.py -q`
Ожидается: FAIL — модуля `app.services.shop` нет.

- [ ] **Шаг 3: Написать витрину**

```python
# backend/app/services/shop.py
"""Цены сайт берёт у витрины бота, а не у браузера.

Сумму, пришедшую из браузера, подделать ничего не стоит: платёж создался бы
на любую цену, какую назовёт покупатель. Поэтому клиент присылает только
идентификатор тарифа и число дней, а рубли сервер выясняет сам.
"""

import logging
from types import TracebackType
from typing import Any, Self

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "ShopCatalogue",
    "ShopError",
    "ShopUnavailableError",
    "UnknownTariffError",
]


class ShopError(RuntimeError):
    """Базовая ошибка витрины."""


class ShopUnavailableError(ShopError):
    """Витрина недоступна или ответила непонятным."""


class UnknownTariffError(ShopError):
    """Такого тарифа или периода в продаже нет."""


class ShopCatalogue:
    def __init__(self, settings: Settings) -> None:
        self._slug = settings.shop_slug
        self._client = httpx.AsyncClient(
            base_url=str(settings.shop_base_url).rstrip("/"),
            headers={"Accept": "application/json"},
            timeout=settings.remnawave_timeout_seconds,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self._client.aclose()

    async def price_kopecks(self, tariff_id: int, period_days: int) -> int:
        """Цена выбранного периода в копейках."""
        tariff = await self._tariff(tariff_id)
        for period in tariff.get("periods") or []:
            if int(period.get("days", -1)) == period_days:
                return int(period["price_kopeks"])
        raise UnknownTariffError(f"tariff {tariff_id} has no {period_days} days")

    async def tariff_name(self, tariff_id: int) -> str:
        tariff = await self._tariff(tariff_id)
        return str(tariff.get("name") or "Подписка")

    async def _tariff(self, tariff_id: int) -> dict[str, Any]:
        for tariff in await self._catalogue():
            if int(tariff.get("id", -1)) == tariff_id:
                return tariff
        raise UnknownTariffError(f"tariff {tariff_id} is not on sale")

    async def _catalogue(self) -> list[dict[str, Any]]:
        try:
            response = await self._client.get(f"/{self._slug}")
            response.raise_for_status()
            answer = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Витрина недоступна: %s", type(exc).__name__)
            raise ShopUnavailableError("The shop is unreachable") from exc

        tariffs = answer.get("tariffs") if isinstance(answer, dict) else None
        if not isinstance(tariffs, list):
            raise ShopUnavailableError("The shop returned no tariffs")
        return [tariff for tariff in tariffs if isinstance(tariff, dict)]
```

- [ ] **Шаг 4: Убедиться, что тесты проходят**

Запустить: `.venv/bin/python -m pytest backend/tests/test_shop_catalogue.py -q`
Ожидается: PASS, 4 теста.

- [ ] **Шаг 5: Закоммитить**

```bash
.venv/bin/python -m ruff check backend
git add backend/app/services/shop.py backend/tests/test_shop_catalogue.py
git commit -m "feat: считать цену на сервере, а не верить браузеру"
```

---

### Задача 4: Платёж гостя без аккаунта

**Файлы:**
- Изменить: `backend/app/models/billing.py:60-90`
- Создать: `backend/alembic/versions/20260822_0003_guest_payments.py`
- Тест: `backend/tests/test_billing_model.py`

**Интерфейсы:**
- Отдаёт: `Payment.user_id: UUID | None`, `Payment.contact_email: str | None`, `Payment.period_days: int | None`, `Payment.tariff_id: int | None`.

Гость покупает по почте, аккаунта у него может не быть. Заводить ему аккаунт молча нельзя: почта в `users` уникальна, восстановления пароля на сайте нет, и человек навсегда потеряет возможность зарегистрироваться сам. Поэтому платёж живёт без пользователя, а связь с человеком держит почта.

- [ ] **Шаг 1: Написать падающий тест**

```python
# backend/tests/test_billing_model.py
from app.models.billing import Payment, PaymentPurpose, PaymentStatus


def test_payment_can_belong_to_a_guest() -> None:
    """Гость платит по почте, аккаунта у него может не быть вовсе."""
    payment = Payment(
        user_id=None,
        contact_email="guest@example.com",
        amount_kopecks=30000,
        status=PaymentStatus.PENDING,
        purpose=PaymentPurpose.SUBSCRIPTION,
        provider="platega",
        description="Подписка на 30 дней",
        tariff_id=2,
        period_days=30,
    )

    assert payment.user_id is None
    assert payment.contact_email == "guest@example.com"
    assert payment.period_days == 30
```

- [ ] **Шаг 2: Убедиться, что тест падает**

Запустить: `.venv/bin/python -m pytest backend/tests/test_billing_model.py -q`
Ожидается: FAIL — у `Payment` нет `contact_email`.

- [ ] **Шаг 3: Поправить модель**

```python
# backend/app/models/billing.py, класс Payment
    # Гость покупает по почте, и аккаунта у него может не быть. Заводить
    # его молча нельзя: почта в users уникальна, а восстановления пароля
    # на сайте нет — человек не смог бы зарегистрироваться сам.
    user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
    )
    contact_email: Mapped[str | None] = mapped_column(String(320), index=True)
    tariff_id: Mapped[int | None] = mapped_column(Integer)
    period_days: Mapped[int | None] = mapped_column(Integer)
    subscription_url: Mapped[str | None] = mapped_column(String(500))
```

и заменить связь на необязательную:

```python
    user: Mapped[User | None] = relationship()
```

- [ ] **Шаг 4: Написать миграцию**

```python
# backend/alembic/versions/20260822_0003_guest_payments.py
"""Платёж гостя: без аккаунта, но с почтой.

Revision ID: 20260822_0003
Revises: 20260821_0002
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260822_0003"
down_revision: str | None = "20260821_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("payments", "user_id", nullable=True)
    op.add_column("payments", sa.Column("contact_email", sa.String(length=320)))
    op.add_column("payments", sa.Column("tariff_id", sa.Integer()))
    op.add_column("payments", sa.Column("period_days", sa.Integer()))
    # Ссылку на подписку возвращает панель в момент выдачи. Храним её,
    # иначе страница результата не сможет показать человеку, что он купил.
    op.add_column("payments", sa.Column("subscription_url", sa.String(length=500)))
    op.create_index("ix_payments_contact_email", "payments", ["contact_email"])


def downgrade() -> None:
    op.drop_index("ix_payments_contact_email", table_name="payments")
    op.drop_column("payments", "subscription_url")
    op.drop_column("payments", "period_days")
    op.drop_column("payments", "tariff_id")
    op.drop_column("payments", "contact_email")
    # Платежи без пользователя обратно не помещаются — их удаляем.
    op.execute("DELETE FROM payments WHERE user_id IS NULL")
    op.alter_column("payments", "user_id", nullable=False)
```

- [ ] **Шаг 5: Убедиться, что тест проходит**

Запустить: `.venv/bin/python -m pytest backend/tests/test_billing_model.py -q`
Ожидается: PASS.

- [ ] **Шаг 6: Закоммитить**

```bash
.venv/bin/python -m ruff check backend
git add backend/app/models/billing.py backend/alembic/versions/20260822_0003_guest_payments.py backend/tests/test_billing_model.py
git commit -m "feat: разрешить платёж гостя без аккаунта на сайте"
```

---

### Задача 5: Создание платежа

**Файлы:**
- Создать: `backend/app/services/checkout.py`
- Создать: `backend/app/api/routes/payments.py`
- Изменить: `backend/app/api/router.py`
- Изменить: `backend/app/api/dependencies.py`
- Изменить: `backend/app/schemas/cabinet.py`
- Тест: `backend/tests/test_checkout_routes.py`

**Интерфейсы:**
- Использует: `PlategaGateway`, `ShopCatalogue`, модель `Payment` из задач 2–4.
- Отдаёт: `CheckoutService.start(email: str, tariff_id: int, period_days: int) -> StartedCheckout`, где `StartedCheckout(payment_id: UUID, redirect_url: str)`; маршрут `POST /api/v1/payments/checkout`; схемы `CheckoutRequest`, `CheckoutResponse`.

- [ ] **Шаг 1: Написать падающий тест**

```python
# backend/tests/test_checkout_routes.py
from app.main import create_app


def test_checkout_rejects_a_price_from_the_browser(anonymous_client) -> None:
    """Сумму принимать нельзя — её назначает сервер."""
    answer = anonymous_client.post(
        "/api/v1/payments/checkout",
        json={
            "email": "guest@example.com",
            "tariffId": 2,
            "periodDays": 30,
            "amountKopecks": 1,
        },
    )

    assert answer.status_code == 422


def test_checkout_without_configured_cash_desk_says_so(anonymous_client) -> None:
    """Без настроенной кассы сайт обязан сказать это прямо, а не молчать."""
    answer = anonymous_client.post(
        "/api/v1/payments/checkout",
        json={"email": "guest@example.com", "tariffId": 2, "periodDays": 30},
    )

    assert answer.status_code == 503
    assert answer.json()["detail"]["code"] == "payments_not_configured"
```

- [ ] **Шаг 2: Убедиться, что тест падает**

Запустить: `.venv/bin/python -m pytest backend/tests/test_checkout_routes.py -q`
Ожидается: FAIL — маршрута нет, ответ 404.

- [ ] **Шаг 3: Написать схемы**

```python
# backend/app/schemas/cabinet.py — дописать
class CheckoutRequest(BaseModel):
    """Заявка на покупку.

    Суммы здесь намеренно нет: цену выясняет сервер, иначе покупатель
    назначил бы её себе сам. extra="forbid" превращает присланную сумму в
    отказ, а не в молча проигнорированное поле.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    email: EmailStr
    tariff_id: int = Field(gt=0, alias="tariffId")
    period_days: int = Field(gt=0, le=730, alias="periodDays")


class CheckoutResponse(BaseModel):
    payment_id: UUID = Field(serialization_alias="paymentId")
    redirect_url: str = Field(serialization_alias="redirectUrl")


class PaymentStatusResponse(BaseModel):
    """Состояние платежа для страницы результата."""

    status: str
    paid: bool
    subscription_url: str | None = Field(
        default=None, serialization_alias="subscriptionUrl"
    )
```

- [ ] **Шаг 4: Написать сервис**

```python
# backend/app/services/checkout.py
"""Покупка: создать платёж и увести человека платить.

Платёж записывается в базу до похода в Platega. Если Platega не ответит,
у нас останется след с суммой и почтой — иначе деньги могли бы уйти по
ссылке, о которой сайт ничего не знает.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.platega.client import (
    PlategaGateway,
    PlategaNotConfiguredError,
    PlategaUnavailableError,
)
from app.models.billing import Payment, PaymentPurpose, PaymentStatus
from app.services.shop import ShopCatalogue, ShopUnavailableError, UnknownTariffError

logger = logging.getLogger(__name__)

KOPECKS_IN_RUBLE = 100


class CheckoutNotConfiguredError(RuntimeError):
    """Касса не настроена."""


class CheckoutUnavailableError(RuntimeError):
    """Платёжная система или витрина недоступны."""


@dataclass(frozen=True)
class StartedCheckout:
    payment_id: UUID
    redirect_url: str


class CheckoutService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def start(
        self,
        *,
        email: str,
        tariff_id: int,
        period_days: int,
    ) -> StartedCheckout:
        if not self._settings.is_platega_configured:
            raise CheckoutNotConfiguredError("Platega is not configured")

        async with ShopCatalogue(self._settings) as shop:
            try:
                amount_kopecks = await shop.price_kopecks(tariff_id, period_days)
                name = await shop.tariff_name(tariff_id)
            except UnknownTariffError:
                raise
            except ShopUnavailableError as error:
                raise CheckoutUnavailableError(str(error)) from error

        payment = Payment(
            user_id=None,
            contact_email=email,
            amount_kopecks=amount_kopecks,
            status=PaymentStatus.PENDING,
            purpose=PaymentPurpose.SUBSCRIPTION,
            provider="platega",
            description=f"{name}, {period_days} дн.",
            tariff_id=tariff_id,
            period_days=period_days,
        )
        self._session.add(payment)
        await self._session.flush()

        origin = self._settings.allowed_origins[0].rstrip("/")
        try:
            async with PlategaGateway(self._settings) as platega:
                created = await platega.create_payment(
                    amount_rubles=amount_kopecks / KOPECKS_IN_RUBLE,
                    description=payment.description,
                    payload=str(payment.id),
                    return_url=f"{origin}/pay/{payment.id}",
                    failed_url=f"{origin}/pay/{payment.id}?failed=1",
                )
        except PlategaNotConfiguredError as error:
            raise CheckoutNotConfiguredError(str(error)) from error
        except PlategaUnavailableError as error:
            payment.status = PaymentStatus.FAILED
            await self._session.commit()
            raise CheckoutUnavailableError(str(error)) from error

        payment.provider_payment_id = created.id
        await self._session.commit()

        return StartedCheckout(payment_id=payment.id, redirect_url=created.redirect_url)
```

- [ ] **Шаг 5: Написать маршрут и подключить его**

```python
# backend/app/api/routes/payments.py
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_checkout_service
from app.schemas.cabinet import CheckoutRequest, CheckoutResponse
from app.services.checkout import (
    CheckoutNotConfiguredError,
    CheckoutService,
    CheckoutUnavailableError,
)
from app.services.shop import UnknownTariffError

router = APIRouter(prefix="/payments", tags=["payments"])
CheckoutServiceDep = Annotated[CheckoutService, Depends(get_checkout_service)]


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    summary="Создать платёж и получить ссылку на оплату",
)
async def start_checkout(
    payload: CheckoutRequest,
    checkout: CheckoutServiceDep,
) -> CheckoutResponse:
    try:
        started = await checkout.start(
            email=payload.email,
            tariff_id=payload.tariff_id,
            period_days=payload.period_days,
        )
    except CheckoutNotConfiguredError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "payments_not_configured",
                "message": "Оплата на сайте пока не подключена",
            },
        ) from error
    except UnknownTariffError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "tariff_not_found", "message": "Такого тарифа нет"},
        ) from error
    except CheckoutUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": "payments_unavailable",
                "message": "Платёжная система не отвечает, попробуйте ещё раз",
            },
        ) from error

    return CheckoutResponse(
        payment_id=started.payment_id,
        redirect_url=started.redirect_url,
    )
```

```python
# backend/app/api/dependencies.py — дописать
def get_checkout_service(
    session: DatabaseSession,
    settings: SettingsDep,
) -> CheckoutService:
    return CheckoutService(session, settings)
```

```python
# backend/app/api/router.py — дописать
from app.api.routes.payments import router as payments_router

api_router.include_router(payments_router)
```

- [ ] **Шаг 6: Добавить маршрут состояния платежа**

Возвращаться с оплаты можно и не заплатив, поэтому страница результата
спрашивает сервер, а не верит самому факту возврата.

```python
# backend/app/api/routes/payments.py — дописать
from uuid import UUID

from app.schemas.cabinet import PaymentStatusResponse


@router.get(
    "/{payment_id}",
    response_model=PaymentStatusResponse,
    summary="Состояние платежа",
)
async def payment_status(
    payment_id: UUID,
    checkout: CheckoutServiceDep,
) -> PaymentStatusResponse:
    state = await checkout.state(payment_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "payment_not_found", "message": "Платёж не найден"},
        )
    return state
```

```python
# backend/app/services/checkout.py — дописать в CheckoutService
    async def state(self, payment_id: UUID) -> PaymentStatusResponse | None:
        """Состояние платежа для страницы результата."""
        payment = await self._session.get(Payment, payment_id)
        if payment is None:
            return None
        return PaymentStatusResponse(
            status=payment.status.value,
            paid=payment.status is PaymentStatus.SUCCEEDED,
            subscription_url=payment.subscription_url,
        )
```

- [ ] **Шаг 7: Убедиться, что тесты проходят**

Запустить: `.venv/bin/python -m pytest backend/tests -q`
Ожидается: PASS, все тесты.

- [ ] **Шаг 8: Закоммитить**

```bash
.venv/bin/python -m ruff check backend
git add backend/app backend/tests/test_checkout_routes.py
git commit -m "feat: создавать платёж своей кассой и отдавать ссылку на оплату"
```

---

### Задача 6: Вебхук Platega

**Файлы:**
- Изменить: `backend/app/services/checkout.py`
- Изменить: `backend/app/api/routes/payments.py`
- Тест: `backend/tests/test_platega_webhook.py`

**Интерфейсы:**
- Отдаёт: `CheckoutService.confirm(payment_id: str, status_name: str) -> bool` — возвращает `True` только тому вызову, который сам перевёл платёж в `succeeded`; маршрут `POST /api/v1/payments/platega/webhook`.

Вебхук вызывается несколько раз: Platega повторяет доставку, пока не увидит 200. Поэтому подписку продлевает только первый успешный переход, а остальные вызовы отвечают 200 и ничего не делают.

- [ ] **Шаг 1: Написать падающие тесты**

```python
# backend/tests/test_platega_webhook.py
WEBHOOK = "/api/v1/payments/platega/webhook"


def test_webhook_without_credentials_is_rejected(anonymous_client) -> None:
    answer = anonymous_client.post(
        WEBHOOK,
        json={"id": "tx-1", "status": "CONFIRMED"},
        headers={"X-MerchantId": "wrong", "X-Secret": "wrong"},
    )

    assert answer.status_code == 401


def test_empty_verification_ping_is_answered(anonymous_client) -> None:
    """Platega проверяет адрес пустым запросом до первой оплаты."""
    answer = anonymous_client.post(WEBHOOK, content=b"")

    assert answer.status_code == 200
```

- [ ] **Шаг 2: Убедиться, что тесты падают**

Запустить: `.venv/bin/python -m pytest backend/tests/test_platega_webhook.py -q`
Ожидается: FAIL — маршрута нет, 404.

- [ ] **Шаг 3: Написать подтверждение платежа в сервисе**

```python
# backend/app/services/checkout.py — дописать в CheckoutService
SUCCESS_STATUS = "CONFIRMED"


    async def confirm(self, *, provider_payment_id: str, status_name: str) -> bool:
        """Отметить платёж оплаченным. True — только первому, кто это сделал.

        Platega повторяет вебхук, пока не получит 200, поэтому один и тот же
        платёж приходит несколько раз. Подписку продлевает только переход
        pending → succeeded, иначе человек получил бы лишние дни за те же
        деньги.
        """
        statement = select(Payment).where(
            Payment.provider == "platega",
            Payment.provider_payment_id == provider_payment_id,
        )
        payment = await self._session.scalar(statement)
        if payment is None:
            logger.warning("Вебхук про неизвестный платёж")
            return False

        if status_name.upper() != SUCCESS_STATUS:
            if payment.status is PaymentStatus.PENDING:
                payment.status = PaymentStatus.FAILED
                await self._session.commit()
            return False

        if payment.status is not PaymentStatus.PENDING:
            return False

        payment.status = PaymentStatus.SUCCEEDED
        await self._session.commit()
        return True
```

Добавить импорт `from sqlalchemy import select` в начало файла.

- [ ] **Шаг 4: Написать маршрут вебхука**

```python
# backend/app/api/routes/payments.py — дописать
import hmac
import json as jsonlib

from fastapi import Request, Response

from app.api.dependencies import SettingsDep


@router.post(
    "/platega/webhook",
    summary="Уведомление Platega об оплате",
    include_in_schema=False,
)
async def platega_webhook(
    request: Request,
    settings: SettingsDep,
    checkout: CheckoutServiceDep,
) -> Response:
    merchant = request.headers.get("X-MerchantId", "")
    secret = request.headers.get("X-Secret", "")
    body = await request.body()

    # Platega проверяет адрес пустым запросом без заголовков.
    if not merchant and not secret and not body.strip():
        return Response(status_code=status.HTTP_200_OK)

    expected_secret = (
        settings.platega_secret.get_secret_value()
        if settings.platega_secret
        else ""
    )
    # Сравнение с постоянным временем: обычное сравнение строк подсказывает
    # подбирающему, сколько символов он уже угадал.
    authorised = hmac.compare_digest(
        merchant, settings.platega_merchant_id or ""
    ) and hmac.compare_digest(secret, expected_secret)
    if not authorised:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        payload = jsonlib.loads(body)
    except ValueError:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    identifier = str(payload.get("id") or payload.get("Id") or "")
    state = str(payload.get("status") or payload.get("Status") or "")
    if not identifier:
        return Response(status_code=status.HTTP_200_OK)

    # Выдачу подписки подключит задача 7: здесь платёж только фиксируется.
    await checkout.confirm(provider_payment_id=identifier, status_name=state)

    # Ответ всегда 200: иначе Platega будет повторять доставку вечно.
    return Response(status_code=status.HTTP_200_OK)
```

- [ ] **Шаг 5: Убедиться, что тесты проходят**

Запустить: `.venv/bin/python -m pytest backend/tests -q`
Ожидается: PASS.

- [ ] **Шаг 6: Закоммитить**

```bash
.venv/bin/python -m ruff check backend
git add backend/app backend/tests/test_platega_webhook.py
git commit -m "feat: принимать уведомления Platega об оплате"
```

---

### Задача 7: Выдача подписки после оплаты

**Файлы:**
- Изменить: `backend/app/services/checkout.py`
- Тест: `backend/tests/test_checkout_delivery.py`

**Интерфейсы:**
- Использует: `RemnawaveGateway.get_user_by_username`, `.set_expiry`, `.create_user` — уже написаны и работают на контракте панели 3.x.
- Отдаёт: `CheckoutService.deliver(provider_payment_id: str) -> None`; функция `panel_username(email: str) -> str`.

Имя пользователя в панели строится из почты одной и той же функцией — иначе тот же человек при второй покупке получит вторую подписку вместо продления.

- [ ] **Шаг 1: Написать падающие тесты**

```python
# backend/tests/test_checkout_delivery.py
from app.services.checkout import panel_username


def test_username_is_a_pure_function_of_the_email() -> None:
    """Одна почта — одно имя, всегда. Иначе вторая покупка заведёт дубль."""
    assert panel_username("Guest@Example.COM") == panel_username("guest@example.com")


def test_username_survives_awkward_emails() -> None:
    name = panel_username("имя.фамилия+метка@example.com")

    assert name
    assert " " not in name
    assert len(name) <= 64
```

- [ ] **Шаг 2: Убедиться, что тесты падают**

Запустить: `.venv/bin/python -m pytest backend/tests/test_checkout_delivery.py -q`
Ожидается: FAIL — функции `panel_username` нет.

- [ ] **Шаг 3: Написать выдачу**

```python
# backend/app/services/checkout.py — дописать
import hashlib
import re
from datetime import UTC, datetime, timedelta

from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)
from app.services.panel import read_panel_user

USERNAME_LIMIT = 64


def panel_username(email: str) -> str:
    """Имя пользователя панели, выведенное из почты.

    Чистая функция: одна почта всегда даёт одно имя. На это опирается
    продление — по этому имени покупателя ищут в панели, и если имя
    «поплывёт», человек получит вторую подписку вместо продления.
    """
    normalised = email.strip().lower()
    local = normalised.split("@", 1)[0]
    safe = re.sub(r"[^a-z0-9]+", "_", local).strip("_") or "user"
    # Хвост хеша разводит однофамильцев с разных почтовых доменов.
    tail = hashlib.sha256(normalised.encode()).hexdigest()[:8]
    return f"{safe}_{tail}"[:USERNAME_LIMIT]


    async def deliver(self, *, provider_payment_id: str) -> None:
        """Выдать оплаченную подписку в панели.

        Вызывается только после успешного перехода платежа в succeeded.
        Ошибку панели наверх не поднимаем: деньги уже получены, и вебхуку
        надо ответить 200, иначе Platega будет слать его снова. Невыданная
        подписка видна в логе и в статусе платежа.
        """
        statement = select(Payment).where(
            Payment.provider == "platega",
            Payment.provider_payment_id == provider_payment_id,
        )
        payment = await self._session.scalar(statement)
        if payment is None or payment.contact_email is None:
            return

        username = panel_username(payment.contact_email)
        days = payment.period_days or 30

        try:
            async with RemnawaveGateway(self._settings) as panel:
                try:
                    existing = await panel.get_user_by_username(username)
                except RemnawaveUserNotFoundError:
                    await panel.create_user(
                        username=username,
                        expire_at=datetime.now(UTC) + timedelta(days=days),
                        email=payment.contact_email,
                    )
                    return

                panel_user = read_panel_user(existing)
                # Продлеваем от даты окончания, если она ещё не прошла:
                # иначе покупка съедала бы остаток оплаченного срока.
                today = datetime.now(UTC).date()
                base = max(panel_user.expires_at, today)
                await panel.set_expiry(
                    panel_user.id,
                    datetime.combine(
                        base + timedelta(days=days),
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                )
        except RemnawaveUnavailableError:
            logger.exception(
                "Оплата получена, но подписка не выдана: платёж %s", payment.id
            )
```

Ссылку на подписку сохраняем в платеже — её ждёт страница результата. В обеих
ветках, и при создании, и при продлении:

```python
                    created = await panel.create_user(...)
                    payment.subscription_url = str(
                        created.get("subscriptionUrl") or ""
                    ) or None
                    await self._session.commit()
                    return
```

```python
                payment.subscription_url = panel_user.subscription_url
                await self._session.commit()
```

- [ ] **Шаг 4: Подключить выдачу к вебхуку**

```python
# backend/app/api/routes/payments.py — заменить строку про задачу 7
    paid = await checkout.confirm(
        provider_payment_id=identifier, status_name=state
    )
    # Подписку выдаём только тому вызову, который сам перевёл платёж в
    # succeeded: Platega присылает уведомление несколько раз.
    if paid:
        await checkout.deliver(provider_payment_id=identifier)
```

- [ ] **Шаг 5: Убедиться, что тесты проходят**

Запустить: `.venv/bin/python -m pytest backend/tests -q`
Ожидается: PASS.

- [ ] **Шаг 6: Закоммитить**

```bash
.venv/bin/python -m ruff check backend
git add backend/app backend/tests/test_checkout_delivery.py
git commit -m "feat: выдавать подписку в панели после оплаты"
```

---

### Задача 8: Витрина сайта идёт в свою кассу

**Файлы:**
- Изменить: `src/api/shop.ts:75-100`
- Изменить: `src/api/contracts.ts`

**Интерфейсы:**
- Использует: `POST /api/v1/payments/checkout` из задачи 5.

- [ ] **Шаг 1: Переписать создание покупки**

```ts
// src/api/shop.ts — заменить обращение к боту на свою кассу
  async createPurchase(payload: GuestPurchasePayload): Promise<GuestPurchase> {
    /*
     * Раньше покупку создавал бот, и деньги уходили на его мерчант.
     * Теперь платёж создаёт сайт своей кассой; витрину бота продолжаем
     * читать только ради цен, чтобы они не разъехались.
     */
    const response = await fetch("/api/v1/payments/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: payload.email,
        tariffId: payload.tariffId,
        periodDays: payload.periodDays,
      }),
    });

    if (!response.ok) {
      throw new ShopRequestError(FALLBACK_ERROR);
    }

    const raw = (await response.json()) as {
      paymentId: string;
      redirectUrl: string;
    };

    return { token: raw.paymentId, paymentUrl: raw.redirectUrl };
  },
```

- [ ] **Шаг 2: Спрашивать состояние платежа у своего сервера**

Токен покупки теперь наш идентификатор платежа, и у бота его нет — старый
запрос ответил бы «не найдено» и страница ждала бы подтверждения вечно.

```ts
// src/api/shop.ts — заменить getPurchaseStatus
  async getPurchaseStatus(token: string): Promise<GuestPurchaseStatus> {
    const response = await fetch(
      `/api/v1/payments/${encodeURIComponent(token)}`,
    );

    if (!response.ok) {
      throw new ShopRequestError(FALLBACK_ERROR);
    }

    const raw = (await response.json()) as {
      status: string;
      paid: boolean;
      subscriptionUrl?: string | null;
    };

    return {
      status: raw.status,
      done: raw.paid,
      failed: raw.status === "failed" || raw.status === "cancelled",
      subscriptionUrl: raw.subscriptionUrl ?? null,
    };
  },
```

- [ ] **Шаг 3: Проверить сборку**

Запустить: `npm run typecheck && npm run build`
Ожидается: обе команды завершаются без ошибок.

- [ ] **Шаг 4: Закоммитить**

```bash
git add src/api/shop.ts src/api/contracts.ts
git commit -m "feat: продавать через свою кассу, а не через бота"
```

---

### Задача 9: Выкатка и живая проверка

**Файлы:**
- Изменить: `scripts/deploy.sh:66-80`
- Изменить: `.github/workflows/deploy.yml`
- Изменить: `README.md`

- [ ] **Шаг 1: Передавать реквизиты кассы при выкатке**

```bash
# scripts/deploy.sh, рядом с остальными set_env_value
  set_env_value VPANFI_PLATEGA_MERCHANT_ID "${VPANFI_PLATEGA_MERCHANT_ID:-}"
  set_env_value VPANFI_PLATEGA_SECRET "${VPANFI_PLATEGA_SECRET:-}"
```

и прокинуть их в `.github/workflows/deploy.yml` тем же способом, каким туда попадают `VPANFI_REMNAWAVE_*` — внутри SSH-канала, а не в командной строке.

- [ ] **Шаг 2: Записать секреты в GitHub**

```bash
gh secret set VPANFI_PLATEGA_MERCHANT_ID --repo anfixit/vpanfi
gh secret set VPANFI_PLATEGA_SECRET --repo anfixit/vpanfi
```

Пустой секрет оставляет то, что уже лежит в `.env` на сервере, — проверено по `set_env_value`. Заполненный перезаписывает; именно так 21.08.2026 выкатка вернула на сервер устаревший токен панели.

- [ ] **Шаг 3: Дописать README**

Добавить `VPANFI_PLATEGA_MERCHANT_ID` и `VPANFI_PLATEGA_SECRET` в список секретов деплоя и одной фразой сказать, что касса сайта отдельная от кассы бота.

- [ ] **Шаг 4: Выкатить**

```bash
git push origin HEAD
```

Дождаться зелёного CI и деплоя, затем убедиться, что сайт жив:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://vpanfi.su/api/healthz
```

- [ ] **Шаг 5: Поменять адрес вебхука в кабинете Platega**

Это делает владелец сервиса. Сейчас там записано `https://vpanfi.su/api/payments/platega/webhook`, а API сайта живёт под `/api/v1`. Правильный адрес: `https://vpanfi.su/api/v1/payments/platega/webhook`.

- [ ] **Шаг 6: Живая проверка настоящими деньгами**

Купить самый дешёвый период на минимальную сумму и пройти путь до конца. Проверить:

```bash
# ссылка на оплату должна вести на мерчант САЙТА, а не бота
# в адресе pay.platega.io параметр mh обязан быть cf9fe88f-…
ssh yc 'docker exec vpanfi-postgres psql -U vpanfi -d vpanfi -c "select status, amount_kopecks, contact_email, provider_payment_id from payments order by created_at desc limit 3;"'
ssh master 'docker exec remnawave-db psql -U postgres -d postgres -c "select id, username, status, expire_at from users order by created_at desc limit 3;"'
```

Ожидается: платёж в статусе `succeeded`, в панели новый пользователь с нужной датой окончания.

- [ ] **Шаг 7: Повторить вебхук и убедиться, что дней не прибавилось**

Platega доставляет уведомление не один раз. Повторно отправить то же уведомление и убедиться, что `expire_at` в панели не сдвинулся: это главная проверка идемпотентности, и без неё покупатель получал бы лишние дни за те же деньги.
