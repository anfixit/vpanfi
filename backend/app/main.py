import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import TypedDict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware
from app.db.session import async_session_factory
from app.services.referral_wiring import (
    obojti_ozhidayushchie,
    sverit_ustrojstva,
)
from app.services.reminders import RemindersService

logger = logging.getLogger(__name__)

__all__ = ["app", "create_app"]


class HealthStatus(TypedDict):
    status: str
    environment: str


async def _napominaniya() -> None:
    """Обходить людей и предупреждать об окончании подписки.

    Живёт внутри приложения, а не в кроне снаружи: расписание тогда
    едет вместе с кодом, и его не забудут перенести при переезде.
    Процесс uvicorn один, поэтому обход не задвоится.
    """
    settings = get_settings()
    chasy = max(1, settings.reminder_interval_hours)
    # Небольшая задержка на старте: пусть приложение сперва поднимется
    # и ответит проверке здоровья.
    await asyncio.sleep(60)
    while True:
        try:
            async with async_session_factory() as session:
                service = RemindersService(session, settings)
                otpravleno = await service.run_once()
            if otpravleno:
                logger.info("Напоминаний о сроке отправлено: %s", otpravleno)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Обход напоминаний сорвался")
        await asyncio.sleep(chasy * 3600)


_PERVAYA_SVERKA_USTROJSTV = timedelta(minutes=10)
_SVERKA_USTROJSTV_KAZHDYE = timedelta(hours=24)


async def _nagrady() -> None:
    """Повторять зависшие награды и раз в сутки сверять устройства.

    Рефералка выключена по умолчанию, и тогда задача выходит сразу же:
    пустой обход каждые полчаса не стоит даже строчки в журнале. Сама
    выдача идёт своей задачей на свою же награду (см.
    ``referral_wiring.obojti_ozhidayushchie``): здесь только регулярный
    запуск, чтобы этот модуль и ``api/dependencies.py`` не зависели
    друг от друга напрямую.

    Сверка устройств (``sverit_ustrojstva``) живёт в этом же цикле, а
    не в отдельной задаче: третья фоновая задача ради обхода раз в
    сутки не стоила бы своего кода, когда рядом уже крутится цикл с
    подходящей частотой. Отметка времени последней сверки хранится
    прямо в этой функции и переживает только её собственные пробуждения,
    а первый запуск сдвинут на 10 минут от старта, чтобы частый
    перезапуск при деплое не заваливал Анфису уведомлениями.
    """
    settings = get_settings()
    if not settings.referral_enabled:
        return

    minuty = max(5, settings.referral_retry_minutes)
    # Та же небольшая задержка на старте, что и у напоминаний.
    await asyncio.sleep(90)
    sleduyushchaya_sverka = datetime.now(UTC) + _PERVAYA_SVERKA_USTROJSTV
    while True:
        try:
            obrabotano = await obojti_ozhidayushchie()
            if obrabotano:
                logger.info(
                    "Рефералка: повторных попыток выдачи сделано: %s",
                    obrabotano,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Рефералка: обход повторов сорвался")

        if datetime.now(UTC) >= sleduyushchaya_sverka:
            try:
                sovpadenij = await sverit_ustrojstva()
                if sovpadenij:
                    logger.info(
                        "Рефералка: найдено совпадений устройств: %s",
                        sovpadenij,
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Рефералка: сверка устройств сорвалась")
            sleduyushchaya_sverka = (
                datetime.now(UTC) + _SVERKA_USTROJSTV_KAZHDYE
            )

        await asyncio.sleep(minuty * 60)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Database, Redis and SDK clients will be initialized here when the
    # persistence layer is connected.
    zadacha = asyncio.create_task(_napominaniya())
    nagrady_zadacha = asyncio.create_task(_nagrady())
    try:
        yield
    finally:
        zadacha.cancel()
        nagrady_zadacha.cancel()


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
