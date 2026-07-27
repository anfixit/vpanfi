#!/usr/bin/env bash
# Runs on the production server through the deployment SSH session.
# Makes sure /opt/vpanfi is a checkout of main and hands over to the
# repository's own deploy script.
set -Eeuo pipefail

APP_DIR=/opt/vpanfi
REPO_URL=https://github.com/anfixit/vpanfi.git

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR does not exist on the server" >&2
  exit 1
fi

if [ ! -d "$APP_DIR/.git" ]; then
  if [ -n "$(find "$APP_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
    echo "ERROR: $APP_DIR is not empty and is not a Git repository" >&2
    exit 1
  fi

  echo "Cloning $REPO_URL into $APP_DIR"
  git clone --branch main --single-branch "$REPO_URL" "$APP_DIR"
fi

git config --global --add safe.directory "$APP_DIR" || true

cd "$APP_DIR"
chmod +x scripts/deploy.sh
APP_DIR="$APP_DIR" ./scripts/deploy.sh

echo
echo "=== Deployment verification ==="
echo "--- Checkout ---"
git status --short --branch
git rev-parse --short HEAD

echo "--- Compose ---"
docker compose config --quiet && echo "compose config: valid"
docker compose ps

echo "--- Health ---"
curl -fsS http://127.0.0.1:8080/healthz && echo " <- /healthz"
curl -fsS http://127.0.0.1:8080/api/healthz && echo " <- /api/healthz"

# Кабинет живёт на том же сервере, что и панель с прокси, поэтому
# каждый деплой подтверждает, что чужие контейнеры не пострадали.
echo "--- Neighbouring services ---"
for service in caddy remnawave remnawave-db remnawave-redis; do
  state="$(docker inspect -f '{{.State.Status}}' "$service" 2>/dev/null || echo missing)"
  echo "$service: $state"
done
