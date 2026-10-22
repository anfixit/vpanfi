"""Кошелёк человека: он один на сайт и бота продаж.

Своего баланса сайт не ведёт. Деньги лежат в боте продаж, и кабинет
только показывает их: иначе человек пополнил бы один кошелёк, а увидел
другой и не понял, куда делись деньги.

Сопоставляются учётки двумя ключами. Телеграм-идентификатор надёжнее:
он берётся из подтверждённой привязки на сайте, а не из слов человека.
Кому Telegram недоступен (а сайт нужен ровно таким людям), остаётся
ссылка подписки: её короткий идентификатор бот отдаёт наружу, и сайт
знает его от панели.

Ни одна поломка здесь не ломает кабинет: не нашли человека, бот не
настроен, бот молчит — баланса просто нет, и карточки в кабинете тоже
нет. Нуль вместо неизвестной суммы был бы ложью.
"""

import logging

from app.core.config import Settings
from app.integrations.bedolaga.client import (
    BedolagaError,
    BedolagaGateway,
    BedolagaNotConfiguredError,
    BedolagaUserNotFoundError,
    BotUser,
)
from app.integrations.remnawave.client import extract_short_uuid
from app.models.user import IdentityProvider, User

logger = logging.getLogger(__name__)

__all__ = ["WalletService"]


class WalletService:
    """Сумма кошелька человека из бота продаж."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def balance_kopeks(
        self,
        user: User,
        *,
        subscription_url: str | None = None,
    ) -> int | None:
        """Сколько у человека денег в копейках, или None.

        None означает «неизвестно», и причин ровно четыре: мост к боту
        не настроен, ключей сопоставления нет, человека в боте нет, бот
        не ответил. Разница между ними важна для журнала, но не для
        кабинета: показывать нечего во всех четырёх случаях.

        Args:
            user: Пользователь кабинета вместе с его привязками.
            subscription_url: Ссылка подписки из панели, если кабинет
                её уже спросил. Второй ключ сопоставления для людей без
                привязанного Telegram.
        """
        if not self._settings.is_bedolaga_configured:
            return None

        telegram_id = _telegram_id(user)
        short_uuid = (
            extract_short_uuid(subscription_url)
            if subscription_url is not None
            else None
        )
        if telegram_id is None and short_uuid is None:
            return None

        try:
            bot_user = await self._find(telegram_id, short_uuid)
        except BedolagaNotConfiguredError:
            return None
        except BedolagaUserNotFoundError:
            # Человека нет в боте вовсе: обычное дело для тех, кто
            # пришёл прямо на сайт и в Telegram не заходил.
            return None
        except BedolagaError:
            # Шлюз уже написал в журнал, что именно случилось.
            return None

        return bot_user.balance_kopeks

    async def _find(
        self,
        telegram_id: int | None,
        short_uuid: str | None,
    ) -> BotUser:
        """Найти человека в боте одним ключом, затем другим.

        Raises:
            BedolagaUserNotFoundError: Ни один ключ не нашёл человека.
            BedolagaError: Бот недоступен или не настроен.
        """
        async with BedolagaGateway(self._settings) as gateway:
            if telegram_id is not None:
                try:
                    return await gateway.user_by_telegram_id(telegram_id)
                except BedolagaUserNotFoundError:
                    # Привязан Telegram, а в боте человека нет: он мог
                    # покупать подписку только на сайте. Ссылка
                    # подписки — второй шанс его узнать.
                    if short_uuid is None:
                        raise

            if short_uuid is None:
                raise BedolagaUserNotFoundError("no lookup key")

            return await gateway.user_by_subscription_short_uuid(short_uuid)


def _telegram_id(user: User) -> int | None:
    """Телеграм-идентификатор из подтверждённой привязки на сайте.

    Привязок у человека может не быть вовсе, а у бота идентификатор
    числовой: нечисловое значение означает чужой формат, и доверять
    ему нельзя.
    """
    for identity in user.identities:
        if identity.provider is not IdentityProvider.TELEGRAM:
            continue
        try:
            return int(identity.provider_user_id)
        except ValueError:
            logger.warning("Привязка Telegram с нечисловым id")
            return None
    return None
