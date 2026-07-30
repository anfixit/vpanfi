#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/vpanfi}"
APP_PORT="${VPANFI_PORT:-8080}"
WEB_HEALTH_URL="http://127.0.0.1:${APP_PORT}/healthz"
API_HEALTH_URL="http://127.0.0.1:${APP_PORT}/api/healthz"
HEALTH_ATTEMPTS=45
HEALTH_INTERVAL_SECONDS=2
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

set_env_value() {
  # Writes one variable into .env without ever echoing its value.
  local key="$1"
  local value="$2"

  if [[ -z "$value" ]]; then
    return
  fi

  if grep -q "^${key}=" .env; then
    local escaped
    escaped="$(printf '%s' "$value" | sed -e 's/[\\&|]/\\&/g')"
    sed -i "s|^${key}=.*|${key}=${escaped}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi

  log "Updated ${key} in .env"
}

apply_panel_credentials() {
  # The panel URL and token arrive from repository secrets so they survive
  # a rebuilt server and never live in Git. Empty values leave whatever is
  # already in .env untouched, so a hand-edited file still works.
  set_env_value VPANFI_REMNAWAVE_BASE_URL "${VPANFI_REMNAWAVE_BASE_URL:-}"
  set_env_value VPANFI_REMNAWAVE_API_TOKEN "${VPANFI_REMNAWAVE_API_TOKEN:-}"
  set_env_value VITE_DEMO_MODE "${VITE_DEMO_MODE:-}"
  set_env_value VPANFI_TELEGRAM_BOT_TOKEN "${VPANFI_TELEGRAM_BOT_TOKEN:-}"
  set_env_value VPANFI_TELEGRAM_BOT_USERNAME "${VPANFI_TELEGRAM_BOT_USERNAME:-}"
  set_env_value VPANFI_VK_CLIENT_ID "${VPANFI_VK_CLIENT_ID:-}"
  set_env_value VPANFI_VK_CLIENT_SECRET "${VPANFI_VK_CLIENT_SECRET:-}"
  set_env_value VPANFI_YANDEX_CLIENT_ID "${VPANFI_YANDEX_CLIENT_ID:-}"
  set_env_value VPANFI_YANDEX_CLIENT_SECRET "${VPANFI_YANDEX_CLIENT_SECRET:-}"
  set_env_value VPANFI_OAUTH_REDIRECT_URL "${VPANFI_OAUTH_REDIRECT_URL:-}"
  chmod 600 .env
}

attach_to_proxy_network() {
  # Compose recreates vpanfi-web on every release, which drops the extra
  # network that lets the server's Caddy reach it by name. Reattaching
  # here keeps the published domain working after a deploy.
  local network="${VPANFI_PROXY_NETWORK:-remnawave-network}"

  if ! docker network inspect "$network" >/dev/null 2>&1; then
    return
  fi

  local attached
  attached="$(
    docker inspect \
      -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{"\n"}}{{end}}' \
      vpanfi-web 2>/dev/null || true
  )"

  if grep -qx "$network" <<<"$attached"; then
    return
  fi

  log "Attaching vpanfi-web to ${network}"
  docker network connect "$network" vpanfi-web
}

wait_for_health() {
  local attempt

  for attempt in $(seq 1 "$HEALTH_ATTEMPTS"); do
    if curl -fsS "$WEB_HEALTH_URL" >/dev/null 2>&1 \
      && curl -fsS "$API_HEALTH_URL" >/dev/null 2>&1; then
      log "Web and API health checks passed"
      return 0
    fi

    sleep "$HEALTH_INTERVAL_SECONDS"
  done

  log "Health check failed: ${WEB_HEALTH_URL} or ${API_HEALTH_URL}"
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

if [[ -z "$(docker compose ps --quiet 2>/dev/null)" ]]; then
  FIRST_DEPLOY=true
fi

log "Fetching main branch"
git fetch --prune origin main
git reset --hard origin/main

ensure_environment
apply_panel_credentials

log "Validating Docker Compose configuration"
docker compose config --quiet

log "Building application images"
docker compose build --pull

log "Starting application"
docker compose up -d --remove-orphans

attach_to_proxy_network

wait_for_health

log "Removing unused images"
docker image prune -f >/dev/null

log "Deployment completed at $(git rev-parse --short HEAD)"
docker compose ps
