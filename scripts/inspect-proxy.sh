#!/usr/bin/env bash
# Read-only look at the Caddy instance that already serves this server.
# The repository is public, so this prints shapes and yes/no answers only:
# never the proxy configuration itself and never other people's domains.
set -Eeuo pipefail

DOMAIN="${DOMAIN:?DOMAIN is required}"
WEB_CONTAINER=vpanfi-web

echo "=== Caddy container ==="
if ! docker inspect caddy >/dev/null 2>&1; then
  echo "caddy: missing"
  exit 1
fi

echo "state: $(docker inspect -f '{{.State.Status}}' caddy)"
echo "image: $(docker inspect -f '{{index (split .Config.Image \":\") 0}}' caddy)"

echo "networks:"
docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}  {{$name}}
{{end}}' caddy

echo "config mounts (container side):"
docker inspect -f '{{range .Mounts}}  {{.Destination}} (rw={{.RW}})
{{end}}' caddy

echo
echo "=== Configuration file ==="
CADDYFILE_HOST=""
while read -r source destination; do
  case "$destination" in
    */Caddyfile|*/caddy/Caddyfile|/etc/caddy/Caddyfile)
      CADDYFILE_HOST="$source"
      ;;
  esac
done < <(docker inspect -f '{{range .Mounts}}{{.Source}} {{.Destination}}
{{end}}' caddy)

if [ -z "$CADDYFILE_HOST" ]; then
  echo "Caddyfile mount: not found (config may be JSON or baked into the image)"
else
  echo "Caddyfile mount: found"
  if [ -r "$CADDYFILE_HOST" ]; then
    echo "readable by deploy user: yes"
    echo "writable by deploy user: $([ -w "$CADDYFILE_HOST" ] && echo yes || echo no)"
    echo "site blocks: $(grep -cE '^[^[:space:]#].*\{[[:space:]]*$' "$CADDYFILE_HOST" || true)"
    echo "already mentions the target domain: $(grep -cF "$DOMAIN" "$CADDYFILE_HOST" || true)"
    echo "uses import: $(grep -cE '^\s*import ' "$CADDYFILE_HOST" || true)"
  else
    echo "readable by deploy user: no"
  fi
fi

echo
echo "=== Reachability of the cabinet from Caddy ==="
echo "web container: $(docker inspect -f '{{.State.Status}}' "$WEB_CONTAINER" 2>/dev/null || echo missing)"
if docker exec caddy wget -q -T 3 -O /dev/null "http://${WEB_CONTAINER}/healthz" 2>/dev/null; then
  echo "caddy -> ${WEB_CONTAINER}: reachable"
else
  echo "caddy -> ${WEB_CONTAINER}: not reachable (shared network needed)"
fi

echo
echo "=== What the proxy answers for the target domain today ==="
code="$(
  curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
    --resolve "${DOMAIN}:443:127.0.0.1" "https://${DOMAIN}/" 2>/dev/null || echo 000
)"
echo "https://${DOMAIN}/ from the server itself: HTTP ${code}"
