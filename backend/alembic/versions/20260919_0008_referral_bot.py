"""Рефералка: друг может прийти не только на сайт, но и в бота продаж.

У награды за друга из бота продаж нет своего платежа сайта, поэтому
``payment_id`` становится необязательным. Источник награды (``source``)
отличает старые записи с сайта от новых из бота. Привязка к боту идёт
через ``bot_transaction_id`` (уникален, как и ``payment_id`` у наград
с сайта) и ``friend_telegram_id`` (нужен для продления другу через
Bedolaga, минуя панель).

Revision ID: 20260919_0008
Revises: 20260919_0007
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260919_0008"
down_revision: str | None = "20260919_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "referral_rewards",
        sa.Column(
            "source",
            sa.String(8),
            nullable=False,
            server_default="site",
        ),
    )
    op.add_column(
        "referral_rewards",
        sa.Column("friend_telegram_id", sa.BigInteger()),
    )
    op.add_column(
        "referral_rewards",
        sa.Column("bot_transaction_id", sa.Integer()),
    )
    op.create_unique_constraint(
        "uq_referral_rewards_bot_transaction_id",
        "referral_rewards",
        ["bot_transaction_id"],
    )
    op.alter_column(
        "referral_rewards", "payment_id", nullable=True
    )


def downgrade() -> None:
    # У наград с source == "bot" своего платежа сайта нет вовсе
    # (payment_id у них и так NULL), поэтому обратная миграция сперва
    # удаляет их: иначе NOT NULL на payment_id не встанет назад.
    # Выданные другу и пригласившему дни это не трогает, теряется
    # только запись о них в этой таблице.
    op.execute("DELETE FROM referral_rewards WHERE source = 'bot'")
    op.alter_column(
        "referral_rewards", "payment_id", nullable=False
    )
    op.drop_constraint(
        "uq_referral_rewards_bot_transaction_id",
        "referral_rewards",
        type_="unique",
    )
    op.drop_column("referral_rewards", "bot_transaction_id")
    op.drop_column("referral_rewards", "friend_telegram_id")
    op.drop_column("referral_rewards", "source")
