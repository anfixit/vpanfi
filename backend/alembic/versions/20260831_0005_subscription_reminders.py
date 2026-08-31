"""Отметки об отправленных напоминаниях о сроке.

Сайт продавал и замолкал навсегда: человек узнавал об окончании
подписки, когда переставал работать интернет. Бот такое умел, но
покупателя сайта в боте нет.

Ключ включает дату окончания, поэтому после продления круг
предупреждений начинается заново.

Revision ID: 20260831_0005
Revises: 20260822_0004
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260831_0005"
down_revision: str | None = "20260822_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscription_reminders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("days_before", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id",
            "expires_on",
            "days_before",
            name="uq_reminder_once_per_cycle",
        ),
    )
    op.create_index(
        "ix_subscription_reminders_user_id",
        "subscription_reminders",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_subscription_reminders_user_id",
        table_name="subscription_reminders",
    )
    op.drop_table("subscription_reminders")
