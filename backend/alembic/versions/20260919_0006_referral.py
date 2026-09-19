"""Рефералка: код у платежа и таблица наград.

Код приглашения это имя учётки пригласившего в панели, поэтому у
платежа он просто строка. Награда заводится после того, как другу
выдана подписка, и хранит всё нужное для выдачи дней обеим сторонам:
почта друга и id платежа защищены от повторной вставки, статус строкой,
чтобы новое значение не тянуло за собой миграцию типа.

Revision ID: 20260919_0006
Revises: 20260831_0005
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260919_0006"
down_revision: str | None = "20260831_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments", sa.Column("referral_code", sa.String(64))
    )
    op.create_index(
        "ix_payments_referral_code", "payments", ["referral_code"]
    )

    op.create_table(
        "referral_rewards",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("friend_email", sa.String(320), nullable=False),
        sa.Column("friend_panel_user_id", sa.BigInteger()),
        sa.Column("inviter_username", sa.String(64), nullable=False),
        sa.Column("inviter_panel_user_id", sa.BigInteger(), nullable=False),
        sa.Column("inviter_telegram_id", sa.BigInteger()),
        sa.Column("friend_days", sa.Integer(), nullable=False),
        sa.Column("inviter_days", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("friend_granted_at", sa.DateTime(timezone=True)),
        sa.Column("inviter_granted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("last_error", sa.String(500)),
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
            "payment_id", name="uq_referral_rewards_payment_id"
        ),
        sa.UniqueConstraint(
            "friend_email", name="uq_referral_rewards_friend_email"
        ),
    )
    op.create_index(
        "ix_referral_rewards_inviter_username",
        "referral_rewards",
        ["inviter_username"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_referral_rewards_inviter_username",
        table_name="referral_rewards",
    )
    op.drop_table("referral_rewards")

    op.drop_index("ix_payments_referral_code", table_name="payments")
    op.drop_column("payments", "referral_code")
