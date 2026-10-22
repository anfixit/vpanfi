"""Отметка о выданной подписке, отдельная от ссылки на неё.

До 22.10.2026 признаком выданной подписки была заполненная
``subscription_url``: вебхук ЮKassa приходит несколько раз, и повторная
выдача отсекалась тем, что ссылка уже записана. С появлением фонового
добора оплат (``app/services/payment_sweep.py``) этого признака стало
мало. Добор берёт платёж каждые пару минут, и платёж, по которому
панель ответила, но ссылки в ответе не оказалось, он продлевал бы
бесконечно: ссылки нет — значит, выдай ещё раз.

Поэтому выдача отмечается своим полем. Существующим оплаченным
платежам отметка ставится по ``updated_at``: иначе первый же обход
после деплоя решил бы, что подписку по ним ещё не выдавали, и выдал бы
её заново всем, кто когда-либо платил.

Revision ID: 20261022_0009
Revises: 20260919_0008
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261022_0009"
down_revision: str | None = "20260919_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        """
        UPDATE payments
        SET delivered_at = updated_at
        WHERE status = 'SUCCEEDED'
        """
    )


def downgrade() -> None:
    op.drop_column("payments", "delivered_at")
