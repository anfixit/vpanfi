#!/usr/bin/env bash
# Grants or revokes the admin flag for one cabinet account.
#
# There is deliberately no endpoint for this: an account that can make
# other accounts administrators is a much larger target than one that
# cannot. The first administrator has to be appointed from the server.
set -Eeuo pipefail

DB_CONTAINER=vpanfi-postgres
DB_USER=vpanfi
DB_NAME=vpanfi

EMAIL="${EMAIL:?EMAIL is required}"
GRANT="${GRANT:-true}"

case "$GRANT" in
  true|false) ;;
  *)
    echo "ERROR: GRANT must be true or false" >&2
    exit 1
    ;;
esac

if ! docker inspect "$DB_CONTAINER" >/dev/null 2>&1; then
  echo "ERROR: $DB_CONTAINER is not running" >&2
  exit 1
fi

run_sql() {
  # Stdin is closed on purpose: this script arrives over SSH on stdin,
  # and an interactive docker exec would consume the rest of it.
  docker exec "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -qtAX -c "$1" < /dev/null
}

escaped_email="${EMAIL//\'/\'\'}"

exists="$(
  run_sql "SELECT count(*) FROM users WHERE lower(email) = lower('${escaped_email}');"
)"

if [ "$exists" = "0" ]; then
  echo "ERROR: no account with that email" >&2
  exit 1
fi

run_sql "UPDATE users SET is_admin = ${GRANT} WHERE lower(email) = lower('${escaped_email}');"

echo "admin accounts now:"
run_sql "SELECT email FROM users WHERE is_admin;"

echo "GRANT-ADMIN-COMPLETE"
