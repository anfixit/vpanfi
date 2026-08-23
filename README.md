# VPaNfi

VPaNfi is a standalone customer portal for simple internet access, subscription management and device onboarding through the Remnawave API.

## Product idea

The service is designed for people who do not want to understand protocols, configuration links or network terminology. The user sees one clear next action, while the technical details remain hidden behind an advanced section.

## How the pieces fit together

The Remnawave panel owns every subscription. The website and the Telegram
bot are two equal interfaces to it — neither keeps its own copy and
neither is a source of truth. The cabinet stores only which panel user an
account belongs to, and reads everything else from the panel on request.

A subscription reaches the cabinet by exactly one route: its own
subscription link, which the bot sends to the customer. Signing in with
Telegram says who a person is; it says nothing about which subscription
is theirs, and the two are deliberately never joined. The panel is
therefore never queried by Telegram identity.

The brand mascot is Анфиса, a friendly monkey travelling through the internet jungle.

## Mascot

The approved reference lives in `design/mascot/reference.png`, with a contact sheet of every state in `design/mascot/reference-sheet.png`.

Ten states ship in `public/mascots` as AVIF with a WebP fallback: `greeting`, `connected`, `phone`, `laptop`, `support`, `error`, `qr`, `payment-success`, `subscription-active`, `explorer`.

Use them through `src/components/Mascot.tsx` — never an emoji, an ASCII drawing or a redrawn character:

```tsx
<Mascot variant="connected" className="card-mascot" decorative />
```

The component reserves its box before the image loads, so a mascot never shifts the layout, and it loads lazily unless `loading="eager"` is passed for above-the-fold art.

## Stack

- React 19
- TypeScript
- Vite
- FastAPI
- PostgreSQL
- Redis
- native CSS design system
- Docker, Compose and Nginx

## Local development

```bash
npm install --no-audit --no-fund
npm run dev
```

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e "backend[dev]"
.venv/bin/python -m pytest -q backend/tests
```

A hook runs those same checks before every commit, so a failing lint never
reaches CI. Enable it once per clone:

```bash
git config core.hooksPath scripts/hooks
```

It checks only what the commit touches — a documentation change waits for
nothing — and `git commit --no-verify` still lets a deliberate exception
through.

Checks that must pass before pushing:

```bash
npm run typecheck && npm run build
ruff check backend && pytest -q backend/tests
docker compose config --quiet && docker compose build
```

## Demo mode

With `VITE_DEMO_MODE=true` the cabinet serves its own deterministic data and marks itself with a visible "Демо-режим" badge.

Demo mode never simulates a real payment. The payment button previews the success screen under a "Демонстрация" label and states plainly that no money moved. Actions that need a service which is not connected yet — payments, balance top-up, profile writes, admin screens — explain what is missing instead of doing nothing.

## Production deployment

`.github/workflows/ci.yml` runs the frontend, backend and container jobs on every push and pull request. On a push to `main` the `deploy` job runs only after all three succeed; it calls `.github/workflows/deploy.yml`, which is also available manually through **Run workflow** (`workflow_dispatch`). Concurrent production deploys queue instead of overlapping.

The deploy job verifies the server host key against `DEPLOY_HOST_FINGERPRINT` before connecting — it pins whichever offered key matches the recorded fingerprint and fails if none does. It then runs `scripts/remote-bootstrap.sh` over SSH, which clones or updates `/opt/vpanfi` and hands over to `scripts/deploy.sh`.

`scripts/deploy.sh` preserves the production `.env`, generates one on first deploy, validates the Compose configuration, builds fresh images, starts the stack, waits for both `/healthz` and `/api/healthz`, and rolls back to the previous commit if anything fails. Every run finishes by printing the deployed commit, the Compose state, both health checks and the status of the neighbouring Caddy and Remnawave containers.

Required GitHub Actions secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_HOST_FINGERPRINT` — from `ssh-keyscan -p PORT HOST | ssh-keygen -lf -`

Optional secrets, applied to `/opt/vpanfi/.env` on every deploy. Leave them unset to keep whatever the server already has:

- `VPANFI_REMNAWAVE_BASE_URL` — panel base URL, no trailing slash
- `VPANFI_REMNAWAVE_API_TOKEN` — panel API token
- `VPANFI_PLATEGA_MERCHANT_ID` — the site's own Platega merchant, separate from the bot's
- `VPANFI_PLATEGA_SECRET` — its API key

The site sells through its own cash desk: the bot has a different merchant,
and mixing them would send the money to the wrong account. Platega delivers
its notifications to `https://<domain>/api/v1/payments/platega/webhook`, and
the address is registered in the Platega dashboard, not in this repository.

Optional repository **variable**:

- `VITE_DEMO_MODE` — set to `false` once the panel is connected

They travel inside the SSH channel rather than on the remote command line, so they never appear in the server's process list or in a workflow log.

The web service binds only to `127.0.0.1:8080`. The public domain is served by the Caddy instance already running on the server; VPaNfi never touches ports 80 or 443 itself.

### Publishing a domain

Run the **Publish domain** workflow (`workflow_dispatch`, default `vpanfi.su`). It is manual on purpose: it is the only workflow that touches the shared Caddy configuration.

The workflow refuses to continue unless the domain already resolves to this server, attaches `vpanfi-web` to the proxy network so Caddy can reach it by name, backs the Caddyfile up, appends a single site block, validates it and asks Caddy to reload. Caddy is never restarted, and a failed validation or reload restores the previous file before exiting. It then sets `VPANFI_FRONTEND_ORIGIN` in `/opt/vpanfi/.env` and verifies the domain end to end.

`scripts/deploy.sh` reattaches `vpanfi-web` to that network on every release, because Compose drops the extra network whenever it recreates the container.

## Signing in

Password sign-in always works. Telegram, VK and Yandex are additional
ways to sign in, and each is enabled independently by its credentials — a
provider without them is simply not offered on the sign-in screen,
because a button that cannot work is worse than no button.

These providers only establish identity. They never bring a subscription
with them: that arrives solely through the subscription link. The same
mechanism serves the profile, where linking a provider and signing in
with it are one operation, differing only in whether someone is already
signed in.

The Telegram **login bot is a separate thing from the bot that sells
subscriptions**, which is why its settings are named for logging in. It
may be a dedicated bot; nothing in the cabinet assumes otherwise.

| Provider | What it needs |
|---|---|
| Telegram | `VPANFI_TELEGRAM_LOGIN_BOT_TOKEN` secret, `VPANFI_TELEGRAM_LOGIN_BOT_USERNAME` variable, and the domain registered through BotFather `/setdomain` |
| VK | a VK ID application: `VPANFI_VK_CLIENT_ID` variable and `VPANFI_VK_CLIENT_SECRET` secret |
| Yandex | a Yandex OAuth application: `VPANFI_YANDEX_CLIENT_ID` variable and `VPANFI_YANDEX_CLIENT_SECRET` secret |

VK and Yandex must be told to return the visitor to
`https://<domain>/auth/callback`.

Telegram does not use OAuth: its widget signs the user data in the
browser and the server verifies that signature with the login bot token.
Without that check anyone could post someone else's Telegram id and sign
in as them, so an unsigned, tampered or stale payload is rejected.

## Security

- `.env` is never committed; `.env.example` documents every variable.
- The API refuses to start in production with the placeholder JWT secret, a secret shorter than 32 characters, or debug mode enabled.
- Refresh tokens live in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie scoped to the auth path; access tokens stay in memory only.
- CORS accepts only the configured origins, and both nginx and the API send CSP and the usual hardening headers.
- The Remnawave adapter is isolated in `backend/app/integrations/remnawave/` and is never reached without real credentials.

## Status

Active development. The UI runs on demonstration data until the backend persistence and Remnawave credentials are connected.
