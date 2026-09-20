"""Ссылка на бота продаж для друга, пришедшего по приглашению.

Страница покупки хочет предложить пришедшему по ссылке купить не на
сайте, а прямо в боте продаж, и для этого ей нужно превратить код
пригласившего в ссылку вида ``https://t.me/<бот>?start=<код в боте>``.
Сама эта проверка не решает, положена ли награда: она только смотрит,
жив ли пригласивший в панели и знает ли его бот продаж. Право на
награду (тег PAID/SVOI) проверяется заново и отдельно в момент самой
покупки (``ReferralService``), а не здесь.

Приватность: маршрут, построенный вокруг этого резолвера, раскрывает
только то, что данное имя учётки в панели принадлежит активному
клиенту с привязанным ботом продаж. Это и так известно всякому, у кого
на руках ссылка с этим кодом, потому что код и есть то самое имя
учётки.
"""

import logging
import re
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any
from urllib.parse import quote

from app.core.config import Settings
from app.integrations.bedolaga.client import (
    BedolagaGateway,
    BedolagaUserNotFoundError,
)
from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveUserNotFoundError,
)
from app.services.referral import normalize_code

logger = logging.getLogger(__name__)

__all__ = ["InviteResolver"]

# Кэш держит код на 10 минут: этого достаточно, чтобы один и тот же
# друг, обновляющий страницу покупки, не долбил панель и бота продаж
# на каждый показ, но не настолько долго, чтобы свежая покупка друга
# застряла в устаревшем "нет ссылки".
_CACHE_TTL_SECONDS = 600.0
# Больше 500 разных кодов в кэше не держим: это не то место, где стоит
# копить память без предела ради кода, который никто больше не покажет.
_CACHE_MAX_ENTRIES = 500

# Маршрут открыт всем, а каждый промах кэша это запрос в панель и, возможно,
# в бота продаж. Перебором разных кодов кэш обходится, поэтому походы наружу
# ограничены на весь процесс: сверх лимита ответ пустой и в кэш не пишется,
# чтобы настоящая ссылка заработала, как только окно освободится. Заодно это
# тормозит перебор имён учёток через этот маршрут.
_LOOKUPS_PER_WINDOW = 30
_LOOKUP_WINDOW_SECONDS = 60.0

_SINERGIYA_RE = re.compile(r"^OOO_SINERGIYA_", re.IGNORECASE)

GatewayFactory = Callable[[Settings], AbstractAsyncContextManager[Any]]

# Отличает "в кэше нет записи" от "в кэше есть запись со значением None"
# (ссылки нет, но это уже проверено и это тоже кэшируется).
_MISS = object()


def _passes_basic_checks(raw: Mapping[str, Any]) -> bool:
    """Пригласивший достаточно жив для ссылки в бота, не для награды.

    Это не полная проверка приёма пригласившего
    (``_validate_inviter_payload`` в ``referral.py`` смотрит ещё тег
    PAID/SVOI): здесь достаточно убедиться, что учётка не интеграция
    и не отключена. Раскрывать через открытый маршрут больше, чем
    "жив или не жив", то есть проверять тег заранее, смысла нет: тег
    всё равно проверится при самой покупке.
    """
    username = str(raw.get("username") or "")
    if _SINERGIYA_RE.match(username):
        return False
    status = str(raw.get("status") or "").upper()
    return status == "ACTIVE"


def _read_telegram_id(raw: Mapping[str, Any]) -> int | None:
    """Достать telegramId из ответа панели, как это делает referral.py.

    Своя копия, а не импорт приватной функции из ``referral.py``:
    этот модуль не должен зависеть от того, что переживёт правки в
    том файле, который сейчас на отдельном ревью.
    """
    value = raw.get("telegramId")
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


class InviteResolver:
    """Резолвер ссылки на бота продаж с кэшем в памяти на один процесс.

    Шлюзы приходят фабриками от настроек (``Settings -> шлюз``), а не
    готовыми объектами: резолвер живёт как единственный экземпляр на
    всё приложение (см. ``api/dependencies.get_invite_resolver``) и
    не должен держать соединение, открытое под настройки первого же
    запроса, который его создал.
    """

    def __init__(
        self,
        *,
        panel_factory: GatewayFactory | None = None,
        bedolaga_factory: GatewayFactory | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._panel_factory = panel_factory or (
            lambda settings: RemnawaveGateway(settings)
        )
        self._bedolaga_factory = bedolaga_factory or (
            lambda settings: BedolagaGateway(settings)
        )
        self._clock = clock
        # OrderedDict в порядке добавления: самая старая запись всегда
        # первая, и eviction снимает именно её (FIFO), без отдельного
        # учёта времени создания.
        self._cache: OrderedDict[str, tuple[float, str | None]] = (
            OrderedDict()
        )
        # Моменты последних походов наружу, для ограничителя выше.
        self._lookups: deque[float] = deque()

    async def resolve(
        self, raw_code: str | None, settings: Settings
    ) -> str | None:
        """Отдать ссылку на бота продаж или None, не поднимая исключений.

        На выключенном мосте выходит раньше любой проверки кода и
        раньше кэша: даже чтение кэша здесь было бы лишней работой,
        когда ответ всегда один и тот же.
        """
        try:
            return await self._resolve(raw_code, settings)
        except Exception:
            # Без деталей кода или его пригласившего: предупреждение
            # не должно превращаться в журнал того, кто чей код искал.
            logger.warning("Рефералка: приглашение - резолвер сорвался")
            return None

    async def _resolve(
        self, raw_code: str | None, settings: Settings
    ) -> str | None:
        if not (
            settings.referral_enabled
            and settings.referral_bot_enabled
            and settings.is_bedolaga_configured
        ):
            return None

        code = normalize_code(raw_code)
        if code is None:
            return None

        cached = self._from_cache(code)
        if cached is not _MISS:
            return cached

        if not self._lookup_allowed():
            logger.warning("Слишком много запросов ссылки приглашения")
            return None

        url = await self._lookup(code, settings)
        self._store(code, url)
        return url

    def _lookup_allowed(self) -> bool:
        """Пустить поход наружу, если в текущем окне ещё есть место."""
        now = self._clock()
        window_start = now - _LOOKUP_WINDOW_SECONDS
        while self._lookups and self._lookups[0] <= window_start:
            self._lookups.popleft()
        if len(self._lookups) >= _LOOKUPS_PER_WINDOW:
            return False
        self._lookups.append(now)
        return True

    async def _lookup(self, code: str, settings: Settings) -> str | None:
        """Сходить в панель и в бота продаж за ссылкой одного кода.

        "Не найден" в панели или в боте это обычный исход, не ошибка:
        сюда прилетают чужие имена учёток из чужих ссылок, и часть из
        них не найдётся никогда. Другие сбои (сеть, неверный ключ)
        поднимаются наружу, и их ловит ``resolve``.
        """
        try:
            async with self._panel_factory(settings) as panel:
                inviter_raw = await panel.get_user_by_username(code)
        except RemnawaveUserNotFoundError:
            return None

        if not _passes_basic_checks(inviter_raw):
            return None

        telegram_id = _read_telegram_id(inviter_raw)
        if telegram_id is None:
            return None

        try:
            async with self._bedolaga_factory(settings) as bedolaga:
                bot_user = await bedolaga.user_by_telegram_id(telegram_id)
        except BedolagaUserNotFoundError:
            return None

        if not bot_user.referral_code:
            return None

        username = settings.telegram_sales_bot_username
        code_in_bot = quote(bot_user.referral_code, safe="")
        return f"https://t.me/{username}?start={code_in_bot}"

    def _from_cache(self, code: str) -> Any:
        entry = self._cache.get(code)
        if entry is None:
            return _MISS
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._cache[code]
            return _MISS
        return value

    def _store(self, code: str, value: str | None) -> None:
        # Переставляем существующий ключ в конец, чтобы порядок
        # OrderedDict всегда отражал порядок последнего обновления, а
        # не только первого добавления.
        if code in self._cache:
            del self._cache[code]
        self._cache[code] = (self._clock() + _CACHE_TTL_SECONDS, value)
        if len(self._cache) > _CACHE_MAX_ENTRIES:
            self._cache.popitem(last=False)
