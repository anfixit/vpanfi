"""Фоновый опрос кассы по платежам, которые ещё ждут оплаты.

Сайт узнаёт об оплате из уведомления ЮKassa, и выдача зовётся только из
вебхука. Адрес уведомлений у магазина один, а магазин общий с ботом
продаж и с @hopbyhop_bot; те живут опросом кассы и уведомлений не ждут
вовсе. Человек может закрыть страницу результата и не вернуться, и тогда
при пропавшем уведомлении его оплаченная подписка никем не выдастся.

Обход не знает ни про панель, ни про письма: он только спрашивает кассу
и зовёт готовый ``CheckoutService.poll``, то есть ту же пару
``confirm``/``deliver``, что и вебхук. Двойной выдачи поэтому не бывает:
``confirm`` отдаёт True только тому вызову, который сам перевёл платёж
из pending в succeeded.

Живёт отдельным модулем, а не внутри ``main.py``: так фоновая задача и
её сборка сервиса проверяются тестами без поднятия приложения.
"""

import logging

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.services.checkout import CheckoutService
from app.services.referral_wiring import (
    build_referral_service,
    zapustit_obrabotku,
)

logger = logging.getLogger(__name__)

__all__ = ["obojti_ozhidayushchie_platezhi"]

# Сколько платежей опрашиваем за один обход. Своих незакрытых платежей
# у сайта единицы, и потолок здесь только от неожиданностей: касса не
# должна получить сотню запросов подряд из-за одной сломанной ночи.
_ZA_ODIN_OBHOD = 20


async def obojti_ozhidayushchie_platezhi(limit: int = _ZA_ODIN_OBHOD) -> int:
    """Спросить кассу о своих платежах в pending и выдать оплаченное.

    Список идентификаторов читается короткой сессией, которая сразу
    закрывается, а каждый платёж обрабатывается в своей: держать одну
    сессию на весь обход значило бы ждать панель и почту по каждому
    платежу в ней же (так же устроен обход зависших наград в
    ``referral_wiring.obojti_ozhidayushchie``).

    Возвращает число выданных подписок. Наверх не бросает ничего: обход
    идёт по расписанию, и один сломанный платёж не должен оставить без
    выдачи остальные.
    """
    settings = get_settings()
    if not settings.is_yookassa_configured:
        return 0

    async with async_session_factory() as session:
        ids = await CheckoutService(session, settings).pending_provider_ids(
            limit=limit
        )

    vydano = 0
    for provider_payment_id in ids:
        try:
            async with async_session_factory() as session:
                service = CheckoutService(
                    session,
                    settings,
                    build_referral_service(session, settings),
                    zapustit_obrabotku,
                )
                if await service.poll(
                    provider_payment_id=provider_payment_id
                ):
                    vydano += 1
        except Exception:
            logger.exception(
                "Опрос платежа сорвался: %s", provider_payment_id
            )

    return vydano
