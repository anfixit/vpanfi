"""Ядро рефералки: кто получает награду и как она доходит до обоих.

Друг платит впервые, и обоим полагается по дню за каждый оплаченный.
Само начисление идёт в два отдельных прыжка (панель для друга, панель
или бот продаж для пригласившего), и каждый прыжок сразу помечается
сделанным: сбой одного из них при повторной попытке не должен продлить
того, кому уже продлили.

Хранилище спрятано за протоколом ``RewardStore``: тестам рефералки база
не нужна, у проекта нет тестовой Postgres (модели держат перечисления и
``PGUUID``), и вся логика проверяется поддельным хранилищем в памяти.
Оба внешних шлюза приходят фабриками, нулевыми вызываемыми, отдающими
асинхронный контекстный менеджер, чтобы тесты подсовывали подделки, а
прод собирал настоящие ``RemnawaveGateway``/``BedolagaGateway``.
"""

import asyncio
import logging
import re
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.bedolaga.client import BedolagaUserNotFoundError
from app.integrations.remnawave.client import RemnawaveUserNotFoundError
from app.models.billing import Payment, PaymentStatus, ReferralReward
from app.services.panel import read_panel_user

logger = logging.getLogger(__name__)

__all__ = [
    "CODE_RE",
    "ReferralService",
    "RewardStore",
    "SqlRewardStore",
    "normalize_code",
]

# Код приглашения это имя учётки в панели: буквы, цифры и то, что
# панель разрешает в username. Ограничение длины совпадает с колонкой
# `referral_code`/`inviter_username` (String(64)).
CODE_RE = re.compile(r"^[A-Za-z0-9_.-]{3,64}$")

# Учётки интеграции, которые не должны получать награду за приглашение.
_SINERGIYA_RE = re.compile(r"^OOO_SINERGIYA_", re.IGNORECASE)

# После десятой неудачной попытки выдачи запись перестаёт повторяться
# сама: дальше ей нужны глаза человека, а не фоновая задача.
_MAX_ATTEMPTS = 10
# Окно, за которое считается потолок наград одному пригласившему.
_CAP_WINDOW_DAYS = 30
# Совпадает с длиной колонки `last_error` (String(500)).
_MAX_ERROR_LENGTH = 500

# Свежую запись обход не трогает: за ней уже идёт фоновая задача,
# которую checkout поставил сразу после register, и гонка с обходом
# нужна не раньше, чем эта задача успеет провалиться и записать сбой
# в базу.
_DUE_MIN_AGE = timedelta(minutes=10)

# Обход клиентов бота продаж постранично. Тот же приём, что и у
# MAX_PURCHASE_PAGES в bedolaga.client: неверный total на стороне бота
# не должен превратить обход в вечный цикл.
_MAX_BOT_SYNC_PAGES = 50
# Размер страницы /users бота продаж за один запрос.
_BOT_SYNC_PAGE_SIZE = 200

GatewayFactory = Callable[[], AbstractAsyncContextManager[Any]]

# Блокировки по id награды, общие для всех экземпляров ReferralService
# в процессе: фоновая задача, запущенная сразу после register, и
# периодический обход читают одну и ту же запись каждый из своей
# сессии, и оба должны видеть одну и ту же блокировку, а не свою
# локальную.
#
# Гарантия «выдано не более одного раза» держится только на том, что
# это словарь в памяти ОДНОГО процесса. Если api когда-нибудь поднимут
# с --workers > 1 или несколькими репликами контейнера, у каждого будет
# свой отдельный словарь _LOCKS, и два процесса не увидят замок друг
# друга: оба смогут одновременно решить, что награда ещё не выдана, и
# выдать её дважды. Перед этим замок нужно перенести в базу (например
# SELECT ... FOR UPDATE на строке награды).
_LOCKS: dict[UUID, asyncio.Lock] = {}

# Статусы, после которых с наградой больше никто не будет работать
# параллельно: держать для них блокировку значило бы копить словарь
# без границы на каждую когда-либо обработанную запись.
_TERMINAL_STATUSES = frozenset({"granted", "failed", "rejected"})


def _lock_for(reward_id: UUID) -> asyncio.Lock:
    """Отдать (и при нужде завести) блокировку конкретной награды."""
    lock = _LOCKS.get(reward_id)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[reward_id] = lock
    return lock


def _release_lock(reward_id: UUID) -> None:
    """Убрать блокировку завершённой награды, чтобы словарь не рос."""
    _LOCKS.pop(reward_id, None)


def normalize_code(raw: str | None) -> str | None:
    """Привести код приглашения к пригодному для поиска в панели виду.

    Обрезает только пробелы по краям: панель ищет учётку по точному
    имени, и лишняя нормализация регистра увела бы поиск от настоящего
    пользователя (Alyona_Tutina и alyona_tutina это разные запросы).

    Returns:
        Код без краевых пробелов либо None, если кода нет или он не
        похож на имя учётки.
    """
    if raw is None:
        return None
    stripped = raw.strip()
    if not stripped or not CODE_RE.match(stripped):
        return None
    return stripped


class RewardStore(Protocol):
    """То, что нужно ядру рефералки от хранилища наград.

    Логика начисления живёт по эту сторону протокола и не знает про
    SQLAlchemy: тесты дают хранилище в памяти, а прод даёт
    ``SqlRewardStore``.
    """

    async def has_earlier_paid(self, email: str, payment_id: UUID) -> bool:
        """У этой почты уже была другая успешная оплата."""
        ...

    async def reward_exists(self, payment_id: UUID, email: str) -> bool:
        """Награда за первую покупку по этому платежу или почте уже есть.

        Смотрит только вид ``first``: у продления своя собственная
        проверка (``renewal_exists``), и смешивать их здесь означало
        бы, что уже вознаграждённый друг вовсе не может продлиться.
        """
        ...

    async def first_reward_for(self, email: str) -> ReferralReward | None:
        """Награда за первую покупку этого друга, если она уже отработала.

        Ищет без учёта регистра почты и отдаёт запись только в статусе
        ``granted`` или ``held``: в обоих друг реально получил свои
        дни (``held`` держит только награду пригласившему, другу выдано
        сразу же). Статусы ``pending`` и ``failed`` значат, что другу
        либо ещё ничего не выдано, либо выдача не задалась вовсе, и
        продление за такого "друга" было бы наградой за то, чего не
        случилось. ``rejected`` значит, что человек решил, что первой
        покупки как приглашения не было вовсе.
        """
        ...

    async def renewal_for(self, email: str) -> ReferralReward | None:
        """Награда за продление этого друга, если она есть, любого статуса.

        Ищет без учёта регистра почты. Единственный вызывающий,
        ``admin.reject_referral_reward``, отклоняет продление вслед за
        first-наградой того же друга: без этого метода отклонённая
        первая покупка оставляла бы продление висеть в ожидании выдачи
        за друга, которого по факту отменили.
        """
        ...

    async def renewal_exists(self, email: str) -> bool:
        """У этого друга уже есть награда за продление, любого статуса.

        Продление положено только один раз за всю историю друга, и
        рэйс на "первое продление" здесь не важен: как только запись
        появилась, все следующие покупки друга снова обычное продление
        без награды.
        """
        ...

    async def bot_reward_exists(self, transaction_id: int) -> bool:
        """Награда за эту транзакцию бота продаж уже заведена, любого статуса.

        У наград из бота продаж нет своего payment_id сайта, и
        ``bot_transaction_id`` служит той же самой цели, что и
        ``payment_id`` в ``reward_exists``: без него повторный обход
        одного и того же прохода по покупкам завёл бы вторую награду
        на ту же самую покупку. Проверяется без учёта статуса
        намеренно: отклонённая (``rejected``) награда блокирует так же
        навсегда, как и на сайте, потому что transaction_id этой
        покупки больше никогда не появится ни у какой другой.
        """
        ...

    async def add(self, reward: ReferralReward) -> None:
        """Завести новую запись награды."""
        ...

    async def get(self, reward_id: UUID) -> ReferralReward | None:
        """Найти запись награды по id, если она ещё существует."""
        ...

    async def counted_in_last_days(
        self, inviter_username: str, days: int
    ) -> int:
        """Сколько наград этого пригласившего съедает потолок за окно дней.

        Считает по моменту заведения записи (``created_at``), а не по
        моменту выдачи: несколько ``register`` подряд заводят по
        записи каждый, и до первого ``process`` у всех
        ``inviter_granted_at`` пусто. Считать только выданное позволяло
        бы очереди из pending-наград обойти потолок целиком, пока
        фоновая задача не успела дойти ни до одной из них.

        В счёт идут только ``pending``, ``granted`` и ``failed`` с
        ненулевыми днями пригласившему: ``held`` и ``rejected`` потолок
        не расходуют, потому что ``held`` сама и есть последствие
        потолка, а ``rejected`` человек уже отменил.
        """
        ...

    async def due_ids(self, limit: int) -> list[UUID]:
        """Id записей, ожидающих выдачи, самые старые первыми.

        Отдаёт именно id, а не сами записи: обход обрабатывает каждую
        награду в своей сессии, и объект из чужой сессии тут был бы
        бесполезен.
        """
        ...

    async def save(self) -> None:
        """Сохранить то, что изменилось в записях наград."""
        ...

    async def rollback(self) -> None:
        """Откатить сессию после сбоя, чтобы она не осталась мёртвой.

        Одна обработка награды делает несколько запросов в одной
        сессии (сперва другу, потом пригласившему). Незакоммиченный
        сбой первого из них оставляет сессию в состоянии, где любое
        следующее действие получает PendingRollbackError, и без
        явного отката вторая половина той же обработки не выполнится
        даже там, где сеть в порядке.
        """
        ...

    async def refresh(self, reward: ReferralReward) -> None:
        """Перечитать текущее состояние записи перед решением, что выдать.

        Нужно под замком в ``process``: без этого второй обработчик
        решал бы по устаревшему объекту в памяти, не видя, что первый
        уже успел выдать часть награды.
        """
        ...

    async def inviter_stats(self, inviter_username: str) -> tuple[int, int]:
        """Сколько друзей засчитано пригласившему и сколько дней он получил.

        Друг считается засчитанным, если ему уже продлили подписку
        (``inviter_granted_at`` не пусто), либо у награды нулевые дни
        пригласившему при статусе ``granted``: это тег ``SVOI``, где
        друг получает бонус, а пригласившему дни не положены вовсе.
        Считаются только награды вида ``first``: продление это тот же
        самый друг, а не новый, и не должно посчитаться вторым другом.

        Дни считаются только по уже выданным наградам и обоих видов
        сразу: то, что ждёт своей очереди, здесь не в счёт, а дни за
        продление это такие же честно заработанные дни, как и за
        первую покупку.
        """
        ...

    async def recent(self, since: datetime) -> list[ReferralReward]:
        """Награды, заведённые начиная с указанного момента.

        Отклонённые (``rejected``) не идут в сверку устройств: решение
        по ним уже принято человеком, поднимать их снова незачем.
        Записи без ``friend_panel_user_id`` тоже не идут: без него
        нечьи устройства друга смотреть.

        Отдельной отметки "уведомление уже отправлено" нет намеренно:
        сверка идёт раз в сутки, а окно здесь на час шире, чем сутки
        (25 часов), чтобы перезапуск приложения не пропустил награду,
        заведённую прямо перед прошлым обходом. Ценой такой простоты
        одно и то же совпадение после перезапуска может прийти во
        второй раз, но не чаще.
        """
        ...

    async def list_recent(
        self, status: str | None, limit: int
    ) -> list[ReferralReward]:
        """Последние по времени награды, при нужде только одного статуса.

        Единственный способ найти id награды для ``release``/``reject``
        из административного раздела: без него решать по придержанной
        награде можно было бы только глядя в базу напрямую.
        """
        ...


class SqlRewardStore(RewardStore):
    """Хранилище наград поверх обычной сессии SQLAlchemy.

    Тонкий слой без бизнес-правил: у проекта нет тестовой базы, а логика
    рефералки проверяется хранилищем в памяти, а не этим классом.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_earlier_paid(self, email: str, payment_id: UUID) -> bool:
        stmt = (
            select(Payment.id)
            .where(
                func.lower(Payment.contact_email) == email.lower(),
                Payment.status == PaymentStatus.SUCCEEDED,
                Payment.id != payment_id,
            )
            .limit(1)
        )
        return await self._session.scalar(stmt) is not None

    async def reward_exists(self, payment_id: UUID, email: str) -> bool:
        stmt = (
            select(ReferralReward.id)
            .where(
                or_(
                    ReferralReward.payment_id == payment_id,
                    and_(
                        func.lower(ReferralReward.friend_email)
                        == email.lower(),
                        ReferralReward.kind == "first",
                    ),
                )
            )
            .limit(1)
        )
        return await self._session.scalar(stmt) is not None

    async def first_reward_for(self, email: str) -> ReferralReward | None:
        stmt = (
            select(ReferralReward)
            .where(
                func.lower(ReferralReward.friend_email) == email.lower(),
                ReferralReward.kind == "first",
                ReferralReward.status.in_(("granted", "held")),
            )
            .limit(1)
        )
        return await self._session.scalar(stmt)

    async def renewal_for(self, email: str) -> ReferralReward | None:
        stmt = (
            select(ReferralReward)
            .where(
                func.lower(ReferralReward.friend_email) == email.lower(),
                ReferralReward.kind == "renewal",
            )
            .limit(1)
        )
        return await self._session.scalar(stmt)

    async def renewal_exists(self, email: str) -> bool:
        stmt = (
            select(ReferralReward.id)
            .where(
                func.lower(ReferralReward.friend_email) == email.lower(),
                ReferralReward.kind == "renewal",
            )
            .limit(1)
        )
        return await self._session.scalar(stmt) is not None

    async def bot_reward_exists(self, transaction_id: int) -> bool:
        stmt = (
            select(ReferralReward.id)
            .where(ReferralReward.bot_transaction_id == transaction_id)
            .limit(1)
        )
        return await self._session.scalar(stmt) is not None

    async def add(self, reward: ReferralReward) -> None:
        self._session.add(reward)

    async def get(self, reward_id: UUID) -> ReferralReward | None:
        return await self._session.get(ReferralReward, reward_id)

    async def counted_in_last_days(
        self, inviter_username: str, days: int
    ) -> int:
        threshold = datetime.now(UTC) - timedelta(days=days)
        stmt = select(func.count()).where(
            ReferralReward.inviter_username == inviter_username,
            ReferralReward.inviter_days > 0,
            ReferralReward.status.in_(("pending", "granted", "failed")),
            ReferralReward.created_at >= threshold,
        )
        return int(await self._session.scalar(stmt) or 0)

    async def due_ids(self, limit: int) -> list[UUID]:
        threshold = datetime.now(UTC) - _DUE_MIN_AGE
        stmt = (
            select(ReferralReward.id)
            .where(
                ReferralReward.status == "pending",
                ReferralReward.created_at <= threshold,
            )
            .order_by(ReferralReward.created_at)
            .limit(limit)
        )
        return list(await self._session.scalars(stmt))

    async def save(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def refresh(self, reward: ReferralReward) -> None:
        await self._session.refresh(reward)

    async def inviter_stats(self, inviter_username: str) -> tuple[int, int]:
        friends_stmt = select(func.count()).where(
            ReferralReward.inviter_username == inviter_username,
            # Только first: продление это тот же друг, что и при первой
            # покупке, а не второй, и не должно раздувать счётчик друзей.
            ReferralReward.kind == "first",
            or_(
                ReferralReward.inviter_granted_at.is_not(None),
                and_(
                    ReferralReward.inviter_days == 0,
                    ReferralReward.status == "granted",
                ),
            ),
        )
        # Дни за продление считаются вместе с first: у renewal-записи
        # kind тут не проверяем нарочно, дни там честно заработаны так
        # же, как и за первую покупку.
        days_stmt = select(
            func.coalesce(func.sum(ReferralReward.inviter_days), 0)
        ).where(
            ReferralReward.inviter_username == inviter_username,
            ReferralReward.inviter_granted_at.is_not(None),
        )
        friends = int(await self._session.scalar(friends_stmt) or 0)
        days_earned = int(await self._session.scalar(days_stmt) or 0)
        return friends, days_earned

    async def recent(self, since: datetime) -> list[ReferralReward]:
        stmt = select(ReferralReward).where(
            ReferralReward.created_at >= since,
            ReferralReward.status != "rejected",
            ReferralReward.friend_panel_user_id.is_not(None),
        )
        return list(await self._session.scalars(stmt))

    async def list_recent(
        self, status: str | None, limit: int
    ) -> list[ReferralReward]:
        stmt = (
            select(ReferralReward)
            .order_by(ReferralReward.created_at.desc())
            .limit(limit)
        )
        if status is not None:
            stmt = stmt.where(ReferralReward.status == status)
        return list(await self._session.scalars(stmt))


def _inviter_days(raw: Mapping[str, Any], days_if_paid: int) -> int | None:
    """Сколько дней причитается пригласившему, либо None, если не принят.

    ``days_if_paid`` разное для первой покупки и для продления
    (``referral_inviter_days`` и ``referral_renewal_days``
    соответственно), сама проверка тега и статуса при этом общая, и
    вызывающий передаёт нужное число, а не читает настройки здесь.

    Порядок проверок важен: учётки интеграции отсекаются раньше тега и
    статуса, а мёртвая подписка отсекается раньше тега, потому что дни
    не могут лечь на то, чего больше нет.
    """
    username = str(raw.get("username") or "")
    if _SINERGIYA_RE.match(username):
        return None

    status = str(raw.get("status") or "").upper()
    if status != "ACTIVE":
        return None

    tag = str(raw.get("tag") or "").upper()
    if tag == "SVOI":
        # Вечный срок дней не просит, но друг всё равно на бонусе.
        return 0
    if tag == "PAID":
        return days_if_paid
    return None


def _as_aware_utc(moment: datetime) -> datetime:
    """Достроить временную зону там, где драйвер её не дал.

    ``created_at`` приходит либо от asyncpg (``timezone=True``, значение
    уже осведомлено о зоне), либо из объекта, собранного тестом или
    ``add()`` до записи в базу, где naive-datetime это просто "сейчас"
    без зоны. Считать наивное время каким-то другим часовым поясом,
    кроме UTC, здесь неоткуда, весь проект и так работает в UTC.
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment


def _validate_inviter_payload(
    inviter_raw: Mapping[str, Any], days_if_paid: int
) -> tuple[Mapping[str, Any], Any, int] | None:
    """Проверить уже полученного пригласившего по общим правилам приёма.

    Общий код для всех путей начисления: первой покупки на сайте,
    продления на сайте и обхода бота продаж. Каждый из них ищет
    пригласившего своим способом (по имени учётки, по телеграм-id), а
    решение принять его или нет одно и то же везде и живёт только
    здесь, а не в каждом пути по отдельности.

    Returns:
        Кортеж (сырой ответ панели, разобранный пользователь, дни
        пригласившему), либо None, если пригласившего не приняли.
    """
    inviter_days = _inviter_days(inviter_raw, days_if_paid)
    if inviter_days is None:
        return None
    return inviter_raw, read_panel_user(inviter_raw), inviter_days


def _read_telegram_id(raw: Mapping[str, Any]) -> int | None:
    value = raw.get("telegramId")
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


class ReferralService:
    """Правила начисления и обработчик наград за приглашение."""

    def __init__(
        self,
        settings: Settings,
        store: RewardStore,
        panel_factory: GatewayFactory,
        bedolaga_factory: GatewayFactory,
        on_terminal: Callable[[ReferralReward], None] | None = None,
        on_registered: Callable[[ReferralReward], None] | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._panel_factory = panel_factory
        self._bedolaga_factory = bedolaga_factory
        # По умолчанию None: тесты ядра рефералки телеграм не знают
        # вовсе, а сборка для прода (referral_wiring.py) подставляет
        # функцию, которая шлёт сообщение через TelegramNotifier. Так
        # ReferralService не зависит от телеграма напрямую.
        self._on_terminal = on_terminal
        # register() заводит награду прямо из вебхука Platega, и
        # уведомление владельцу о ней шлёт checkout, увидев результат
        # register() своими глазами. sync_bot() заводит награду сама,
        # без какого-либо вызывающего снаружи, которому можно отдать
        # результат, и ей нужен свой способ позвать то же самое
        # уведомление: этот callback, а не правка checkout.py.
        self._on_registered = on_registered

    async def register(
        self,
        *,
        payment: Payment,
        friend_panel_user_id: int | None,
        friend_was_paid: bool,
    ) -> ReferralReward | None:
        """Завести награду за друга: за первую покупку или за продление.

        Пробуем сперва первую покупку (``_register_first_purchase``), а
        если она неприменима, отдельно пробуем продление
        (``_register_renewal``): это разные события в жизни одного и
        того же друга, и правило "первая покупка" не должно мешать
        правилу "продление" видеть тот же платёж.

        Ничего не выдаёт сама, только заводит запись. Выдачу делает
        ``process``, отдельно от ответа вебхуку: сбой панели или бота
        продаж здесь не должен помешать подтвердить платёж.
        """
        try:
            if not self._settings.referral_enabled:
                return None

            email = (payment.contact_email or "").strip().lower()
            if not email:
                return None

            reward = await self._register_first_purchase(
                payment=payment,
                email=email,
                friend_panel_user_id=friend_panel_user_id,
                friend_was_paid=friend_was_paid,
            )
            if reward is not None:
                return reward

            return await self._register_renewal(
                payment=payment,
                email=email,
                friend_panel_user_id=friend_panel_user_id,
            )
        except Exception:
            logger.exception("Рефералка: не удалось завести награду")
            await self._otkatit_bezopasno()
            return None

    async def _validate_inviter(
        self, panel: Any, username: str, days_if_paid: int
    ) -> tuple[Mapping[str, Any], Any, int] | None:
        """Проверить пригласившего в панели: общий код для обоих путей.

        Первая покупка и продление ищут пригласившего по одному и тому
        же имени учётки и принимают его по одним и тем же правилам
        (не интеграция, подписка жива, тег даёт право на награду),
        выносить эту проверку в двух местах по отдельности означало бы
        рано или поздно поправить только одно из них. Сколько дней
        положено за тег PAID, у путей разное (``days_if_paid``), и это
        решает вызывающий, а не сама проверка.

        Returns:
            Кортеж (сырой ответ панели, разобранный пользователь, дни
            пригласившему), либо None, если пригласившего не приняли.
        """
        try:
            inviter_raw = await panel.get_user_by_username(username)
        except RemnawaveUserNotFoundError:
            return None
        return _validate_inviter_payload(inviter_raw, days_if_paid)

    async def _cap_status(
        self, inviter_username: str, inviter_days: int
    ) -> str:
        """pending или held по потолку наград одному пригласившему за месяц.

        Тег ``SVOI`` (``inviter_days == 0``) потолок не расходует и не
        проверяет: ему всё равно нечего выдавать, и держать нулевые
        награды нет смысла.
        """
        if inviter_days <= 0:
            return "pending"
        # Считаем заведённые (pending/granted/failed), а не выданные:
        # несколько оплат подряд видели бы в старом granted_in_last_days
        # один и тот же ноль, потому что ни один process() ещё не успел
        # отработать, и пачка платежей в одну секунду пробивала бы
        # потолок целиком.
        #
        # Остаточная гонка: два по-настоящему одновременных register()
        # всё равно могут прочитать один и тот же counted до того, как
        # второй из них вставит свою запись, и оба пройдут потолок. Для
        # одного процесса uvicorn это редкое совпадение в пределах
        # одного event loop, а цена ошибки, одна лишняя награда сверх
        # потолка, а не потерянная защита, приемлема.
        counted = await self._store.counted_in_last_days(
            inviter_username, _CAP_WINDOW_DAYS
        )
        if counted >= self._settings.referral_monthly_cap:
            # Шестая и дальше ждут одобрения, но другу (если ему тут
            # что-то причитается) дни всё равно достанутся: process
            # выдаст их сразу.
            return "held"
        return "pending"

    async def _register_first_purchase(
        self,
        *,
        payment: Payment,
        email: str,
        friend_panel_user_id: int | None,
        friend_was_paid: bool,
    ) -> ReferralReward | None:
        """Первая оплата друга по коду из ссылки: дни обеим сторонам."""
        code = normalize_code(payment.referral_code)
        if code is None:
            return None

        if friend_was_paid:
            return None
        if await self._store.has_earlier_paid(email, payment.id):
            return None
        if await self._store.reward_exists(payment.id, email):
            return None

        async with self._panel_factory() as panel:
            validated = await self._validate_inviter(
                panel, code, self._settings.referral_inviter_days
            )
            if validated is None:
                return None
            inviter_raw, inviter_user, inviter_days = validated

            if friend_panel_user_id is not None:
                if inviter_user.id == friend_panel_user_id:
                    # Код совпал с собственной учёткой: это
                    # приглашение самого себя.
                    return None
                try:
                    friend_raw = await panel.get_user_by_id(
                        friend_panel_user_id
                    )
                except RemnawaveUserNotFoundError:
                    friend_raw = None
                if friend_raw is not None:
                    friend_username = str(friend_raw.get("username") or "")
                    if friend_username and (
                        friend_username.casefold() == code.casefold()
                    ):
                        return None

        status = await self._cap_status(
            inviter_user.username or code, inviter_days
        )

        reward = ReferralReward(
            payment_id=payment.id,
            friend_email=email,
            friend_panel_user_id=friend_panel_user_id,
            inviter_username=inviter_user.username or code,
            inviter_panel_user_id=inviter_user.id,
            inviter_telegram_id=_read_telegram_id(inviter_raw),
            friend_days=self._settings.referral_friend_days,
            inviter_days=inviter_days,
            kind="first",
            status=status,
            friend_granted_at=None,
            inviter_granted_at=None,
            attempts=0,
            last_error=None,
        )

        await self._store.add(reward)
        await self._store.save()
        return reward

    def _renewal_gap_is_satisfied(
        self, first_created_at: datetime, *, moment: datetime | None = None
    ) -> bool:
        """Прошло ли достаточно дней от первой покупки для продления.

        ``moment`` это момент, с которым сравнивается разрыв. По
        умолчанию берётся "сейчас": сайт узнаёт о втором платеже прямо
        в момент вебхука. Обход бота продаж передаёт время самой
        покупки (``completed_at``), потому что синхронизация с ботом
        случается заметно позже неё, и сравнение с "сейчас" посчитало
        бы разрыв больше, чем он был на самом деле в момент покупки.

        Ноль в настройке отключает проверку вовсе: значит, разделять
        вторую оплату того же вечера от настоящего продления через
        месяц владелец не просит.
        """
        gap_days = self._settings.referral_renewal_min_gap_days
        if gap_days <= 0:
            return True
        reference = (
            _as_aware_utc(moment) if moment is not None else datetime.now(UTC)
        )
        elapsed = reference - _as_aware_utc(first_created_at)
        return elapsed >= timedelta(days=gap_days)

    async def _register_renewal(
        self,
        *,
        payment: Payment,
        email: str,
        friend_panel_user_id: int | None,
    ) -> ReferralReward | None:
        """Первое продление друга после уже вознаграждённой первой покупки.

        В отличие от первой покупки, здесь нет ни кода в платеже (у
        продлевающегося друга в браузере его больше нет), ни проверки
        ``friend_was_paid`` (продлевающийся друг, конечно же, уже PAID):
        решает не платёж, а то, что у этой почты уже есть награда за
        первую покупку.
        """
        if self._settings.referral_renewal_days <= 0:
            return None

        first = await self._store.first_reward_for(email)
        if first is None or first.payment_id == payment.id:
            # Нет первой покупки, значит, и продлять как за друга
            # нечего. Совпавший id платежа означает тот же самый
            # платёж, что уже принёс first-награду (повторный вызов),
            # а не новое продление.
            #
            # Отдельной проверки "у этого payment_id ещё нет никакой
            # награды" тут больше нет: за неё в самом крайнем случае
            # отвечает уникальный индекс uq_referral_rewards_payment_id
            # в базе, тот же, что стоит на страже и у первой покупки, и
            # повторять его проверку средствами приложения незачем.
            return None
        if await self._store.renewal_exists(email):
            return None

        if not self._renewal_gap_is_satisfied(first.created_at):
            # Слишком рано после первой покупки: похоже на вторую
            # оплату тем же вечером, а не на настоящее продление месяц
            # спустя. Награду за это НЕ заводим (не rejected, а просто
            # никакой записи): друг ещё не истратил своё единственное
            # продление, и настоящее продление позже снова пройдёт
            # первую проверку выше (``renewal_exists``).
            return None

        async with self._panel_factory() as panel:
            validated = await self._validate_inviter(
                panel,
                first.inviter_username,
                self._settings.referral_renewal_days,
            )
            if validated is None:
                return None
            inviter_raw, inviter_user, inviter_days = validated

        if inviter_days == 0:
            # SVOI: пригласившему дни не положены вовсе, а другу на
            # продлении бонуса и так не бывает. Заводить запись, которая
            # никому ничего не даст, незачем.
            return None

        status = await self._cap_status(
            inviter_user.username or first.inviter_username, inviter_days
        )

        reward = ReferralReward(
            payment_id=payment.id,
            friend_email=email,
            friend_panel_user_id=friend_panel_user_id,
            inviter_username=inviter_user.username or first.inviter_username,
            inviter_panel_user_id=inviter_user.id,
            inviter_telegram_id=_read_telegram_id(inviter_raw),
            friend_days=0,
            inviter_days=inviter_days,
            kind="renewal",
            status=status,
            friend_granted_at=None,
            inviter_granted_at=None,
            attempts=0,
            last_error=None,
        )

        await self._store.add(reward)
        await self._store.save()
        return reward

    async def sync_bot(
        self, schedule: Callable[[UUID], None] | None = None
    ) -> int:
        """Обойти клиентов бота продаж и завести награды по общим правилам.

        Друг может прийти по ссылке не на сайт, а прямо в бота продаж:
        бот сам записывает ``referred_by_id`` при регистрации нового
        человека, и сайт узнаёт об этом только отсюда, периодическим
        обходом, а не вебхуком, как у покупки на сайте. Правила
        награды при этом ровно те же самые: приём пригласившего
        (``_validate_inviter_payload``), потолок (``_cap_status``) и
        разрыв дат для продления (``_renewal_gap_is_satisfied``) общие
        с ``register``, а не переизобретены здесь.

        Ничего не бросает наружу и не прерывает обход из-за одного
        сломанного кандидата: их за один проход может быть много, и
        сбой сети на одном из них не должен стоить наград всем
        остальным. Возвращает число заведённых наград.
        """
        if not (
            self._settings.referral_enabled
            and self._settings.referral_bot_enabled
            and self._settings.is_bedolaga_configured
        ):
            # Выключенный мост не должен сходить в бота продаж ни
            # разу: даже одно list_users() уже было бы лишним сетевым
            # походом при погашенной настройке.
            return 0

        created = 0
        try:
            async with (
                self._bedolaga_factory() as bedolaga,
                self._panel_factory() as panel,
            ):
                offset = 0
                for _ in range(_MAX_BOT_SYNC_PAGES):
                    users, total = await bedolaga.list_users(
                        limit=_BOT_SYNC_PAGE_SIZE, offset=offset
                    )
                    if not users:
                        break

                    for user in users:
                        if not (
                            user.referred_by_id is not None
                            and user.has_had_paid_subscription
                            and user.telegram_id is not None
                        ):
                            continue
                        reward = await self._sync_bot_candidate(
                            bedolaga, panel, user
                        )
                        if reward is None:
                            continue
                        created += 1
                        self._notify_registered(reward)
                        if schedule is not None:
                            schedule(reward.id)

                    offset += len(users)
                    if offset >= total:
                        break
        except Exception:
            logger.exception("Рефералка: обход бота продаж сорвался")
        return created

    async def _sync_bot_candidate(
        self, bedolaga: Any, panel: Any, user: Any
    ) -> ReferralReward | None:
        """Разобрать одного кандидата, не роняя весь обход при его сбое.

        Свой try/except на кандидата: обход бота продаж должен дойти
        до последнего кандидата даже если сеть подвела на середине
        списка, и сломанный кандидат не должен унести с собой награды
        всем, кто идёт после него в той же странице.
        """
        try:
            return await self._sync_one_candidate(bedolaga, panel, user)
        except Exception:
            logger.exception(
                "Рефералка: обход клиента %s бота продаж сорвался",
                user.id,
            )
            await self._otkatit_bezopasno()
            return None

    async def _sync_one_candidate(
        self, bedolaga: Any, panel: Any, user: Any
    ) -> ReferralReward | None:
        """Завести не больше одной награды за друга из бота продаж.

        За один проход у одного и того же друга появляется либо
        награда за первую покупку, либо за продление, никогда обе
        сразу: продление ждёт своего прохода после того, как первая
        покупка отработает до ``granted``/``held`` (этим занимается
        ``process``, а не обход).
        """
        friend_telegram_id = user.telegram_id
        friend_key = f"tg:{friend_telegram_id}"

        purchases = await bedolaga.purchases(user.id)
        if not purchases:
            # Только пополнял баланс, подписку в боте не покупал:
            # пополнение баланса наградой не является.
            return None

        first = await self._store.first_reward_for(friend_key)
        if first is None:
            if await self._store.bot_reward_exists(purchases[0].id):
                # Награда за эту же самую покупку уже где-то заведена
                # (pending, failed или rejected): у этой транзакции
                # id не изменится, и повторная попытка ничего нового
                # не принесёт. Отклонённая награда блокирует ровно так
                # же навсегда, как и на сайте.
                return None
            return await self._create_bot_first_reward(
                bedolaga, panel, user, purchases[0], friend_key,
                friend_telegram_id,
            )

        # first.status гарантированно granted или held: это условие
        # ``first_reward_for`` по контракту протокола.
        if self._settings.referral_renewal_days <= 0:
            return None
        if await self._store.renewal_exists(friend_key):
            return None

        renewal_purchase = next(
            (
                purchase
                for purchase in purchases
                if purchase.id != first.bot_transaction_id
                and self._renewal_gap_is_satisfied(
                    first.created_at, moment=purchase.completed_at
                )
            ),
            None,
        )
        if renewal_purchase is None:
            # Ни одна покупка (кроме самой первой) ещё не отстоит от
            # первой на нужный разрыв: настоящее продление придёт
            # позже, следующим проходом обхода.
            return None

        return await self._create_bot_renewal_reward(
            bedolaga, panel, user, first, renewal_purchase, friend_key,
            friend_telegram_id,
        )

    async def _resolve_bot_inviter(
        self,
        bedolaga: Any,
        panel: Any,
        *,
        referred_by_id: int,
        friend_telegram_id: int,
        days_if_paid: int,
    ) -> tuple[Mapping[str, Any], Any, int] | None:
        """Найти и проверить пригласившего из бота продаж.

        Пригласивший известен боту только числовым id
        (``referred_by_id``): у него может не быть телеграм-id вовсе
        (тогда награду некому отдать) или учётки в панели (тогда его
        и на сайте нет). Правила приёма после этого те же самые, что
        и у пригласившего с сайта (``_validate_inviter_payload``).
        """
        try:
            inviter_bot = await bedolaga.user_by_id(referred_by_id)
        except BedolagaUserNotFoundError:
            return None
        if inviter_bot.telegram_id is None:
            return None
        if inviter_bot.telegram_id == friend_telegram_id:
            # Пригласивший и друг это один и тот же человек в боте.
            return None
        try:
            inviter_raw = await panel.get_user_by_telegram_id(
                inviter_bot.telegram_id
            )
        except RemnawaveUserNotFoundError:
            return None
        return _validate_inviter_payload(inviter_raw, days_if_paid)

    async def _create_bot_first_reward(
        self,
        bedolaga: Any,
        panel: Any,
        user: Any,
        purchase: Any,
        friend_key: str,
        friend_telegram_id: int,
    ) -> ReferralReward | None:
        """Завести награду за первую покупку друга, пришедшего в бота."""
        validated = await self._resolve_bot_inviter(
            bedolaga,
            panel,
            referred_by_id=user.referred_by_id,
            friend_telegram_id=friend_telegram_id,
            days_if_paid=self._settings.referral_inviter_days,
        )
        if validated is None:
            return None
        inviter_raw, inviter_user, inviter_days = validated
        inviter_username = inviter_user.username or str(inviter_user.id)

        status = await self._cap_status(inviter_username, inviter_days)

        reward = ReferralReward(
            payment_id=None,
            source="bot",
            friend_email=friend_key,
            friend_panel_user_id=None,
            friend_telegram_id=friend_telegram_id,
            inviter_username=inviter_username,
            inviter_panel_user_id=inviter_user.id,
            inviter_telegram_id=_read_telegram_id(inviter_raw),
            bot_transaction_id=purchase.id,
            friend_days=self._settings.referral_friend_days,
            inviter_days=inviter_days,
            kind="first",
            status=status,
            friend_granted_at=None,
            inviter_granted_at=None,
            attempts=0,
            last_error=None,
        )
        return await self._save_bot_reward(reward)

    async def _create_bot_renewal_reward(
        self,
        bedolaga: Any,
        panel: Any,
        user: Any,
        first: ReferralReward,
        purchase: Any,
        friend_key: str,
        friend_telegram_id: int,
    ) -> ReferralReward | None:
        """Завести награду за продление друга, пришедшего в бота продаж."""
        validated = await self._resolve_bot_inviter(
            bedolaga,
            panel,
            referred_by_id=user.referred_by_id,
            friend_telegram_id=friend_telegram_id,
            days_if_paid=self._settings.referral_renewal_days,
        )
        if validated is None:
            return None
        inviter_raw, inviter_user, inviter_days = validated

        if inviter_days == 0:
            # SVOI: пригласившему дни не положены вовсе, а другу на
            # продлении и так не бывает бонуса сверху. Заводить пустую
            # запись, которая никому ничего не даст, незачем, как и на
            # сайте.
            return None

        inviter_username = inviter_user.username or first.inviter_username
        status = await self._cap_status(inviter_username, inviter_days)

        reward = ReferralReward(
            payment_id=None,
            source="bot",
            friend_email=friend_key,
            friend_panel_user_id=None,
            friend_telegram_id=friend_telegram_id,
            inviter_username=inviter_username,
            inviter_panel_user_id=inviter_user.id,
            inviter_telegram_id=_read_telegram_id(inviter_raw),
            bot_transaction_id=purchase.id,
            friend_days=0,
            inviter_days=inviter_days,
            kind="renewal",
            status=status,
            friend_granted_at=None,
            inviter_granted_at=None,
            attempts=0,
            last_error=None,
        )
        return await self._save_bot_reward(reward)

    async def _save_bot_reward(
        self, reward: ReferralReward
    ) -> ReferralReward | None:
        """Сохранить новую награду из обхода бота продаж.

        Один и тот же transaction_id может попасться дважды, если два
        прохода обхода наложились друг на друга: unique-индекс базы
        отбивает вторую вставку сам, и это штатный случай, о котором
        достаточно короткой строки в лог, а не трассы исключения.
        """
        await self._store.add(reward)
        try:
            await self._store.save()
        except IntegrityError:
            logger.info(
                "Рефералка: награда за транзакцию %s из бота продаж "
                "уже заведена другим проходом обхода",
                reward.bot_transaction_id,
            )
            await self._store.rollback()
            return None
        return reward

    async def process_by_id(self, reward_id: UUID) -> None:
        """Обработать награду по id: вход для фоновой задачи со своей сессией.

        И сразу после ``register``, и на периодическом обходе к этому
        моменту известен только id награды: сама запись живёт в чужой
        сессии либо не читалась вовсе. Награды не удаляются, и
        пропажа записи означала бы ошибку где-то ещё, а не штатный
        случай, поэтому здесь предупреждение в лог, а не тихий возврат.
        """
        reward = await self._store.get(reward_id)
        if reward is None:
            logger.warning(
                "Рефералка: награда %s не найдена для обработки", reward_id
            )
            return
        await self.process(reward)

    async def process(self, reward: ReferralReward) -> None:
        """Выдать то, что причитается по записи и ещё не выдано.

        Каждая удачная выдача сохраняется сразу же, до следующего
        сетевого вызова: повтор после сбоя должен продлить только то,
        что не продлилось в прошлый раз.

        Фоновая задача, которую ``checkout`` запускает сразу после
        ``register``, и периодический обход зависших наград читают
        одну и ту же запись каждый из своей сессии: держим замок на
        всё время обработки и первым делом перечитываем состояние
        записи, чтобы второй обработчик увидел, что первый уже успел
        сделать.

        Уведомление об итоге (``on_terminal``) уходит ровно один раз,
        на самом переходе в granted или failed. ``entered`` держит,
        дошла ли эта обработка до самой работы: если запись уже была
        терминальной, ранний возврат ниже сработает раньше, чем
        ``entered`` станет True, и повторный ``process`` на готовой
        награде ничего не пошлёт.
        """
        lock = _lock_for(reward.id)
        entered = False
        async with lock:
            try:
                await self._store.refresh(reward)

                if reward.status not in ("pending", "held"):
                    return
                entered = True

                # Продление (kind="renewal") ничего не должно другу:
                # friend_days == 0, и звать панель за нулём дней незачем.
                # friend_granted_at у такой награды навсегда останется
                # пустым, единственное, что на него смотрит, это же
                # самое условие чуть выше, и повторный process() снова
                # безопасно пропустит этот шаг.
                if reward.friend_granted_at is None and reward.friend_days > 0:
                    granted = await self._grant_friend(reward)
                    if not granted:
                        return

                if reward.status == "held":
                    # Другу выдано, а снятие потолка пригласившему
                    # дожидается человека, а не фоновой задачи.
                    return

                if reward.inviter_days == 0:
                    if reward.status != "granted":
                        reward.status = "granted"
                        await self._store.save()
                    return

                if reward.inviter_granted_at is None:
                    granted = await self._grant_inviter(reward)
                    if not granted:
                        return

                reward.status = "granted"
                await self._store.save()
            except Exception:
                logger.exception(
                    "Рефералка: сбой обработки награды %s", reward.id
                )
            finally:
                if entered and reward.status in _TERMINAL_STATUSES:
                    self._notify_terminal(reward)
                if reward.status in _TERMINAL_STATUSES:
                    _release_lock(reward.id)

    def _notify_terminal(self, reward: ReferralReward) -> None:
        """Позвать внешний callback об итоге, не давая ему испортить награду.

        Свой try/except: сбой похода в телеграм (или любой другой
        callback, который подставит сборка) не должен менять статус
        награды и не должен подняться выше ``process``.
        """
        if self._on_terminal is None:
            return
        try:
            self._on_terminal(reward)
        except Exception:
            logger.exception(
                "Рефералка: обработчик итогового уведомления упал по "
                "награде %s",
                reward.id,
            )

    def _notify_registered(self, reward: ReferralReward) -> None:
        """Позвать внешний callback о новой награде из бота продаж.

        Свой try/except, тем же приёмом, что и у ``_notify_terminal``:
        сбой похода в телеграм не должен прервать обход бота продаж,
        у которого впереди могут быть ещё десятки кандидатов.
        """
        if self._on_registered is None:
            return
        try:
            self._on_registered(reward)
        except Exception:
            logger.exception(
                "Рефералка: обработчик новой награды упал по награде %s",
                reward.id,
            )

    async def device_overlaps(
        self, since: datetime
    ) -> list[tuple[ReferralReward, int]]:
        """Найти среди свежих наград совпадающие по устройствам.

        Совпадение никого не наказывает само: список идёт человеку,
        а решение (``release``/``reject`` в административном разделе)
        остаётся за ним. Один и тот же пригласивший часто встречается
        в нескольких наградах сразу, и его устройства запрашиваются в
        панели один раз на весь обход, а не на каждую награду.

        Сбой панели по одной награде не должен ронять весь обход:
        такая награда просто пропускается, а метод целиком исключений
        не поднимает (его зовёт фоновая задача, которой падать нельзя).
        """
        try:
            rewards = await self._store.recent(since)
        except Exception:
            logger.exception("Рефералка: не удалось получить свежие награды")
            return []

        hits: list[tuple[ReferralReward, int]] = []
        if not rewards:
            return hits

        inviter_cache: dict[int, frozenset[str] | None] = {}
        try:
            async with self._panel_factory() as panel:
                for reward in rewards:
                    if reward.friend_panel_user_id is None:
                        continue

                    friend_hwids = await self._safe_hwids(
                        panel,
                        reward.friend_panel_user_id,
                        reward.id,
                        "друга",
                    )
                    if friend_hwids is None:
                        continue

                    inviter_id = reward.inviter_panel_user_id
                    if inviter_id not in inviter_cache:
                        inviter_cache[inviter_id] = await self._safe_hwids(
                            panel, inviter_id, reward.id, "пригласившего"
                        )
                    inviter_hwids = inviter_cache[inviter_id]
                    if inviter_hwids is None:
                        continue

                    common = friend_hwids & inviter_hwids
                    if common:
                        hits.append((reward, len(common)))
        except Exception:
            logger.exception("Рефералка: сверка устройств сорвалась")
            return []
        return hits

    async def _safe_hwids(
        self,
        panel: Any,
        user_id: int,
        reward_id: UUID,
        kto: str,
    ) -> frozenset[str] | None:
        """Устройства пользователя панели, либо None при сбое похода.

        None отличается от пустого множества: сбой панели должен
        пропустить награду целиком, а настоящее отсутствие устройств
        (человек просто не подключился) пропускать её не должно.
        """
        try:
            devices = await panel.list_devices(user_id)
        except Exception:
            logger.exception(
                "Рефералка: не удалось получить устройства %s по "
                "награде %s",
                kto,
                reward_id,
            )
            return None
        return frozenset(
            device.get("hwid")
            for device in devices
            if isinstance(device.get("hwid"), str) and device.get("hwid")
        )

    async def _grant_friend(self, reward: ReferralReward) -> bool:
        """Продлить подписку друга. True значит: выдано или уже было.

        Друг с сайта живёт только в панели, и продление идёт напрямую
        ниже. Друг, пришедший в бота продаж (``source == "bot"``),
        живёт своей подпиской в самом боте, и ему сюда дороги нет:
        ``_grant_friend_via_bot`` продлевает его через Bedolaga, а
        панель не трогает вовсе, потому что бот сам синхронизирует
        срок с панелью и переписал бы любое прямое продление панели
        своим же сроком при следующей сверке.
        """
        if reward.source == "bot":
            return await self._grant_friend_via_bot(reward)

        if reward.friend_panel_user_id is None:
            # Идентификатор учётки друга обязан прийти с самого начала
            # (Task 4 передаёт его всегда); выводить имя из почты здесь
            # означало бы завести циклический импорт с checkout и, хуже
            # того, продлить не ту учётку, если имя из почты кому-то
            # уже принадлежит.
            await self._record_failure(
                reward, "у награды нет id учётки друга в панели"
            )
            return False

        try:
            async with self._panel_factory() as panel:
                friend_raw = await panel.get_user_by_id(
                    reward.friend_panel_user_id
                )
                friend = read_panel_user(friend_raw)
                base = max(friend.expires_at, date.today())
                expires_at = base + timedelta(days=reward.friend_days)
                await panel.set_expiry(
                    friend.id,
                    datetime.combine(
                        expires_at, datetime.min.time(), tzinfo=UTC
                    ),
                )
        except Exception as error:
            logger.exception(
                "Рефералка: не удалось выдать дни другу по награде %s",
                reward.id,
            )
            await self._record_failure(reward, f"не выдано другу: {error}")
            return False

        reward.friend_granted_at = datetime.now(UTC)
        try:
            await self._store.save()
        except Exception:
            await self._mark_unrecoverable(reward, "friend")
            return False
        return True

    async def _grant_friend_via_bot(self, reward: ReferralReward) -> bool:
        """Продлить подписку друга из бота продаж через сам бот.

        Отсутствие ``friend_panel_user_id`` тут нормально, а не сбой:
        друг из бота продаж мог никогда не заходить на сайт и вовсе
        не иметь учётки в панели. ``BedolagaUserNotFoundError`` значит,
        что у друга в боте только пробный период (там оплаченной
        подписки не бывает): продлевать нечего, и падать в панель
        нельзя, потому что бот перепишет срок своим при следующей
        сверке.
        """
        try:
            async with self._bedolaga_factory() as bedolaga:
                try:
                    subscription_id = (
                        await bedolaga.subscription_id_by_telegram_id(
                            reward.friend_telegram_id
                        )
                    )
                except BedolagaUserNotFoundError as error:
                    logger.warning(
                        "Рефералка: у друга по награде %s в боте "
                        "только триал",
                        reward.id,
                    )
                    await self._record_failure(
                        reward, f"у друга в боте только триал: {error}"
                    )
                    return False
                await bedolaga.extend(subscription_id, reward.friend_days)
        except Exception as error:
            logger.exception(
                "Рефералка: не удалось выдать дни другу из бота продаж "
                "по награде %s",
                reward.id,
            )
            await self._record_failure(reward, f"не выдано другу: {error}")
            return False

        reward.friend_granted_at = datetime.now(UTC)
        try:
            await self._store.save()
        except Exception:
            await self._mark_unrecoverable(reward, "friend")
            return False
        return True

    async def _grant_inviter(self, reward: ReferralReward) -> bool:
        """Продлить подписку пригласившего. True: выдано или уже было."""
        try:
            if reward.inviter_telegram_id is not None:
                async with self._bedolaga_factory() as bedolaga:
                    try:
                        subscription_id = (
                            await bedolaga.subscription_id_by_telegram_id(
                                reward.inviter_telegram_id
                            )
                        )
                    except BedolagaUserNotFoundError as error:
                        # У бота нашёлся только триал, продлевать
                        # нечего, а падать в панель нельзя: бот
                        # перезапишет срок своим при следующей сверке.
                        logger.warning(
                            "Рефералка: у пригласившего по награде %s в "
                            "боте только триал",
                            reward.id,
                        )
                        await self._record_failure(
                            reward,
                            f"у пригласившего в боте только триал: {error}",
                        )
                        return False
                    await bedolaga.extend(subscription_id, reward.inviter_days)
            else:
                async with self._panel_factory() as panel:
                    inviter_raw = await panel.get_user_by_id(
                        reward.inviter_panel_user_id
                    )
                    inviter = read_panel_user(inviter_raw)
                    base = max(inviter.expires_at, date.today())
                    expires_at = base + timedelta(days=reward.inviter_days)
                    await panel.set_expiry(
                        inviter.id,
                        datetime.combine(
                            expires_at, datetime.min.time(), tzinfo=UTC
                        ),
                    )
        except Exception as error:
            logger.exception(
                "Рефералка: не удалось выдать дни пригласившему по "
                "награде %s",
                reward.id,
            )
            await self._record_failure(
                reward, f"не выдано пригласившему: {error}"
            )
            return False

        reward.inviter_granted_at = datetime.now(UTC)
        try:
            await self._store.save()
        except Exception:
            await self._mark_unrecoverable(reward, "inviter")
            return False
        return True

    async def _record_failure(
        self, reward: ReferralReward, message: str
    ) -> None:
        """Отметить неудачную попытку, а после многих сдаться.

        Сохраняет сама: это последняя запись, которую в данной попытке
        можно сделать, и мёртвое хранилище тут не должно ронять того,
        кто вызвал ``_record_failure`` из своего except.
        """
        reward.attempts += 1
        reward.last_error = message[:_MAX_ERROR_LENGTH]
        if reward.attempts >= _MAX_ATTEMPTS:
            reward.status = "failed"
        try:
            await self._store.save()
        except Exception:
            logger.exception(
                "Рефералка: не удалось сохранить попытку по награде %s",
                reward.id,
            )
            await self._otkatit_bezopasno()

    async def _mark_unrecoverable(
        self, reward: ReferralReward, side: str
    ) -> None:
        """Дни выдались, а отметка об этом не сохранилась.

        Повтор тут же продлил бы того, кому уже продлили: единственный
        безопасный выход это перестать трогать награду автоматикой и
        отдать её человеку. Пробуем сохранить это решение ещё раз, но
        отдельным try/except: если хранилище мёртвое и вторая попытка
        тоже упадёт, объект в памяти всё равно останется failed, а
        трасса уйдёт в лог.
        """
        reward.status = "failed"
        reward.last_error = (
            f"выдано, но не сохранено: нужна проверка вручную ({side})"
        )[:_MAX_ERROR_LENGTH]
        logger.exception(
            "Рефералка: выдано (%s) по награде %s, но не сохранилось; "
            "нужна ручная проверка",
            side,
            reward.id,
        )
        try:
            await self._store.save()
        except Exception:
            logger.exception(
                "Рефералка: не удалось сохранить отметку failed по "
                "награде %s",
                reward.id,
            )
            await self._otkatit_bezopasno()

    async def _otkatit_bezopasno(self) -> None:
        """Откатить сессию после сбоя, не давая самому откату всё уронить.

        Хранилище в этой сессии могло уже упасть один раз: если и
        rollback не выйдет, обработке всё равно нужно закончиться и
        отдать след в лог, а не поднять исключение выше себя.
        """
        try:
            await self._store.rollback()
        except Exception:
            logger.exception("Рефералка: не удалось откатить сессию")
