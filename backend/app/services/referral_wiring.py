"""Общая сборка ``ReferralService`` для API и фоновой задачи.

Вынесено в отдельный модуль, чтобы ``api/dependencies.py`` и
``app/main.py`` не импортировали друг друга: обоим нужен один и тот же
способ собрать сервис поверх сессии и настроек, а прямой импорт одного
из другого завёл бы цикл.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.bedolaga.client import BedolagaGateway
from app.integrations.remnawave.client import RemnawaveGateway
from app.services.referral import ReferralService, SqlRewardStore

__all__ = ["build_referral_service"]


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
