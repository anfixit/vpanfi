"""Заголовки безопасности для всех ответов API."""

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

__all__ = ["SecurityHeadersMiddleware"]

HSTS_MAX_AGE_SECONDS = 31_536_000

# API отдаёт только JSON, поэтому политика максимально узкая:
# исполняемого и встраиваемого контента здесь не бывает.
API_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Добавляет базовый набор security-заголовков к каждому ответу."""

    def __init__(
        self,
        app: Callable[..., object],
        *,
        https_only: bool,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._https_only = https_only

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            API_CONTENT_SECURITY_POLICY
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"

        if self._https_only:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={HSTS_MAX_AGE_SECONDS}; includeSubDomains"
            )

        return response
