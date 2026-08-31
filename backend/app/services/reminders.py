"""Напоминания покупателям сайта о том, что подписка кончается.

Бот такие письма шлёт давно, но только тем, кто в нём есть. Покупателя
сайта там нет: он платит почтой, без телеграма. Поэтому сайт продавал,
выдавал доступ и замолкал навсегда, а человек узнавал об окончании,
когда переставал работать интернет.

На 31.08.2026 половина платящих не связана с ботом. Для тех из них,
у кого есть кабинет на сайте, это единственный способ предупредить.
"""

import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.integrations.remnawave.client import (
    RemnawaveGateway,
    RemnawaveUnavailableError,
    RemnawaveUserNotFoundError,
)
from app.models.reminder import SubscriptionReminder
from app.models.user import User
from app.services.letters import subscription_expiring_letter
from app.services.mail import Mailer, MailNotConfiguredError
from app.services.panel import read_panel_user

logger = logging.getLogger(__name__)

__all__ = ["RemindersService"]


class RemindersService:
    """Предупреждает об окончании подписки по почте."""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def run_once(self) -> int:
        """Обойти всех и разослать то, что причитается.

        Возвращает число отправленных писем. Наверх ничего не бросает:
        обход идёт по расписанию, и падение из-за одного человека
        оставило бы без предупреждения всех остальных.
        """
        if not self._settings.reminder_days_list:
            return 0
        if not self._settings.is_mail_configured:
            logger.warning("Почта не настроена: напоминания не разосланы")
            return 0

        users = list(
            await self._session.scalars(
                select(User).where(
                    User.remnawave_user_id.is_not(None),
                    User.is_active.is_(True),
                )
            )
        )
        if not users:
            return 0

        otpravleno = 0
        try:
            async with RemnawaveGateway(self._settings) as panel:
                for user in users:
                    try:
                        otpravleno += await self._odin(user, panel)
                    except RemnawaveUserNotFoundError:
                        # Учётку удалили из панели, а кабинет остался.
                        continue
                    except Exception:
                        logger.exception(
                            "Напоминание не обработано: %s", user.email
                        )
        except RemnawaveUnavailableError:
            logger.warning("Панель не отвечает: напоминания отложены")

        return otpravleno

    async def _odin(self, user: User, panel: RemnawaveGateway) -> int:
        assert user.remnawave_user_id is not None
        payload = await panel.get_user_by_id(user.remnawave_user_id)
        panel_user = read_panel_user(payload)
        expires_on = panel_user.expires_at
        if expires_on is None:
            return 0

        ostalos = (expires_on - datetime.now(UTC).date()).days
        if ostalos < 0:
            # Срок уже вышел, предупреждать поздно.
            return 0

        porog = self._porog(ostalos)
        if porog is None:
            return 0
        if await self._uzhe_pisali(user.id, expires_on, porog):
            return 0

        # Отметку ставим до отправки: письмо, ушедшее дважды, хуже
        # неотправленного, а сбой почты виден в журнале.
        if not await self._otmetit(user.id, expires_on, porog):
            return 0

        letter = subscription_expiring_letter(
            days_left=ostalos,
            expires_at=expires_on,
            buy_url=self._buy_url(),
            support_url=str(self._settings.telegram_support_url),
            support_email=self._settings.support_email,
        )
        try:
            await Mailer(self._settings).send(
                to_email=user.email, letter=letter
            )
        except (MailNotConfiguredError, OSError, ValueError):
            logger.exception("Письмо о сроке не ушло: %s", user.email)
            return 0

        logger.info(
            "Напоминание о сроке отправлено: %s, осталось %s дн.",
            user.email,
            ostalos,
        )
        return 1

    def _porog(self, ostalos: int) -> int | None:
        """Самый близкий порог, до которого человек уже дошёл.

        Пороги перебираем от меньшего к большему, чтобы при пропущенном
        обходе человек получил письмо про ближний срок, а не про
        давно прошедший дальний.
        """
        for porog in sorted(self._settings.reminder_days_list):
            if ostalos <= porog:
                return porog
        return None

    async def _uzhe_pisali(
        self, user_id, expires_on: date, porog: int
    ) -> bool:
        found = await self._session.scalar(
            select(SubscriptionReminder.id).where(
                SubscriptionReminder.user_id == user_id,
                SubscriptionReminder.expires_on == expires_on,
                SubscriptionReminder.days_before <= porog,
            )
        )
        return found is not None

    async def _otmetit(self, user_id, expires_on: date, porog: int) -> bool:
        """Занять порог. False означает, что его уже занял кто-то другой."""
        self._session.add(
            SubscriptionReminder(
                user_id=user_id, expires_on=expires_on, days_before=porog
            )
        )
        try:
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            return False
        return True

    def _buy_url(self) -> str:
        origin = (
            self._settings.allowed_origins[0]
            if self._settings.allowed_origins
            else ""
        ).rstrip("/")
        return f"{origin}/buy"
