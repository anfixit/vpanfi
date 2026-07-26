#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/vpanfi}"
APP_PORT="${VPANFI_PORT:-8080}"
HEALTH_URL="http://127.0.0.1:${APP_PORT}/healthz"
PREVIOUS_SHA=""
FIRST_DEPLOY=false

log() {
  printf '\n[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

ensure_environment() {
  if [[ -f .env ]]; then
    chmod 600 .env
    return
  fi

  log "Creating the initial production environment"

  local postgres_password
  local jwt_secret
  postgres_password="$(openssl rand -hex 32)"
  jwt_secret="$(openssl rand -hex 64)"

  cat > .env <<EOF
VPANFI_PORT=${APP_PORT}
VPANFI_ENVIRONMENT=production
VPANFI_FRONTEND_ORIGIN=http://localhost:${APP_PORT}
POSTGRES_PASSWORD=${postgres_password}
VPANFI_JWT_SECRET=${jwt_secret}
VPANFI_REMNAWAVE_BASE_URL=
VPANFI_REMNAWAVE_API_TOKEN=
VITE_TELEGRAM_SUPPORT_URL=https://t.me/VPaNfi_bot
VITE_DEMO_MODE=true
VITE_API_BASE_URL=/api
EOF

  chmod 600 .env
}

wait_for_health() {
  local attempt

  for attempt in $(seq 1 30); do
    if wget -qO- "$HEALTH_URL" >/dev/null 2>&1; then
      log "Application is healthy"
      return 0
    fi

    sleep 2
  done

  log "Health check failed: ${HEALTH_URL}"
  docker compose ps
  docker compose logs --tail=120 web api
  return 1
}

rollback() {
  local exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    return
  fi

  trap - ERR
  log "Deployment failed"

  if [[ "$FIRST_DEPLOY" == false && -n "$PREVIOUS_SHA" ]]; then
    log "Rolling back to ${PREVIOUS_SHA}"
    git reset --hard "$PREVIOUS_SHA"
    docker compose build
    docker compose up -d --remove-orphans
  fi

  exit "$exit_code"
}

trap rollback ERR

cd "$APP_DIR"

if [[ ! -d .git ]]; then
  log "Repository is not initialized in ${APP_DIR}"
  exit 1
fi

PREVIOUS_SHA="$(git rev-parse HEAD)"

log "Fetching main branch"
git fetch --prune origin main
git reset --hard origin/main

ensure_environment

log "Validating Docker Compose configuration"
docker compose config --quiet

log "Building application images"
docker compose build --pull

log "Starting application"
docker compose up -d --remove-orphans

wait_for_health

log "Removing unused images"
docker image prune -f >/dev/null

log "Deployment completed at $(git rev-parse --short HEAD)"
docker compose ps
