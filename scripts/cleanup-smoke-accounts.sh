#!/usr/bin/env bash
# Removes the throwaway accounts that production smoke tests create.
#
# Deliberately narrow: the pattern is hardcoded and cannot be passed in,
# so this can never turn into a way to delete real customers.
set -Eeuo pipefail

DB_CONTAINER=vpanfi-postgres
DB_USER=vpanfi
DB_NAME=vpanfi
SMOKE_PATTERN='smoke-test%@vpanfi.ru'

if ! docker inspect "$DB_CONTAINER" >/dev/null 2>&1; then
  echo "ERROR: $DB_CONTAINER is not running" >&2
  exit 1
fi

run_sql() {
  docker exec -i "$DB_CONTAINER" \
    psql -U "$DB_USER" -d "$DB_NAME" -qtAX -c "$1"
}

before="$(
  run_sql "SELECT count(*) FROM users WHERE email LIKE '${SMOKE_PATTERN}';"
)"
echo "smoke accounts found: ${before}"

if [ "$before" = "0" ]; then
  echo "nothing to clean up"
  exit 0
fi

echo "emails about to be removed:"
run_sql "SELECT email FROM users WHERE email LIKE '${SMOKE_PATTERN}';"

# Платежи ссылаются на пользователя с ON DELETE RESTRICT, но у смоук-
# аккаунтов их не бывает: они не доходят до оплаты. Если вдруг дойдут —
# удаление упадёт, и это правильнее, чем стереть историю платежей.
run_sql "DELETE FROM users WHERE email LIKE '${SMOKE_PATTERN}';"

after="$(
  run_sql "SELECT count(*) FROM users WHERE email LIKE '${SMOKE_PATTERN}';"
)"
echo "smoke accounts remaining: ${after}"

if [ "$after" != "0" ]; then
  echo "ERROR: some smoke accounts survived" >&2
  exit 1
fi
