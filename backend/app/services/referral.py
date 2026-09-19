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

GatewayFactory = Callable[[], AbstractAsyncContextManager[Any]]

# Блокировки по id награды, общие для всех экземпляров ReferralService
# в процессе: фоновая задача, запущенная сразу после register, и
# периодический обход читают одну и ту же запись каждый из своей
# сессии, и оба должны видеть одну и ту же блокировку, а не свою
# локальную.
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
        """Награда по этому платежу или почте уже заведена."""
        ...

    async def add(self, reward: ReferralReward) -> None:
        """Завести новую запись награды."""
        ...

    async def get(self, reward_id: UUID) -> ReferralReward | None:
        """Найти запись награды по id, если она ещё существует."""
        ...

    async def granted_in_last_days(
        self, inviter_username: str, days: int
    ) -> int:
        """Сколько раз пригласившему уже выдали награду за окно дней."""
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
        Дни считаются только по уже выданным наградам: то, что ждёт
        своей очереди, здесь не в счёт.
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
                    func.lower(ReferralReward.friend_email) == email.lower(),
                )
            )
            .limit(1)
        )
        return await self._session.scalar(stmt) is not None

    async def add(self, reward: ReferralReward) -> None:
        self._session.add(reward)

    async def get(self, reward_id: UUID) -> ReferralReward | None:
        return await self._session.get(ReferralReward, reward_id)

    async def granted_in_last_days(
        self, inviter_username: str, days: int
    ) -> int:
        threshold = datetime.now(UTC) - timedelta(days=days)
        stmt = select(func.count()).where(
            ReferralReward.inviter_username == inviter_username,
            ReferralReward.inviter_granted_at.is_not(None),
            ReferralReward.inviter_granted_at >= threshold,
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
            or_(
                ReferralReward.inviter_granted_at.is_not(None),
                and_(
                    ReferralReward.inviter_days == 0,
                    ReferralReward.status == "granted",
                ),
            ),
        )
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


def _inviter_days(raw: Mapping[str, Any], settings: Settings) -> int | None:
    """Сколько дней причитается пригласившему, либо None, если не принят.

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
        return settings.referral_inviter_days
    return None


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
    ) -> None:
        self._settings = settings
        self._store = store
        self._panel_factory = panel_factory
        self._bedolaga_factory = bedolaga_factory

    async def register(
        self,
        *,
        payment: Payment,
        friend_panel_user_id: int | None,
        friend_was_paid: bool,
    ) -> ReferralReward | None:
        """Завести награду за первую оплату друга, если она положена.

        Ничего не выдаёт сама, только заводит запись. Выдачу делает
        ``process``, отдельно от ответа вебхуку: сбой панели или бота
        продаж здесь не должен помешать подтвердить платёж.
        """
        try:
            if not self._settings.referral_enabled:
                return None

            code = normalize_code(payment.referral_code)
            if code is None:
                return None

            email = (payment.contact_email or "").strip().lower()
            if not email:
                return None

            if friend_was_paid:
                return None
            if await self._store.has_earlier_paid(email, payment.id):
                return None
            if await self._store.reward_exists(payment.id, email):
                return None

            async with self._panel_factory() as panel:
                try:
                    inviter_raw = await panel.get_user_by_username(code)
                except RemnawaveUserNotFoundError:
                    return None

                inviter_user = read_panel_user(inviter_raw)

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

            inviter_days = _inviter_days(inviter_raw, self._settings)
            if inviter_days is None:
                return None

            status = "pending"
            if inviter_days > 0:
                granted = await self._store.granted_in_last_days(
                    inviter_user.username or code, _CAP_WINDOW_DAYS
                )
                if granted >= self._settings.referral_monthly_cap:
                    # Шестая и дальше ждут одобрения, но другу дни
                    # всё равно причитаются: process выдаст их сразу.
                    status = "held"

            reward = ReferralReward(
                payment_id=payment.id,
                friend_email=email,
                friend_panel_user_id=friend_panel_user_id,
                inviter_username=inviter_user.username or code,
                inviter_panel_user_id=inviter_user.id,
                inviter_telegram_id=_read_telegram_id(inviter_raw),
                friend_days=self._settings.referral_friend_days,
                inviter_days=inviter_days,
                status=status,
                friend_granted_at=None,
                inviter_granted_at=None,
                attempts=0,
                last_error=None,
            )

            await self._store.add(reward)
            await self._store.save()
            return reward
        except Exception:
            logger.exception("Рефералка: не удалось завести награду")
            await self._otkatit_bezopasno()
            return None

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
        """
        lock = _lock_for(reward.id)
        async with lock:
            try:
                await self._store.refresh(reward)

                if reward.status not in ("pending", "held"):
                    return

                if reward.friend_granted_at is None:
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
                if reward.status in _TERMINAL_STATUSES:
                    _release_lock(reward.id)

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
        """Продлить подписку друга в панели. True значит: выдано или уже было.

        Друг всегда клиент сайта: подписка у него только в панели, ни
        Bedolaga тут ни при чём.
        """
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
