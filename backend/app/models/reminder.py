from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class SubscriptionReminder(TimestampMixin, Base):
    """Отметка о том, что человеку уже написали про окончание срока.

    Нужна ровно затем, чтобы не писать дважды. Проверка идёт по кругу
    несколько раз в сутки, и без отметки человек получал бы одно и то
    же письмо каждые несколько часов.

    Ключ включает дату окончания, а не только порог: после продления
    дата меняется, и предупреждения начинаются заново, как и должны.
    """

    __tablename__ = "subscription_reminders"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "expires_on",
            "days_before",
            name="uq_reminder_once_per_cycle",
        ),
    )

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
    # Дата окончания подписки, о которой предупреждали.
    expires_on: Mapped[date] = mapped_column(Date, nullable=False)
    # За сколько дней предупредили.
    days_before: Mapped[int] = mapped_column(Integer, nullable=False)
