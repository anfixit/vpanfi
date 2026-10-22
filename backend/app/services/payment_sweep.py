"""Добор оплат, о которых уведомление ЮKassa до нас не дошло.

До 22.10.2026 единственным способом узнать об оплате был вебхук
``POST /api/v1/payments/yookassa/webhook``. Пока сайт отвечает, этого
хватает: касса повторяет уведомление, пока не увидит 200. Но её окно
повторов конечно, и если сайт лежал дольше (деплой, сеть, 5xx), платёж
оставался PENDING навсегда: деньги приняты, подписка не выдана, и
узнавал об этом только сам покупатель. Сервис работает почти в ноль,
людей около сотни, и каждая такая оплата заметна.

Поэтому сайт спрашивает сам. Вся сверка уже живёт в
``CheckoutService.confirm``: он ходит в ``GET /v3/payments/{id}`` и
сверяет сумму с нашей записью, поэтому здесь только выбор платежей и
расписание. У бота продаж свой такой же добор
(``app/services/payment_verification_service.py``), сайту он не указ:
касса общая, а платежи у каждого свои.

Обход и вебхук могут проснуться одновременно на одном платеже, и
подписка от этого не должна выдаться дважды. Поэтому и тот, и другой
работают под ``zamok_platezha``.
"""

import asyncio
import logging
from collections import Counter
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.models.billing import Payment, PaymentStatus
from app.services.checkout import (
    PROVIDER,
    CheckoutNotConfiguredError,
    CheckoutService,
    CheckoutUnavailableError,
)
from app.services.referral_wiring import (
    build_referral_service,
    zapustit_obrabotku,
)

logger = logging.getLogger(__name__)

__all__ = [
    "OSTYVSHEE_OKNO",
    "SVEZHEE_OKNO",
    "dobor_period",
    "dovesti_platyozh",
    "obojti_svezhie",
    "ozhidayushchie_id",
    "zakryt_ostyvshie",
    "zamok_platezha",
]

# Сколько времени платёж ещё считается живым. Сутки с запасом покрывают
# и оплату по СБП из приложения банка, и человека, который открыл
# страницу кассы, ушёл и вернулся вечером.
SVEZHEE_OKNO = timedelta(hours=24)

# До какого возраста мы ещё спрашиваем кассу о просроченном платеже.
# Сам по себе наш таймер ничего не решает: пометить платёж
# несостоявшимся вправе только касса, и ``confirm`` делает это, когда
# она отвечает canceled (истёкший срок оплаты ЮKassa показывает именно
# так). Поэтому просроченные не выбрасываются, а доспрашиваются раз в
# сутки, пока касса не скажет, чем всё кончилось.
OSTYVSHEE_OKNO = timedelta(days=30)

# Сколько платежей берём за один обход. Больше за раз не нужно: добор
# повторяется через минуты, а хвост из сотен платежей означал бы сотни
# походов в кассу подряд.
_ZA_ODIN_OBHOD = 50

# Не чаще раза в минуту, даже если в настройках стоит меньше.
_MIN_MINUT = 1

# Блокировка на платёж, общая для вебхука и обхода. Процесс uvicorn
# один, поэтому словаря в памяти достаточно. С --workers > 1 или
# несколькими репликами контейнера у каждого процесса будет свой
# словарь, и оба смогут одновременно решить, что подписка ещё не
# выдана: тогда замок надо переносить в базу (SELECT ... FOR UPDATE на
# строке платежа). Та же оговорка, что у ``referral._LOCKS``.
_ZAMKI: dict[str, asyncio.Lock] = {}
_ZHDUSHCHIE: Counter[str] = Counter()


@asynccontextmanager
async def zamok_platezha(provider_payment_id: str) -> AsyncIterator[None]:
    """Занять платёж на время его обработки.

    Счётчик ждущих нужен, чтобы словарь не рос без границы, но и чтобы
    замок не исчезал из-под того, кто его ещё ждёт: убираем запись
    только когда последний ждущий вышел.
    """
    zamok = _ZAMKI.setdefault(provider_payment_id, asyncio.Lock())
    _ZHDUSHCHIE[provider_payment_id] += 1
    try:
        async with zamok:
            yield
    finally:
        _ZHDUSHCHIE[provider_payment_id] -= 1
        if _ZHDUSHCHIE[provider_payment_id] <= 0:
            del _ZHDUSHCHIE[provider_payment_id]
            _ZAMKI.pop(provider_payment_id, None)


async def ozhidayushchie_id(
    session: AsyncSession,
    *,
    ne_starshe: timedelta,
    ne_mladshe: timedelta | None = None,
    limit: int = _ZA_ODIN_OBHOD,
) -> list[str]:
    """Идентификаторы наших неоплаченных платежей, старые первыми.

    Отдаёт идентификаторы кассы, а не сами записи: каждый платёж
    обрабатывается в своей сессии, и объект из чужой сессии здесь был
    бы бесполезен. Платежи без идентификатора кассы пропускаем: о них
    она ничего не знает (``start`` не дождался ответа и уже пометил их
    несостоявшимися).
    """
    seichas = datetime.now(UTC)
    stmt = select(Payment.provider_payment_id).where(
        Payment.provider == PROVIDER,
        Payment.status == PaymentStatus.PENDING,
        Payment.provider_payment_id.is_not(None),
        Payment.created_at >= seichas - ne_starshe,
    )
    if ne_mladshe is not None:
        stmt = stmt.where(Payment.created_at < seichas - ne_mladshe)
    stmt = stmt.order_by(Payment.created_at).limit(limit)
    najdeno = await session.scalars(stmt)
    return [identifier for identifier in najdeno if identifier]


async def dovesti_platyozh(provider_payment_id: str) -> bool:
    """Переспросить кассу об одном платеже и выдать подписку, если оплачен.

    Возвращает True, если подписка выдана этим вызовом. Своя сессия на
    платёж, как у обхода зависших наград: сбой на одном платеже не
    должен оставлять сессию мёртвой для следующего
    (``PendingRollbackError``).

    Правило «продлевает только переход pending → succeeded» остаётся за
    ``confirm``: повторный вызов вернёт False, и подписка не продлится
    второй раз. ``needs_delivery`` — тот же второй шанс, что и у
    повторного вебхука: платёж оплачен, а ссылки нет, потому что в
    прошлый раз не ответила панель.

    Raises:
        CheckoutUnavailableError: Касса не ответила.
        CheckoutNotConfiguredError: Касса или сквад не настроены.

    И то, и другое касается всех платежей сразу, а не одного этого,
    поэтому наверх: обход на таком прерывается и повторит в следующий
    раз.
    """
    settings = get_settings()
    async with (
        zamok_platezha(provider_payment_id),
        async_session_factory() as session,
    ):
        service = CheckoutService(
            session,
            settings,
            build_referral_service(session, settings),
            zapustit_obrabotku,
        )
        try:
            oplatil = await service.confirm(
                provider_payment_id=provider_payment_id
            )
            if not oplatil and not await service.needs_delivery(
                provider_payment_id=provider_payment_id
            ):
                return False
            await service.deliver(provider_payment_id=provider_payment_id)
        except (CheckoutUnavailableError, CheckoutNotConfiguredError):
            await _otkatit(session, provider_payment_id)
            raise
        except Exception:
            logger.exception(
                "Добор оплат: платёж %s не обработан",
                provider_payment_id,
            )
            await _otkatit(session, provider_payment_id)
            return False

    logger.info(
        "Добор оплат: подписка выдана по платежу %s без уведомления кассы",
        provider_payment_id,
    )
    return True


async def _otkatit(session: AsyncSession, provider_payment_id: str) -> None:
    try:
        await session.rollback()
    except Exception:
        logger.exception(
            "Добор оплат: не удалось откатить сессию платежа %s",
            provider_payment_id,
        )


async def _obojti(
    *,
    ne_starshe: timedelta,
    ne_mladshe: timedelta | None = None,
    limit: int = _ZA_ODIN_OBHOD,
) -> int:
    async with async_session_factory() as session:
        ids = await ozhidayushchie_id(
            session,
            ne_starshe=ne_starshe,
            ne_mladshe=ne_mladshe,
            limit=limit,
        )

    vydano = 0
    for identifier in ids:
        try:
            if await dovesti_platyozh(identifier):
                vydano += 1
        except (CheckoutUnavailableError, CheckoutNotConfiguredError):
            # Молчащая касса касается всех платежей сразу: дальше по
            # списку идти бессмысленно, обход повторится через минуты.
            logger.warning(
                "Добор оплат: касса недоступна, обход отложен "
                "(осталось платежей: %s)",
                len(ids) - ids.index(identifier),
            )
            break
    return vydano


async def obojti_svezhie(limit: int = _ZA_ODIN_OBHOD) -> int:
    """Доспросить кассу о платежах не старше суток."""
    return await _obojti(ne_starshe=SVEZHEE_OKNO, limit=limit)


async def zakryt_ostyvshie(limit: int = _ZA_ODIN_OBHOD) -> int:
    """Доспросить кассу о платежах, что висят в pending дольше суток.

    Отдельным редким обходом, а не вместе со свежими: такой платёж
    почти всегда брошенная корзина, и спрашивать о нём каждые две
    минуты значило бы гонять кассу зря. Пометить его несостоявшимся
    решает только она: ``confirm`` ставит FAILED, когда касса отвечает
    canceled. Своего таймера, по которому мы объявляли бы платёж
    пропавшим, здесь нет — он мог бы объявить таким оплаченный.
    """
    return await _obojti(
        ne_starshe=OSTYVSHEE_OKNO, ne_mladshe=SVEZHEE_OKNO, limit=limit
    )


def dobor_period(settings: Settings) -> timedelta:
    """Период добора оплат, не короче минуты.

    Чистая функция, а не выражение внутри цикла в ``main.py``: сам цикл
    засыпает настоящими минутами и тестам не подходит, а правило
    (не чаще раза в минуту даже при более частой настройке) проверяется
    без ожидания.
    """
    return timedelta(
        minutes=max(_MIN_MINUT, settings.yookassa_recheck_minutes)
    )
