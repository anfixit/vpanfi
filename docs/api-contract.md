# API-контракт VPaNfi

Префикс: `/api/v1`.

## Сессия и аккаунт

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/oauth/{provider}/start`
- `GET /auth/oauth/{provider}/callback`
- `POST /auth/identities/{provider}/link`
- `DELETE /auth/identities/{provider}`
- `GET /me`
- `PATCH /me`

Провайдеры: `yandex`, `vk`, `telegram`.

## Подписка

- `GET /subscription`
- `GET /subscription/countries`
- `POST /subscription/refresh`
- `GET /subscription/connection`
- `POST /subscription/connection/rotate`

Ответ интерфейса не должен раскрывать токен Remnawave. Сервер возвращает только нужные пользователю поля и короткоживущие ссылки.

## Устройства

- `GET /devices`
- `PATCH /devices/{id}`
- `DELETE /devices/{id}`
- `POST /device-slots/checkout`

Удаление привязки требует повторного подтверждения, а частота операций ограничивается.

## Тарифы и платежи

- `GET /plans`
- `POST /payments/sbp/checkout`
- `POST /payments/sbp/webhook`
- `GET /payments`
- `GET /balance`
- `POST /balance/top-up`
- `PATCH /subscription/auto-renew`

Тарифы первого релиза:

| Срок | Цена | Устройства |
|---|---:|---:|
| 1 месяц | 300 ₽ | 3 |
| 3 месяца | 800 ₽ | 3 |
| 6 месяцев | 1 500 ₽ | 3 |
| Дополнительное место | 100 ₽ в месяц | +1 |

Пробный период: 7 дней. Продление суммирует дни.

## Поддержка

- `GET /support/conversations/current`
- `POST /support/messages`
- `POST /support/tickets`
- `POST /support/handoff`

AI-адаптер получает только минимально необходимый контекст. Передача персональных данных и ключей подключения запрещена. При низкой уверенности или платёжных вопросах диалог передаётся человеку.

## Администрирование

- `GET /admin/summary`
- `GET /admin/users`
- `GET /admin/users/{id}`
- `POST /admin/users/{id}/subscription/extend`
- `POST /admin/users/{id}/device-slots`
- `GET /admin/payments`
- `GET /admin/support`
- `GET /admin/audit`

Все методы требуют отдельной административной роли и пишут audit event.
