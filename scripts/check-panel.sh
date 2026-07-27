#!/usr/bin/env bash
# Asks the running API container whether it can talk to the panel.
#
# The check runs inside vpanfi-api on purpose: that is the process which
# will make the real calls, so it proves both the credentials and the
# network path. This repository is public, so the output reports status
# codes and counts only — never the panel address and never the token.
set -Eeuo pipefail

API_CONTAINER=vpanfi-api

if ! docker inspect "$API_CONTAINER" >/dev/null 2>&1; then
  echo "ERROR: $API_CONTAINER is not running" >&2
  exit 1
fi

docker exec "$API_CONTAINER" python - <<'PY'
import asyncio

import httpx

from app.core.config import get_settings

settings = get_settings()

if settings.remnawave_base_url is None:
    print("VPANFI_REMNAWAVE_BASE_URL: not set")
else:
    print("VPANFI_REMNAWAVE_BASE_URL: set")
    print(f"scheme: {settings.remnawave_base_url.scheme}")

print(
    "VPANFI_REMNAWAVE_API_TOKEN:",
    "set" if settings.remnawave_api_token else "not set",
)

if settings.remnawave_base_url is None or settings.remnawave_api_token is None:
    raise SystemExit("Credentials are incomplete, nothing else to check")


async def main() -> None:
    base = str(settings.remnawave_base_url).rstrip("/")
    token = settings.remnawave_api_token.get_secret_value()
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(
        base_url=base,
        headers=headers,
        timeout=settings.remnawave_timeout_seconds,
    ) as client:
        try:
            response = await client.get("/api/users", params={"size": 1})
        except httpx.HTTPError as error:
            print(f"reachable: no ({type(error).__name__})")
            raise SystemExit("The API container cannot reach the panel")

        print(f"reachable: yes (HTTP {response.status_code})")

        if response.status_code in (401, 403):
            raise SystemExit("The panel rejected the token")

        if response.status_code >= 400:
            raise SystemExit("The panel answered with an error")

        try:
            payload = response.json()
        except ValueError:
            raise SystemExit("The panel answered with something that is not JSON")

        body = payload.get("response", payload) if isinstance(payload, dict) else payload
        if isinstance(body, dict):
            body = body.get("users", body)

        if isinstance(body, list):
            print(f"users visible through the token: {len(body)}")
            fields = sorted(body[0]) if body and isinstance(body[0], dict) else []
            print(f"user fields returned: {', '.join(fields) if fields else 'none'}")
        else:
            print("unexpected users payload shape")

        print("panel connection: OK")


asyncio.run(main())
PY
