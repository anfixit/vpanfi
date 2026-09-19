# Рефералка через сайт: план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Клиент делится ссылкой `vpanfi.su/?ref=<имя учётки в панели>`; друг покупает на сайте, и после его первой оплаты оба получают по 30 дней подписки.

**Architecture:** Код приглашения это имя учётки в панели Remnawave, поэтому пригласивший находится одним запросом в панель. Сайт хранит код у платежа, после выдачи подписки заводит запись награды и отдаёт её обработчику: другу дни через панель, пригласившему через Bedolaga (если у учётки есть `telegramId`) или через панель. Сбой не ломает выдачу подписки: запись остаётся в ожидании, фоновая задача повторяет.

**Tech Stack:** FastAPI, SQLAlchemy async + Alembic (Postgres), httpx, pytest + respx, React + TypeScript (Vite).

## Global Constraints

- Замысел: `docs/superpowers/specs/2026-09-19-referral-design.md`. Награда: другу 30 дней, пригласившему 30 дней, разово за первую оплату друга.
- Рефералка выключена по умолчанию: `VPANFI_REFERRAL_ENABLED=false`. Выключенная, она не меняет ни одного существующего поведения, и все прежние тесты зелёные.
- Сбой панели или Bedolaga в рефералке никогда не ломает выдачу оплаченной подписки и ответ вебхуку.
- Тесты не используют базу данных: в проекте нет тестовой БД (модели на `PGUUID` и перечислениях Postgres). Логика рефералки живёт за протоколом хранилища, тесты дают поддельное хранилище в памяти. HTTP подделывается через `respx`.
- Секреты не попадают в репозиторий и журналы. Ключ Bedolaga приходит из `VPANFI_BEDOLAGA_API_TOKEN`.
- Новая настройка проводится через четыре места: `backend/app/core/config.py`, `docker-compose.yml`, `.github/workflows/*deploy*` (запись в `.env` сервера), `README`/`.env.example`.
- Тексты для людей на русском, на «Вы», без длинных тире (символа U+2014 в новых строках быть не должно). Комментарии в коде на русском, в стиле соседнего кода.
- Перед коммитом проходит хук репозитория (ruff, pytest, типы фронта). Коммиты на русском, в конце строка `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Учётки `OOO_SINERGIYA_*`, теги `TRIAL`, `UNPAID` и выключенные учётки как пригласившие не принимаются. Тег `SVOI`: другу бонус положен, пригласившему дни не начисляются.

---

### Task 1: Настройки, модель и миграция

**Files:**
- Modify: `backend/app/core/config.py` (рядом с `max_support_url`)
- Modify: `backend/app/models/billing.py` (поле у `Payment`, новая модель)
- Modify: `backend/app/models/__init__.py` (экспорт)
- Create: `backend/alembic/versions/20260919_0006_referral.py`
- Modify: `docker-compose.yml`, workflow деплоя, `.env.example`
- Test: `backend/tests/test_config.py`, `backend/tests/test_billing_model.py`

**Interfaces:**
- Produces, настройки `Settings`: `referral_enabled: bool = False`, `referral_friend_days: int = 30`, `referral_inviter_days: int = 30`, `referral_monthly_cap: int = 5`, `referral_retry_minutes: int = 30`, `bedolaga_api_url: str = "https://vpanfibot.ru/api"`, `bedolaga_api_token: SecretStr | None = None`, свойство `is_bedolaga_configured -> bool`.
- Produces, модель: `Payment.referral_code: Mapped[str | None]` (`String(64)`, индекс).
- Produces, модель `ReferralReward` (таблица `referral_rewards`): `id: UUID`, `payment_id: UUID` (FK `payments.id`, unique), `friend_email: str` (String(320), unique), `friend_panel_user_id: int | None`, `inviter_username: str` (String(64), index), `inviter_panel_user_id: int`, `inviter_telegram_id: int | None`, `friend_days: int`, `inviter_days: int`, `status: str` (String(16): `pending`, `granted`, `held`, `failed`, `rejected`), `friend_granted_at`, `inviter_granted_at` (datetime | None), `attempts: int = 0`, `last_error: str | None` (String(500)), плюс `TimestampMixin`.
- Статус строкой, а не перечислением Postgres: новое значение не потребует миграции типа.

- [ ] **Step 1:** Тесты в `test_config.py`: значения по умолчанию перечисленных настроек; `VPANFI_REFERRAL_ENABLED=true` читается; `is_bedolaga_configured` ложно без ключа и истинно с ключом. Тест в `test_billing_model.py`: у `ReferralReward.__table__` есть уникальные ограничения на `payment_id` и `friend_email`, у `Payment` есть колонка `referral_code`.
- [ ] **Step 2:** Запустить, убедиться, что падают.
- [ ] **Step 3:** Реализовать настройки, модель, миграцию `0006` (`down_revision` = последняя `20260831_0005`), с `downgrade`. Провести настройки через compose, workflow и `.env.example` по образцу `VPANFI_TELEGRAM_SUPPORT_URL` и ключей Platega.
- [ ] **Step 4:** `ruff check`, `pytest`, `alembic upgrade head --sql` без ошибок (офлайн-режим, база не нужна).
- [ ] **Step 5:** Коммит `Рефералка: настройки, поле кода у платежа и таблица наград`.

### Task 2: Шлюз Bedolaga

**Files:**
- Create: `backend/app/integrations/bedolaga/__init__.py`, `backend/app/integrations/bedolaga/client.py`
- Test: `backend/tests/test_bedolaga_gateway.py`

**Interfaces:**
- Produces: `class BedolagaGateway` с `async with`, как `RemnawaveGateway`. Исключения `BedolagaNotConfiguredError`, `BedolagaUnavailableError`, `BedolagaUserNotFoundError(LookupError)`.
- `async def subscription_id_by_telegram_id(self, telegram_id: int) -> int`: `GET {url}/users/by-telegram-id/{id}`, заголовок `X-API-Key`. Берёт `subscription.id`; если `subscription` пуст, берёт из `subscriptions` платную (`is_trial` ложно) с самым поздним `end_date`. Нет ни одной: `BedolagaUserNotFoundError`. 404: `BedolagaUserNotFoundError`.
- `async def extend(self, subscription_id: int, days: int) -> None`: `POST {url}/subscriptions/{id}/extend` с телом `{"days": days}`. Любой ответ не 2xx и сетевые ошибки: `BedolagaUnavailableError` с кодом ответа в тексте, без тела ответа и без ключа.
- Таймаут 15 секунд, без повторов внутри шлюза: `extend` не идемпотентен, повтор решает обработчик наград.

- [ ] **Step 1:** Тесты на `respx`: успешный поиск, выбор платной подписки из списка, 404, 500, сетевой сбой, успешный `extend` с проверкой тела и заголовка, 500 на `extend`, отсутствие ключа даёт `BedolagaNotConfiguredError`, ключ не встречается в тексте исключений.
- [ ] **Step 2-4:** Красный прогон, реализация, зелёный прогон и `ruff`.
- [ ] **Step 5:** Коммит `Рефералка: шлюз к API бота продаж`.

### Task 3: Ядро рефералки

**Files:**
- Create: `backend/app/services/referral.py`
- Test: `backend/tests/test_referral.py`

**Interfaces:**
- Consumes: настройки и `ReferralReward` из Task 1, `BedolagaGateway` из Task 2, `RemnawaveGateway.get_user_by_username/get_user_by_id/set_expiry`, `read_panel_user` из `app/services/panel.py`.
- Produces: `CODE_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")`, `def normalize_code(raw: str | None) -> str | None` (обрезает пробелы, отбрасывает не подходящее под `CODE_RE`).
- Produces: протокол `RewardStore` с методами `async def has_earlier_paid(self, email: str, payment_id: UUID) -> bool`, `async def reward_exists(self, payment_id: UUID, email: str) -> bool`, `async def add(self, reward: ReferralReward) -> None`, `async def granted_in_last_days(self, inviter_username: str, days: int) -> int`, `async def due(self, limit: int) -> list[ReferralReward]`, `async def save(self) -> None`; и `class SqlRewardStore(RewardStore)` поверх `AsyncSession`.
- Produces: `class ReferralService(settings, store, panel_factory, bedolaga_factory)`:
  - `async def register(self, *, payment: Payment, friend_panel_user_id: int | None, friend_was_paid: bool) -> ReferralReward | None`. Возвращает `None`, если рефералка выключена, кода нет, у почты уже была успешная оплата, друг уже был `PAID`, награда по платежу или почте уже есть, пригласивший не найден или не принят (см. Global Constraints), код равен имени учётки самого друга. Для `SVOI` пишет `inviter_days=0`. При достигнутом потолке за 30 дней пишет статус `held` (другу дни всё равно выдаются).
  - `async def process(self, reward: ReferralReward) -> None`. Выдаёт то, что ещё не выдано: другу через панель от `max(срок, сегодня)`, пригласившему через Bedolaga при `inviter_telegram_id`, иначе через панель. Каждая удачная выдача сразу ставит свою отметку времени и сохраняется, чтобы повтор не выдал дни дважды. Статус `held` выдаёт только другу. Ошибка увеличивает `attempts`, пишет `last_error` (до 500 символов), после 10 попыток статус `failed`. Обе выдачи сделаны: `granted`.
  - `async def retry_due(self, limit: int = 20) -> int`: обходит `store.due`, возвращает число обработанных.
  - Исключения наружу не выходят ни из одного метода: они пишутся в журнал.

- [ ] **Step 1:** Тесты с поддельным хранилищем и поддельными шлюзами (классы с теми же методами, считающие вызовы). Случаи: выключено; нет кода; не первая оплата; друг уже был `PAID`; свой код; пригласивший не найден; `TRIAL`/`UNPAID`/выключенный/`OOO_SINERGIYA_3` отклоняются; `SVOI` даёт другу дни, пригласившему ноль; клиент бота идёт через Bedolaga, клиент сайта через панель; продление считается от позднейшей из дат; потолок даёт `held`, друг при этом получает дни; сбой Bedolaga оставляет `pending` с отметкой у друга, повторный `process` не выдаёт другу дни второй раз; десять сбоев дают `failed`; повторный `register` по тому же платежу возвращает `None`.
- [ ] **Step 2-4:** Красный прогон, реализация, зелёный прогон и `ruff`.
- [ ] **Step 5:** Коммит `Рефералка: правила начисления и обработчик наград`.

### Task 4: Встраивание в оплату и фон

**Files:**
- Modify: `backend/app/schemas/cabinet.py` (`CheckoutRequest`: необязательное поле `ref`, alias `ref`, длина до 64)
- Modify: `backend/app/api/routes/payments.py` (передать `ref` в `start`)
- Modify: `backend/app/services/checkout.py` (`start(..., referral_code=None)` пишет `normalize_code(...)` в платёж; `deliver` после успешной выдачи зовёт рефералку)
- Modify: `backend/app/api/dependencies.py` (сборка `ReferralService`)
- Modify: `backend/app/main.py` (фоновая задача повторов каждые `referral_retry_minutes`)
- Modify: `backend/app/services/notify.py` (сообщение Анфисе о награде и о `held`)
- Test: `backend/tests/test_checkout_routes.py`, `backend/tests/test_checkout_delivery.py`, `backend/tests/test_notify.py`

**Interfaces:**
- Consumes: `normalize_code`, `ReferralService.register/process/retry_due`.
- В `deliver`: в ветке новой учётки `friend_was_paid=False`, `friend_panel_user_id=created["id"]`; в ветке продления `friend_was_paid = (тег учётки до покупки == "PAID")`, читать тег надо до `set_expiry`. Вызов рефералки обёрнут в `try/except Exception` с записью в журнал и стоит после письма покупателю, чтобы человек получил ссылку раньше любых наград.
- Produces: `def nagrada_soobshchenie(*, friend_email: str, inviter_username: str, status: str) -> str` в `notify.py`.

- [ ] **Step 1:** Тесты: запрос с `ref` проходит схему, без `ref` тоже; мусорный `ref` не роняет запрос и пишет `None`; исходник `deliver` зовёт рефералку после `_notify` (в стиле соседних тестов через `inspect.getsource`); исключение из рефералки не выходит из `deliver`; текст сообщения Анфисе без длинных тире.
- [ ] **Step 2-4:** Красный прогон, реализация, зелёный прогон всего набора и `ruff`.
- [ ] **Step 5:** Коммит `Рефералка: код в оплате, начисление после выдачи и повторы в фоне`.

### Task 5: Кабинет и фронт

**Files:**
- Modify: `backend/app/api/routes/cabinet.py`, `backend/app/schemas/cabinet.py`, `backend/app/services/cabinet.py` (или новый `GET /cabinet/referral`)
- Create: `src/referral.ts` (чтение `?ref`, хранение 30 дней, выдача кода)
- Modify: `src/App.tsx` или `src/main.tsx` (захват кода при загрузке любой страницы), `src/pages/BuyPage.tsx`, `src/api/client.ts`, `src/api/contracts.ts`, `src/pages/DashboardPage.tsx` (карточка «Пригласить друга»), стили
- Test: `backend/tests/test_cabinet_access.py` (или новый `test_referral_routes.py`)

**Interfaces:**
- Produces: `GET /cabinet/referral` для вошедшего: `{"enabled": bool, "link": str | null, "friends": int, "daysEarned": int, "friendDays": int, "inviterDays": int}`. `link` есть, если у человека привязана учётка панели: `https://vpanfi.su/?ref=<remnawave_username>`. Счётчики из `referral_rewards` по `inviter_username`.
- Produces, фронт: `captureReferral(): void`, `currentReferral(): string | null`, `clearReferral(): void` в `src/referral.ts`. Хранилище `localStorage`, ключ `vpanfi.ref`, значение `{code, savedAt}`, срок 30 дней, все обращения в `try/catch`.
- Страница покупки шлёт `ref` в создание платежа и показывает строку «Вы пришли по приглашению. К первой покупке добавится 30 дней.» только когда код есть. После успешной оплаты код стирается.
- Карточка в кабинете: заголовок «Пригласите друга», текст «Друг оплатит подписку по Вашей ссылке, и каждый из Вас получит по 30 дней.», ссылка, кнопка «Скопировать», счётчики. При `enabled=false` карточки нет.

- [ ] **Step 1:** Бэкенд-тесты маршрута: без входа 401, выключено даёт `enabled=false` без ссылки, включено даёт ссылку с именем учётки и счётчики из поддельного хранилища.
- [ ] **Step 2-4:** Красный прогон, реализация бэкенда и фронта, `pytest`, `ruff`, `npx tsc -b`, `npm run build`.
- [ ] **Step 5:** Проверка глазами в dev-сервере: `/?ref=test_user` затем `/buy` показывает строку; кабинет в демо-режиме показывает карточку. Коммит `Рефералка: ссылка в кабинете и код приглашения на странице покупки`.

### Task 6: Совпадение устройств и ручное решение

**Files:**
- Modify: `backend/app/services/referral.py` (`async def device_overlaps(self) -> list[ReferralReward]`)
- Modify: `backend/app/main.py` (раз в сутки), `backend/app/services/notify.py`
- Modify: `backend/app/api/routes/admin.py`, `backend/app/services/admin.py` (`POST /admin/referral-rewards/{id}/release` и `/reject`)
- Test: `backend/tests/test_referral.py`, `backend/tests/test_admin_access.py`

**Interfaces:**
- Consumes: `RemnawaveGateway.list_devices(user_id)`; поле `hwid` у устройства.
- `device_overlaps` берёт награды за последние 2 суток, у которых есть `friend_panel_user_id`, сравнивает множества `hwid` друга и пригласившего; совпадение даёт строку Анфисе: почта друга, имя пригласившего, число общих устройств. Автоматических наказаний нет.
- `release` переводит `held` в `pending` и сразу зовёт `process`; `reject` ставит `rejected`. Оба только для администратора, чужой статус даёт 409.

- [ ] **Step 1-4:** Тесты (совпадение есть, нет, панель недоступна не роняет обход; release/reject и права), реализация, зелёный прогон.
- [ ] **Step 5:** Коммит `Рефералка: сверка устройств и ручное решение по придержанным наградам`.

---

## После кода (делает ведущий, не субагенты)

1. Анфиса добавляет в GitHub Secrets сайта `VPANFI_BEDOLAGA_API_TOKEN` (значение `WEB_API_DEFAULT_TOKEN` бота). Проверка доступа с сервера сайта: `GET https://vpanfibot.ru/api/users/by-telegram-id/<id>` отвечает 200.
2. Деплой с `VPANFI_REFERRAL_ENABLED=false`, проверка, что покупка работает как раньше.
3. Включение, живая проверка: покупка по ссылке клиента бота и по ссылке клиента сайта, сроки в панели выросли у обоих, запись `granted`.
4. База знаний Артёма (`~/dev/vpanfi-support/knowledge`), строка в `announce` подписки с `{{USERNAME}}`, пост в канал. Тексты согласуются с Анфисой.
