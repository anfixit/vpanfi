# Рефералка: мост к боту продаж. План реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Друг, пришедший по ссылке клиента, может купить подписку не только на сайте, но и в боте продаж, и награды начисляются по тем же правилам.

**Architecture:** На странице покупки у пришедшего по приглашению появляется кнопка «Купить в Telegram» со ссылкой `https://t.me/VPaNfi_bot?start=<referral_code пригласившего в боте>`. Бот (Bedolaga) при регистрации нового человека сам записывает `referred_by_id`. Сайт раз в полчаса читает через Web API бота пользователей с `referred_by_id` и их транзакции типа `subscription_payment` и заводит награды в своей таблице `referral_rewards` по общим правилам. Денежная механика бота обезврежена настройками: `REFERRAL_REWARD_SCHEME=levels` при пустой таблице уровней и `REFERRAL_NOTIFICATIONS_ENABLED=false`.

**Tech Stack:** FastAPI, SQLAlchemy async + Alembic, httpx, pytest + respx, React + TypeScript.

## Global Constraints

- Правила наград общие с сайтом и берутся из тех же настроек: другу `referral_friend_days`, пригласившему `referral_inviter_days` за первую покупку друга, пригласившему `referral_renewal_days` за первое продление не раньше чем через `referral_renewal_min_gap_days`; потолок `referral_monthly_cap`; правила приёма пригласившего те же (`OOO_SINERGIYA_*`, статус ACTIVE, теги PAID/SVOI).
- Покупкой в боте считается завершённая транзакция `type == "subscription_payment"`. Пополнение баланса (`deposit`) наградой не является.
- Людям из бота дни добавляются ТОЛЬКО через Bedolaga (`POST /subscriptions/{id}/extend`), и другу тоже.
- Мост включается отдельной настройкой `VPANFI_REFERRAL_BOT_ENABLED` (по умолчанию `false`) и работает только при `referral_enabled` и `is_bedolaga_configured`. Выключенный, он не делает ни одного запроса.
- Тестовой базы нет: логика за протоколом хранилища, тесты на подделках; HTTP через `respx`. Реальные формы ответов API приведены в заданиях, их не выдумывать.
- Сбой бота или панели никогда не ломает покупку на сайте и не роняет фоновую задачу.
- Русские тексты на «Вы», без символа U+2014 в новых строках; комментарии в стиле соседнего кода. Команды Python всегда с `PYTHONPATH=backend`.
- Защита от двойной выдачи держится на одном процессе uvicorn (см. README); новые пути обязаны идти через тот же `process()` с замком.

---

### Task 1: Основа. Модель, настройки, шлюз

**Files:** `backend/app/models/billing.py`, `backend/alembic/versions/20260919_0008_referral_bot.py`, `backend/app/core/config.py`, `docker-compose.yml`, `.github/workflows/deploy.yml`, `scripts/deploy.sh`, `.env.example`, `README.md`, `backend/app/integrations/bedolaga/client.py`, `backend/app/integrations/remnawave/client.py`, тесты `test_billing_model.py`, `test_config.py`, `test_bedolaga_gateway.py`, `test_remnawave_gateway.py`.

**Interfaces (Produces):**
- `ReferralReward.source: str` (`String(8)`, NOT NULL, по умолчанию `site`; значения `site`, `bot`), `payment_id` становится nullable, `friend_telegram_id: int | None` (BigInteger), `bot_transaction_id: int | None` (Integer, unique). Для друга из бота `friend_email` хранит ключ `tg:<telegram_id>`: существующая уникальность (`friend_email`, `kind`) продолжает работать.
- Настройки: `referral_bot_enabled: bool = False`, `referral_bot_sync_minutes: int = 30`, `telegram_sales_bot_username: str = "VPaNfi_bot"`. `VPANFI_REFERRAL_BOT_ENABLED` проводится через четыре места (в workflow из `vars`).
- `BedolagaGateway`: `@dataclass(frozen=True) class BotUser: id: int; telegram_id: int | None; referral_code: str | None; referred_by_id: int | None; has_had_paid_subscription: bool`; `async def user_by_telegram_id(tg: int) -> BotUser`; `async def user_by_id(user_id: int) -> BotUser`; `async def list_users(*, limit: int = 200, offset: int = 0) -> tuple[list[BotUser], int]`; `@dataclass(frozen=True) class BotPurchase: id: int; user_id: int; completed_at: datetime`; `async def purchases(user_id: int) -> list[BotPurchase]` (GET `/transactions` с `user_id`, `type=subscription_payment`, `is_completed=true`, все страницы, по возрастанию `completed_at`). Существующие методы не меняются.
- `RemnawaveGateway.get_user_by_telegram_id(tg: int) -> Mapping[str, Any]` (панель: `GET /api/users/by-telegram-id/{id}`, ответ может быть списком: брать первого ACTIVE, иначе первого; пусто даёт `RemnawaveUserNotFoundError`).

### Task 2: Ядро. Синхронизация с ботом и выдача другу через бота

**Files:** `backend/app/services/referral.py`, `backend/tests/test_referral.py` (или новый `test_referral_bot.py`).

**Interfaces:**
- Хранилище: `async def bot_reward_exists(self, transaction_id: int) -> bool`.
- `ReferralService.sync_bot(self) -> int`: обходит `list_users` постранично, берёт людей с `referred_by_id` и `has_had_paid_subscription`; по каждому берёт `purchases`; первая покупка даёт награду `kind="first"`, `source="bot"`; покупка не раньше чем через разрыв после первой награды (`granted`/`held`) даёт `kind="renewal"`. Пригласивший: `user_by_id(referred_by_id)` → `telegram_id` → панель `get_user_by_telegram_id` → общие правила приёма и потолок. Возвращает число заведённых наград и ставит каждую в обработку через переданный планировщик. Ничего не бросает наружу; сбой на одном человеке не прерывает обход.
- `process()`: для `source == "bot"` дни другу идут через `subscription_id_by_telegram_id(friend_telegram_id)` + `extend`, без панели; остальное без изменений (замок, сохранение после каждой выдачи, попытки, итоговое уведомление).

### Task 3: Проводка. Фон, ссылка в бота, страница покупки

**Files:** `backend/app/services/referral_wiring.py`, `backend/app/main.py`, `backend/app/api/routes/payments.py` или новый `routes/referral.py`, `backend/app/api/router.py`, `src/referral.ts`, `src/api/shop.ts` или `client.ts`, `src/pages/BuyPage.tsx`, стили, тесты маршрута.

**Interfaces:**
- Фон: внутри существующего цикла `_nagrady` раз в `referral_bot_sync_minutes` зовётся `sinhronizirovat_bota()` (своя сессия, не бросает).
- Открытый маршрут `GET /api/v1/referral/invite?ref=<код>` отвечает `{"telegramUrl": str | null}`: код проверяется `normalize_code`, пригласивший ищется в панели, при наличии `telegramId` берётся `referral_code` из бота, ссылка `https://t.me/<telegram_sales_bot_username>?start=<referral_code>`. На любую ошибку и любой негодный код ответ одинаковый: `{"telegramUrl": null}` с кодом 200. Кэш в памяти на 10 минут по коду, не больше 500 записей.
- Страница покупки: у пришедшего по приглашению под строкой про 15 дней появляется вторая кнопка «Купить в Telegram» (только когда `telegramUrl` есть), с подписью «Для Telegram нужен работающий VPN. Награда придёт и там.»
