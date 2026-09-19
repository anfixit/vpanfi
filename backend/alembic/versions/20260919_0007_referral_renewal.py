"""Рефералка: продление друга приносит пригласившему ещё дни.

У друга теперь может быть до двух наград: "first" за первую оплату
(как раньше) и одна-единственная "renewal" за первое продление после
неё. Старый индекс держал ровно одну запись на почту навсегда, с
новым видом наград это стало неверно, и на смену ему приходит индекс
по паре (почта, вид).

Revision ID: 20260919_0007
Revises: 20260919_0006
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260919_0007"
down_revision: str | None = "20260919_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "referral_rewards",
        sa.Column(
            "kind",
            sa.String(16),
            nullable=False,
            server_default="first",
        ),
    )
    op.drop_constraint(
        "uq_referral_rewards_friend_email",
        "referral_rewards",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_referral_rewards_friend_email_kind",
        "referral_rewards",
        ["friend_email", "kind"],
    )


def downgrade() -> None:
    # Может упасть по design: если у какого-то друга уже завелась
    # награда за продление, у него на этот момент две строки с одной
    # и той же почтой (first и renewal), и старый индекс "одна почта -
    # одна запись" по ним не встанет. Поэтому сперва убираем именно
    # renewal-записи, после этого на почту снова остаётся не больше
    # одной строки, и старый индекс встаёт как обычно. Если в проде к
    # моменту отката уже выданы дни по renewal-наградам, это осознанная
    # потеря записи об этом (не самих выданных дней, они уже у людей).
    op.execute("DELETE FROM referral_rewards WHERE kind = 'renewal'")
    op.drop_constraint(
        "uq_referral_rewards_friend_email_kind",
        "referral_rewards",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_referral_rewards_friend_email",
        "referral_rewards",
        ["friend_email"],
    )
    op.drop_column("referral_rewards", "kind")
