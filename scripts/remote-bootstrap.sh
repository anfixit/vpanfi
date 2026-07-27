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
