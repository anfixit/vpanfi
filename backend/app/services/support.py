"""Обращения в поддержку из кабинета.

Порядок действий здесь важнее самих действий: обращение сохраняется в
базу и только потом уходит письмо. Наоборот было бы хуже — почтовый узел
падает регулярно, и человек, получивший «не удалось отправить», пишет
второй раз то же самое, хотя первое обращение уже можно было прочитать.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.support import (
    MessageAuthor,
    SupportMessage,
    SupportTicket,
    TicketStatus,
)
from app.models.user import User
from app.schemas.support import TicketCreatedResponse, TicketCreateRequest
from app.services.letters import support_alert_letter
from app.services.mail import Mailer

logger = logging.getLogger(__name__)

__all__ = ["SupportService"]

SUBJECT_LIMIT = 200

CATEGORY_LABELS = {
    "connection": "Не получается подключиться",
    "payment": "Вопрос по оплате",
    "devices": "Устройства",
    "other": "Другое",
}


def subject_from(message: str) -> str:
    """Короткая тема из первой строки обращения.

    Отдельного поля «тема» в форме нет намеренно: человек, которому
    нечем подключиться, не должен сочинять заголовок. Первая строка
    почти всегда и есть суть.
    """
    first = message.strip().splitlines()[0].strip()
    if not first:
        return "Обращение без темы"
    if len(first) <= SUBJECT_LIMIT:
        return first
    return first[: SUBJECT_LIMIT - 1].rstrip() + "…"


class SupportService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def create(
        self,
        user: User,
        request: TicketCreateRequest,
    ) -> TicketCreatedResponse:
        """Принять обращение и попытаться уведомить поддержку письмом."""
        message = request.message.strip()
        subject = subject_from(message)

        ticket = SupportTicket(
            user_id=user.id,
            subject=subject,
            category=request.category.value,
            status=TicketStatus.WAITING_FOR_SUPPORT,
        )
        ticket.messages.append(
            SupportMessage(author=MessageAuthor.USER, body=message)
        )
        self._session.add(ticket)
        await self._session.commit()

        await self._alert(ticket, user, message)

        return TicketCreatedResponse(
            id=ticket.id,
            subject=ticket.subject,
            status=ticket.status.value,
        )

    async def _alert(
        self,
        ticket: SupportTicket,
        user: User,
        message: str,
    ) -> None:
        """Письмо владельцу сервиса. Ошибка отправки обращение не теряет.

        Тикет уже в базе, поэтому упавшая почта означает всего лишь
        «прочитают позже», а не «обращение пропало».
        """
        if not self._settings.is_mail_configured:
            logger.warning(
                "Почта не настроена: обращение %s останется только в базе",
                ticket.id,
            )
            return

        letter = support_alert_letter(
            ticket_id=str(ticket.id),
            subject=ticket.subject,
            category=CATEGORY_LABELS.get(ticket.category, ticket.category),
            message=message,
            author_name=user.display_name,
            author_email=user.email,
        )

        try:
            await Mailer(self._settings).send(
                to_email=self._settings.support_email,
                letter=letter,
            )
        except Exception:
            logger.exception(
                "Обращение %s принято, но письмо не ушло", ticket.id
            )
