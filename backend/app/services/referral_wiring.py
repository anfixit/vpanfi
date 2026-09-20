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
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.integrations.bedolaga.client import BedolagaGateway
from app.integrations.remnawave.client import RemnawaveGateway
from app.models.billing import ReferralReward
from app.services.notify import (
    TelegramNotifier,
    nagrada_itog_soobshchenie,
    nagrada_soobshchenie,
    sovpadenie_ustrojstv_soobshchenie,
)
from app.services.referral import ReferralService, SqlRewardStore

logger = logging.getLogger(__name__)

__all__ = [
    "bot_sync_next_run",
    "bot_sync_period",
    "build_referral_service",
    "obojti_ozhidayushchie",
    "obrabotat_nagradu",
    "sinhronizirovat_bota",
    "sverit_ustrojstva",
    "zapustit_obrabotku",
]

# Окно сверки устройств: сутки, за которые бегает фоновая задача, плюс
# запас в час на случай перезапуска приложения между двумя обходами.
_DEVICE_CHECK_WINDOW = timedelta(hours=25)

# Первый обход бота продаж сдвинут от старта приложения на 3 минуты:
# короче, чем у сверки устройств (10 минут), потому что здесь нет
# похода в телеграм по каждому пользователю, а только по новым
# наградам, и частый перезапуск при деплое не грозит завалить Анфису.
_BOT_SYNC_PERVYJ_ZAPUSK = timedelta(minutes=3)
# Не короче пяти минут даже если в настройках стоит меньше: панель и
# бот продаж не должны получать обход чаще, чем раз в пять минут.
_BOT_SYNC_MIN_MINUT = 5


def _soobshchit_ob_itoge(settings: Settings, reward: ReferralReward) -> None:
    """Собрать текст об итоге награды и отправить его в фоне.

    Отдельная функция, а не лямбда прямо в build_referral_service:
    ReferralService зовёт этот callback синхронно внутри своего
    try/except, и здесь не должно быть ничего, что само поднимает
    исключение мимо этого except.
    """
    TelegramNotifier(settings).send_later(
        nagrada_itog_soobshchenie(
            friend_email=reward.friend_email,
            inviter_username=reward.inviter_username,
            status=reward.status,
            friend_granted=reward.friend_granted_at is not None,
            inviter_granted=reward.inviter_granted_at is not None,
            friend_days=reward.friend_days,
            inviter_days=reward.inviter_days,
            last_error=reward.last_error,
            kind=reward.kind,
        )
    )


def _soobshchit_o_novoj_nagrade(
    settings: Settings, reward: ReferralReward
) -> None:
    """Рассказать о награде, заведённой обходом бота продаж.

    Награда за покупку на сайте объявляется прямо из checkout.py, сразу
    после ``register()``, потому что там есть кому отдать результат.
    ``sync_bot()`` заводит награду сама, без вызывающего снаружи, и это
    единственное место, откуда за неё можно позвать то же самое
    сообщение владельцу. Проверка ``alert_events`` та же, что и у
    checkout.py: одна настройка решает, слать ли уведомление о любой
    новой награде, независимо от того, где она заведена.
    """
    if "payment" not in settings.alert_events:
        return
    TelegramNotifier(settings).send_later(
        nagrada_soobshchenie(
            friend_email=reward.friend_email,
            inviter_username=reward.inviter_username,
            status=reward.status,
            kind=reward.kind,
            source="bot",
        )
    )


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
        on_terminal=lambda reward: _soobshchit_ob_itoge(settings, reward),
        on_registered=lambda reward: _soobshchit_o_novoj_nagrade(
            settings, reward
        ),
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


async def sverit_ustrojstva() -> int:
    """Сверить устройства друга и пригласившего по свежим наградам.

    Своя сессия, как и у остальных фоновых задач: главный цикл
    ``app.main._nagrady`` зовёт эту функцию раз в сутки, и ей нельзя
    делить сессию с чем-то ещё в этом же процессе. Ни одно совпадение
    не наказывается само: сообщение уходит человеку, а решение
    (``release``/``reject``) остаётся за ним.

    Исключений не поднимает: сама сверка (``device_overlaps``) уже не
    падает, а открытие сессии и отправка в телеграм здесь всё равно
    завёрнуты дополнительно, чтобы сбой периодической задачи не
    прервал цикл в ``main.py``.
    """
    settings = get_settings()
    try:
        async with async_session_factory() as session:
            service = build_referral_service(session, settings)
            since = datetime.now(UTC) - _DEVICE_CHECK_WINDOW
            hits = await service.device_overlaps(since)

        notifier = TelegramNotifier(settings)
        for reward, common in hits:
            notifier.send_later(
                sovpadenie_ustrojstv_soobshchenie(
                    friend_email=reward.friend_email,
                    inviter_username=reward.inviter_username,
                    common=common,
                    status=reward.status,
                )
            )
        return len(hits)
    except Exception:
        logger.exception("Рефералка: сверка устройств сорвалась")
        return 0


async def sinhronizirovat_bota() -> int:
    """Обойти бота продаж и завести награды за друзей, купивших там.

    Своя сессия, как и у ``sverit_ustrojstva``: главный цикл
    ``app.main._nagrady`` не должен делить сессию ни с чем другим.
    ``ReferralService.sync_bot`` сама не бросает исключений и сама же
    ничего не делает, пока мост выключен настройками, но открытие
    сессии здесь всё равно завёрнуто отдельно: сбой до входа в
    ``sync_bot`` не должен прервать цикл в ``main.py``.
    """
    settings = get_settings()
    try:
        async with async_session_factory() as session:
            service = build_referral_service(session, settings)
            return await service.sync_bot(schedule=zapustit_obrabotku)
    except Exception:
        logger.exception(
            "Рефералка: не удалось открыть сессию для обхода бота"
        )
        return 0


def bot_sync_period(settings: Settings) -> timedelta:
    """Период фонового обхода бота продаж, не короче пяти минут.

    Чистая функция, а не выражение внутри цикла ``_nagrady``: сам цикл
    засыпает настоящими минутами и тестам не подходит, а это правило
    (не короче пяти минут даже при более частой настройке) проверяется
    без ожидания.
    """
    return timedelta(
        minutes=max(_BOT_SYNC_MIN_MINUT, settings.referral_bot_sync_minutes)
    )


def bot_sync_next_run(
    *, poslednij_zapusk: datetime | None, seichas: datetime, period: timedelta
) -> datetime:
    """Момент следующего обхода бота продаж.

    Без предыдущего запуска (только что поднялось приложение) первый
    обход назначается через ``_BOT_SYNC_PERVYJ_ZAPUSK`` от текущего
    момента, а не через полный период: это короче, и деплой не должен
    ждать целых 30 минут (значение по умолчанию), чтобы заметить, что
    мост включён. Дальше каждый следующий обход считается от предыдущего
    запуска, а не от "сейчас", чтобы дрожание цикла ``_nagrady`` (он сам
    может проснуться чуть позже своего сна) не растягивало период.
    """
    if poslednij_zapusk is None:
        return seichas + _BOT_SYNC_PERVYJ_ZAPUSK
    return poslednij_zapusk + period
