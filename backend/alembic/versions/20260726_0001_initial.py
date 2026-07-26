"""Create initial VPaNfi schema.

Revision ID: 20260726_0001
Revises:
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260726_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

identity_provider = sa.Enum("TELEGRAM", "YANDEX", "VK", name="identity_provider")
payment_status = sa.Enum(
    "PENDING",
    "SUCCEEDED",
    "FAILED",
    "REFUNDED",
    "CANCELLED",
    name="payment_status",
)
payment_purpose = sa.Enum(
    "SUBSCRIPTION",
    "BALANCE_TOP_UP",
    "EXTRA_DEVICE",
    name="payment_purpose",
)
ticket_status = sa.Enum(
    "OPEN",
    "WAITING_FOR_USER",
    "WAITING_FOR_SUPPORT",
    "RESOLVED",
    "CLOSED",
    name="ticket_status",
)
message_author = sa.Enum("USER", "SUPPORT", "AI", "SYSTEM", name="message_author")


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    identity_provider.create(bind, checkfirst=True)
    payment_status.create(bind, checkfirst=True)
    payment_purpose.create(bind, checkfirst=True)
    ticket_status.create(bind, checkfirst=True)
    message_author.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("password_digest", sa.String(length=512)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remnawave_user_uuid", postgresql.UUID(as_uuid=True)),
        sa.Column("remnawave_username", sa.String(length=128)),
        *timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("remnawave_user_uuid", name="uq_users_remnawave_user_uuid"),
        sa.UniqueConstraint("remnawave_username", name="uq_users_remnawave_username"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_remnawave_user_uuid", "users", ["remnawave_user_uuid"])
    op.create_index("ix_users_remnawave_username", "users", ["remnawave_username"])

    op.create_table(
        "external_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", identity_provider, nullable=False),
        sa.Column("provider_user_id", sa.String(length=255), nullable=False),
        sa.Column("provider_email", sa.String(length=320)),
        sa.Column("provider_username", sa.String(length=255)),
        *timestamps(),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_external_identity"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_identity_provider"),
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"])

    op.create_table(
        "billing_accounts",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("balance_kopecks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_renew_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamps(),
    )

    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount_kopecks", sa.Integer(), nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("purpose", payment_purpose, nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="sbp"),
        sa.Column("provider_payment_id", sa.String(length=255)),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("period_months", sa.Integer()),
        sa.Column("extra_devices", sa.Integer()),
        *timestamps(),
        sa.UniqueConstraint("provider", "provider_payment_id", name="uq_payment_provider_id"),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])

    op.create_table(
        "refresh_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("user_agent", sa.String(length=500)),
        sa.Column("ip_address", sa.String(length=64)),
        *timestamps(),
        sa.UniqueConstraint("token_id", name="uq_refresh_sessions_token_id"),
    )
    op.create_index("ix_refresh_sessions_user_id", "refresh_sessions", ["user_id"])
    op.create_index("ix_refresh_sessions_token_id", "refresh_sessions", ["token_id"])

    op.create_table(
        "support_tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("status", ticket_status, nullable=False),
        *timestamps(),
    )
    op.create_index("ix_support_tickets_user_id", "support_tickets", ["user_id"])
    op.create_index("ix_support_tickets_status", "support_tickets", ["status"])

    op.create_table(
        "support_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ticket_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("support_tickets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("author", message_author, nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_support_messages_ticket_id", "support_messages", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_support_messages_ticket_id", table_name="support_messages")
    op.drop_table("support_messages")
    op.drop_index("ix_support_tickets_status", table_name="support_tickets")
    op.drop_index("ix_support_tickets_user_id", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_index("ix_refresh_sessions_token_id", table_name="refresh_sessions")
    op.drop_index("ix_refresh_sessions_user_id", table_name="refresh_sessions")
    op.drop_table("refresh_sessions")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_table("billing_accounts")
    op.drop_index("ix_external_identities_user_id", table_name="external_identities")
    op.drop_table("external_identities")
    op.drop_index("ix_users_remnawave_username", table_name="users")
    op.drop_index("ix_users_remnawave_user_uuid", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    bind = op.get_bind()
    message_author.drop(bind, checkfirst=True)
    ticket_status.drop(bind, checkfirst=True)
    payment_purpose.drop(bind, checkfirst=True)
    payment_status.drop(bind, checkfirst=True)
    identity_provider.drop(bind, checkfirst=True)
