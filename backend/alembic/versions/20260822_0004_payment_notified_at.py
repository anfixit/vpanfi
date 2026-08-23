"""Отметка об отправленном письме со ссылкой.

Platega повторяет уведомление об оплате, пока не увидит 200. Без отметки
покупатель получал бы одно и то же письмо столько раз, сколько она его
прислала.

Revision ID: 20260822_0004
Revises: 20260822_0003
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260822_0004"
down_revision: str | None = "20260822_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("notified_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_column("payments", "notified_at")
