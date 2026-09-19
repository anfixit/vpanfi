"""Общая сборка ``ReferralService`` для API и фоновой задачи.

Вынесено в отдельный модуль, чтобы ``api/dependencies.py`` и
``app/main.py`` не импортировали друг друга: обоим нужен один и тот же
способ собрать сервис поверх сессии и настроек, а прямой импорт одного
из другого завёл бы цикл.

Здесь же живёт запуск обработки награды в фоне: вебхук Platega должен
ответить 200 быстро, а до шести сетевых походов в панель и в бота
продаж по 10-15 секунд каждый этому мешают. ``register`` остаётся
быстрым и вызывается прямо из запроса, а ``process`` для каждой
награды уходит в свою задачу со своей сессией.
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.integrations.bedolaga.client import BedolagaGateway
from app.integrations.remnawave.client import RemnawaveGateway
from app.services.referral import ReferralService, SqlRewardStore

logger = logging.getLogger(__name__)

__all__ = [
    "build_referral_service",
    "obojti_ozhidayushchie",
    "obrabotat_nagradu",
    "zapustit_obrabotku",
]


def build_referral_service(
    session: AsyncSession, settings: Settings
) -> ReferralService:
    """Собрать сервис рефералки поверх сессии одним и тем же способом.

    Шлюзы приходят фабриками: они не открывают соединение, пока
    рефералке не понадобится сходить в панель или в бота продаж, и
    выключенная рефералка не потребует ни того, ни другого.
    """
    return ReferralService(
        settings,
        SqlRewardStore(session),
        lambda: RemnawaveGateway(settings),
        lambda: BedolagaGateway(settings),
    )


# Сильные ссылки на запущенные задачи обработки наград. asyncio держит
# задачу только слабо: без этого множества сборщик мусора мог бы
# забрать задачу на середине сетевого похода, и награда осталась бы
# pending без единой попытки и без следа в логе.
_ZADACHI: set[asyncio.Task[None]] = set()


async def obrabotat_nagradu(reward_id: UUID) -> None:
    """Обработать одну награду в свежей сессии, не роняя вызывающего.

    Сессия для этой обработки открывается отдельно от той, в которой
    вебхук отвечает Platega: если бы обе награды из одного обхода жили
    в общей сессии, сбой одной из них испортил бы сессию и для
    следующей (``PendingRollbackError``). ``process`` внутри себя уже
    не бросает исключений, но открытие сессии и поиск записи могут
    подняться выше, поэтому здесь свой предохранитель.
    """
    settings = get_settings()
    async with async_session_factory() as session:
        try:
            service = build_referral_service(session, settings)
            await service.process_by_id(reward_id)
        except Exception:
            logger.exception(
                "Рефералка: фоновая обработка награды %s сорвалась",
                reward_id,
            )
            try:
                await session.rollback()
            except Exception:
                logger.exception(
                    "Рефералка: не удалось откатить фоновую сессию "
                    "награды %s",
                    reward_id,
                )


def zapustit_obrabotku(reward_id: UUID) -> None:
    """Поставить обработку награды в фон, не дожидаясь её конца.

    Вызывается прямо из вебхука сразу после ``register``: ответ
    Platega не должен ждать поход в панель и в бота продаж. Задача
    держится в модульном множестве до своего завершения, а done-callback
    убирает её оттуда сам.
    """
    task = asyncio.create_task(obrabotat_nagradu(reward_id))
    _ZADACHI.add(task)
    task.add_done_callback(_ZADACHI.discard)


async def obojti_ozhidayushchie(limit: int = 20) -> int:
    """Обойти зависшие награды по одной, каждую в своей сессии.

    Список id читается короткой отдельной сессией и сразу закрывается:
    держать её открытой на весь обход означало бы то самое ожидание,
    от которого вебхук уже избавлен, только растянутое на всю пачку
    наград сразу.
    """
    async with async_session_factory() as session:
        ids = await SqlRewardStore(session).due_ids(limit)

    for reward_id in ids:
        await obrabotat_nagradu(reward_id)
    return len(ids)
