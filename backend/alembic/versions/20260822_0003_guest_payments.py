"""Платёж гостя: без аккаунта, но с почтой.

Гость покупает по почте, и аккаунта на сайте у него может не быть. Заводить
его молча нельзя: почта в users уникальна, а восстановления пароля на сайте
нет — человек навсегда потерял бы возможность зарегистрироваться сам.

Revision ID: 20260822_0003
Revises: 20260821_0002
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260822_0003"
down_revision: str | None = "20260821_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("payments", "user_id", nullable=True)
    op.add_column(
        "payments", sa.Column("contact_email", sa.String(length=320))
    )
    op.add_column("payments", sa.Column("tariff_id", sa.Integer()))
    op.add_column("payments", sa.Column("period_days", sa.Integer()))
    # Ссылку на подписку панель отдаёт в момент выдачи. Храним её, иначе
    # страница результата не сможет показать человеку, что он купил.
    op.add_column(
        "payments", sa.Column("subscription_url", sa.String(length=500))
    )
    op.create_index(
        "ix_payments_contact_email", "payments", ["contact_email"]
    )


def downgrade() -> None:
    op.drop_index("ix_payments_contact_email", table_name="payments")
    op.drop_column("payments", "subscription_url")
    op.drop_column("payments", "period_days")
    op.drop_column("payments", "tariff_id")
    op.drop_column("payments", "contact_email")
    # Платежи без пользователя обратно не помещаются — их удаляем.
    op.execute("DELETE FROM payments WHERE user_id IS NULL")
    op.alter_column("payments", "user_id", nullable=False)
