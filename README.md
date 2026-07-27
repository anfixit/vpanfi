# VPaNfi

VPaNfi is a standalone customer portal for simple internet access, subscription management and device onboarding through the Remnawave API.

## Product idea

The service is designed for people who do not want to understand protocols, configuration links or network terminology. The user sees one clear next action, while the technical details remain hidden behind an advanced section.

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

The web service binds only to `127.0.0.1:8080`. The public domain is served by the Caddy instance already running on the server; VPaNfi never touches ports 80 or 443 itself.

### Publishing a domain

Run the **Publish domain** workflow (`workflow_dispatch`, default `vpanfi.su`). It is manual on purpose: it is the only workflow that touches the shared Caddy configuration.

The workflow refuses to continue unless the domain already resolves to this server, attaches `vpanfi-web` to the proxy network so Caddy can reach it by name, backs the Caddyfile up, appends a single site block, validates it and asks Caddy to reload. Caddy is never restarted, and a failed validation or reload restores the previous file before exiting. It then sets `VPANFI_FRONTEND_ORIGIN` in `/opt/vpanfi/.env` and verifies the domain end to end.

`scripts/deploy.sh` reattaches `vpanfi-web` to that network on every release, because Compose drops the extra network whenever it recreates the container.

## Security

- `.env` is never committed; `.env.example` documents every variable.
- The API refuses to start in production with the placeholder JWT secret, a secret shorter than 32 characters, or debug mode enabled.
- Refresh tokens live in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie scoped to the auth path; access tokens stay in memory only.
- CORS accepts only the configured origins, and both nginx and the API send CSP and the usual hardening headers.
- The Remnawave adapter is isolated in `backend/app/integrations/remnawave/` and is never reached without real credentials.

## Status

Active development. The UI runs on demonstration data until the backend persistence and Remnawave credentials are connected.
