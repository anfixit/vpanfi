# VPaNfi

VPaNfi is a standalone customer portal for simple internet access, subscription management and device onboarding through the Remnawave API.

## Product idea

The service is designed for people who do not want to understand protocols, configuration links or network terminology. The user sees one clear next action, while the technical details remain hidden behind an advanced section.

The brand mascot is Анфиса, a friendly monkey travelling through the internet jungle.

## Planned areas

- public landing page with tariffs and a seven-day trial;
- authentication with password, Yandex, VK and Telegram;
- personal cabinet with subscription, traffic, countries and devices;
- connection wizard for Android, iOS, Windows, macOS, Linux and TV platforms;
- QR onboarding and alternative applications;
- SBP payments, balance, auto-renewal and payment history;
- Telegram support, contact form and future AI chat;
- compact administration panel;
- isolated Remnawave API adapter;
- Docker deployment through GitHub Actions.

## Stack

- React 19
- TypeScript
- Vite
- FastAPI
- PostgreSQL
- Redis
- native CSS design system
- Docker, Compose and Nginx

## Production deployment

Production is deployed automatically after a successful CI run on `main`.

The workflow connects to the server with the dedicated `deploy` account, synchronizes `/opt/vpanfi` with the current `main` branch, validates the Compose configuration, builds fresh images, starts the stack and verifies the local health endpoint. The deploy script preserves the production `.env` file and rolls back to the previous Git commit if startup or health checks fail.

Required GitHub Actions secrets:

- `DEPLOY_HOST`
- `DEPLOY_PORT`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `DEPLOY_HOST_FINGERPRINT`

The web service binds only to `127.0.0.1:8080`; the public domain is published separately through the server reverse proxy.

## Status

Active development. The UI currently uses demonstration data until the backend and Remnawave credentials are connected.
