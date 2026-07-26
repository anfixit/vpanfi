from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.user import User


class TicketStatus(StrEnum):
    OPEN = "open"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_SUPPORT = "waiting_for_support"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MessageAuthor(StrEnum):
    USER = "user"
    SUPPORT = "support"
    AI = "ai"
    SYSTEM = "system"


class SupportTicket(TimestampMixin, Base):
    __tablename__ = "support_tickets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, name="ticket_status"),
        nullable=False,
        default=TicketStatus.OPEN,
        index=True,
    )

    user: Mapped[User] = relationship()
    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SupportMessage.created_at",
    )


class SupportMessage(TimestampMixin, Base):
    __tablename__ = "support_messages"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    ticket_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author: Mapped[MessageAuthor] = mapped_column(
        Enum(MessageAuthor, name="message_author"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped[SupportTicket] = relationship(back_populates="messages")
