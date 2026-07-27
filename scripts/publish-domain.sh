#!/usr/bin/env bash
# Publishes the cabinet on a domain through the Caddy instance that is
# already running on this server.
#
# Caddy also serves the Remnawave panel, so this script never restarts or
# recreates its container: it appends one site block, validates the result
# and asks Caddy to reload. Any failure restores the previous file and
# reloads it back, so a bad edit cannot take the panel down.
set -Eeuo pipefail

DOMAIN="${DOMAIN:?DOMAIN is required}"
APP_DIR="${APP_DIR:-/opt/vpanfi}"
PROXY_NETWORK="${PROXY_NETWORK:-remnawave-network}"
WEB_CONTAINER=vpanfi-web
CADDY_CONTAINER=caddy
CADDYFILE_IN_CONTAINER=/etc/caddy/Caddyfile

log() {
  printf '\n[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

caddy_exec() {
  docker exec "$CADDY_CONTAINER" "$@"
}

caddy_reload() {
  caddy_exec caddy reload \
    --config "$CADDYFILE_IN_CONTAINER" \
    --adapter caddyfile
}

log "Checking that ${DOMAIN} points at this server"
server_ip="$(curl -fsS --max-time 10 https://api.ipify.org || true)"

if [ -z "$server_ip" ]; then
  echo "ERROR: could not determine this server's public address" >&2
  exit 1
fi

# getent exits non-zero for an unknown name, and pipefail would end the
# script before the explanation below is printed.
resolved="$(getent ahostsv4 "$DOMAIN" || true)"
domain_ip="$(awk 'NR==1 {print $1}' <<<"$resolved")"

if [ -z "$domain_ip" ]; then
  echo "ERROR: ${DOMAIN} does not resolve." >&2
  echo "Point its A record at ${server_ip} and run this workflow again." >&2
  exit 1
fi

if [ "$domain_ip" != "$server_ip" ]; then
  echo "ERROR: ${DOMAIN} resolves to ${domain_ip}, not to ${server_ip}." >&2
  echo "Caddy could not obtain a certificate, so nothing was changed." >&2
  exit 1
fi

log "Locating the Caddyfile on the host"
caddyfile=""
while read -r source destination; do
  if [ "$destination" = "$CADDYFILE_IN_CONTAINER" ]; then
    caddyfile="$source"
  fi
done < <(docker inspect -f '{{range .Mounts}}{{.Source}} {{.Destination}}
{{end}}' "$CADDY_CONTAINER")

if [ -z "$caddyfile" ] || [ ! -w "$caddyfile" ]; then
  echo "ERROR: the Caddyfile is not mounted from a writable host file" >&2
  exit 1
fi

log "Attaching ${WEB_CONTAINER} to ${PROXY_NETWORK}"
if ! docker network inspect "$PROXY_NETWORK" >/dev/null 2>&1; then
  echo "ERROR: network ${PROXY_NETWORK} does not exist" >&2
  exit 1
fi

if docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}
{{end}}' "$WEB_CONTAINER" | grep -qx "$PROXY_NETWORK"; then
  echo "already attached"
else
  docker network connect "$PROXY_NETWORK" "$WEB_CONTAINER"
  echo "attached"
fi

if grep -qF "$DOMAIN" "$caddyfile"; then
  log "The Caddyfile already mentions ${DOMAIN}, leaving it untouched"
else
  backup="${caddyfile}.vpanfi-backup-$(date -u +%Y%m%dT%H%M%SZ)"
  log "Backing the Caddyfile up"
  cp -p "$caddyfile" "$backup"

  log "Appending the site block for ${DOMAIN}"
  cat >> "$caddyfile" <<EOF

${DOMAIN} {
	encode zstd gzip
	reverse_proxy ${WEB_CONTAINER}:80
}
EOF

  if ! caddy_exec caddy validate \
    --config "$CADDYFILE_IN_CONTAINER" \
    --adapter caddyfile; then
    log "Validation failed, restoring the previous Caddyfile"
    cp -p "$backup" "$caddyfile"
    exit 1
  fi

  if ! caddy_reload; then
    log "Reload failed, restoring the previous Caddyfile"
    cp -p "$backup" "$caddyfile"
    caddy_reload || true
    exit 1
  fi

  log "Caddy reloaded with ${DOMAIN}"
fi

log "Pointing the API CORS origin at https://${DOMAIN}"
cd "$APP_DIR"
if grep -q '^VPANFI_FRONTEND_ORIGIN=' .env; then
  sed -i "s|^VPANFI_FRONTEND_ORIGIN=.*|VPANFI_FRONTEND_ORIGIN=https://${DOMAIN}|" .env
else
  printf 'VPANFI_FRONTEND_ORIGIN=https://%s\n' "$DOMAIN" >> .env
fi
docker compose up -d --remove-orphans

log "Verifying the published site"
for attempt in $(seq 1 30); do
  code="$(
    curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
      "https://${DOMAIN}/healthz" 2>/dev/null || echo 000
  )"
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 4
done

echo "https://${DOMAIN}/healthz -> HTTP ${code}"
curl -sS -o /dev/null -w 'https://%{host}/api/healthz -> HTTP %{http_code}\n' \
  --max-time 15 "https://${DOMAIN}/api/healthz" || true

echo
echo "--- Neighbouring services ---"
for service in caddy remnawave remnawave-db remnawave-redis; do
  state="$(docker inspect -f '{{.State.Status}}' "$service" 2>/dev/null || echo missing)"
  echo "$service: $state"
done

if [ "$code" != "200" ]; then
  echo "ERROR: the domain did not serve the cabinet" >&2
  exit 1
fi
