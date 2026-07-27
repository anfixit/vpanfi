from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware

__all__ = ["app", "create_app"]


class HealthStatus(TypedDict):
    status: str
    environment: str


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Database, Redis and SDK clients will be initialized here when the
    # persistence layer is connected.
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VPaNfi API",
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        SecurityHeadersMiddleware,
        https_only=settings.is_production,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.get(
        "/healthz",
        tags=["system"],
        summary="Проверка живости API",
        description=(
            "Отвечает без обращения к базе данных: используется "
            "контейнерным health check и деплоем."
        ),
    )
    async def healthcheck() -> HealthStatus:
        return {"status": "ok", "environment": settings.environment}

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
