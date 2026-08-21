"""Адресовать пользователя панели числовым id вместо UUID.

Remnawave 3.0.0 отказалась от uuid пользователя: в ответах его больше
нет, а на запрос по нему панель отвечает 400. Сохранённые в кабинете
uuid после этого не значат ничего — восстановить связку можно только по
имени пользователя, которое кабинет хранит рядом.

Revision ID: 20260821_0002
Revises: 20260726_0001
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260821_0002"
down_revision: str | None = "20260726_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("remnawave_user_id", sa.BigInteger()))
    op.create_unique_constraint(
        "uq_users_remnawave_user_id", "users", ["remnawave_user_id"]
    )
    op.create_index(
        "ix_users_remnawave_user_id", "users", ["remnawave_user_id"]
    )

    op.drop_index("ix_users_remnawave_user_uuid", table_name="users")
    op.drop_constraint(
        "uq_users_remnawave_user_uuid", "users", type_="unique"
    )
    op.drop_column("users", "remnawave_user_uuid")


def downgrade() -> None:
    # Обратно ставим колонку пустой: uuid, которые в ней лежали, панель
    # уже забыла, и возвращать их неоткуда.
    op.add_column(
        "users",
        sa.Column("remnawave_user_uuid", postgresql.UUID(as_uuid=True)),
    )
    op.create_unique_constraint(
        "uq_users_remnawave_user_uuid", "users", ["remnawave_user_uuid"]
    )
    op.create_index(
        "ix_users_remnawave_user_uuid", "users", ["remnawave_user_uuid"]
    )

    op.drop_index("ix_users_remnawave_user_id", table_name="users")
    op.drop_constraint("uq_users_remnawave_user_id", "users", type_="unique")
    op.drop_column("users", "remnawave_user_id")
