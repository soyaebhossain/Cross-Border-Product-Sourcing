"""Add customer self-service, notification outbox, support, and payment retries.

Revision ID: 20260730_04
Revises: 20260730_03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "20260730_04"
down_revision = "20260730_03"
branch_labels = None
depends_on = None


def _table_exists(bind: Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: Connection, table_name: str) -> set[str]:
    if not _table_exists(bind, table_name):
        return set()
    return {item["name"] for item in sa.inspect(bind).get_columns(table_name)}


def _ensure_column(bind: Connection, table_name: str, column: sa.Column) -> None:
    if _table_exists(bind, table_name) and column.name not in _columns(bind, table_name):
        op.add_column(table_name, column)


def _ensure_index(
    bind: Connection,
    name: str,
    table_name: str,
    columns: tuple[str, ...],
    *,
    unique: bool = False,
) -> None:
    if not _table_exists(bind, table_name):
        return
    inspector = sa.inspect(bind)
    for index in inspector.get_indexes(table_name):
        if index.get("name") == name:
            return
        if tuple(index.get("column_names") or ()) == columns and bool(
            index.get("unique")
        ) == unique:
            return
    if unique:
        for constraint in inspector.get_unique_constraints(table_name):
            if tuple(constraint.get("column_names") or ()) == columns:
                return
    op.create_index(name, table_name, list(columns), unique=unique)


def _create_customer_profile_tables(bind: Connection) -> None:
    if not _table_exists(bind, "customer_profiles"):
        op.create_table(
            "customer_profiles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("full_name", sa.String(length=200)),
            sa.Column("company_name", sa.String(length=200)),
            sa.Column("company_registration_number", sa.String(length=120)),
            sa.Column("tax_identifier", sa.String(length=120)),
            sa.Column(
                "preferred_language",
                sa.String(length=10),
                nullable=False,
                server_default="en",
            ),
            sa.Column(
                "preferred_currency",
                sa.String(length=10),
                nullable=False,
                server_default="BDT",
            ),
            sa.Column(
                "timezone",
                sa.String(length=80),
                nullable=False,
                server_default="Asia/Dhaka",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_users.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("user_id", name="uq_customer_profile_user"),
        )
    _ensure_index(
        bind,
        "ix_customer_profiles_user_id",
        "customer_profiles",
        ("user_id",),
        unique=True,
    )

    if not _table_exists(bind, "customer_addresses"):
        op.create_table(
            "customer_addresses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=80), nullable=False),
            sa.Column("recipient_name", sa.String(length=200), nullable=False),
            sa.Column("company_name", sa.String(length=200)),
            sa.Column("line1", sa.String(length=250), nullable=False),
            sa.Column("line2", sa.String(length=250)),
            sa.Column("city", sa.String(length=120), nullable=False),
            sa.Column("region", sa.String(length=120)),
            sa.Column("postal_code", sa.String(length=40)),
            sa.Column("country_code", sa.String(length=2), nullable=False),
            sa.Column("phone", sa.String(length=40), nullable=False),
            sa.Column(
                "is_default_shipping",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "is_default_billing",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("archived_at", sa.DateTime(timezone=True)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_users.id"], ondelete="CASCADE"
            ),
        )
    _ensure_index(
        bind, "ix_customer_addresses_user_id", "customer_addresses", ("user_id",)
    )
    _ensure_index(
        bind,
        "ix_customer_addresses_archived_at",
        "customer_addresses",
        ("archived_at",),
    )

    if not _table_exists(bind, "customer_invoices"):
        op.create_table(
            "customer_invoices",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("invoice_number", sa.String(length=40), nullable=False),
            sa.Column(
                "currency",
                sa.String(length=10),
                nullable=False,
                server_default="BDT",
            ),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.Column(
                "issued_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["orders_orders.id"], ondelete="RESTRICT"
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_users.id"], ondelete="RESTRICT"
            ),
            sa.UniqueConstraint("order_id", name="uq_customer_invoice_order"),
            sa.UniqueConstraint(
                "invoice_number", name="uq_customer_invoice_number"
            ),
        )
    for name, columns, unique in (
        ("ix_customer_invoices_order_id", ("order_id",), True),
        ("ix_customer_invoices_user_id", ("user_id",), False),
        ("ix_customer_invoices_invoice_number", ("invoice_number",), True),
        ("ix_customer_invoices_issued_at", ("issued_at",), False),
    ):
        _ensure_index(
            bind,
            name,
            "customer_invoices",
            columns,
            unique=unique,
        )


def _create_notification_tables(bind: Connection) -> None:
    if not _table_exists(bind, "customer_notification_preferences"):
        op.create_table(
            "customer_notification_preferences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column(
                "order_email",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "order_sms",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "order_whatsapp",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "support_email",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "support_sms",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "support_whatsapp",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "marketing_email",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_users.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("user_id", name="uq_notification_preferences_user"),
        )
    _ensure_index(
        bind,
        "ix_notification_preferences_user_id",
        "customer_notification_preferences",
        ("user_id",),
        unique=True,
    )

    if not _table_exists(bind, "customer_notifications"):
        op.create_table(
            "customer_notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer()),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("data", sa.JSON(), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_users.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["orders_orders.id"], ondelete="SET NULL"
            ),
        )
    for name, columns in (
        ("ix_customer_notifications_user_id", ("user_id",)),
        ("ix_customer_notifications_order_id", ("order_id",)),
        ("ix_customer_notifications_category", ("category",)),
        ("ix_customer_notifications_read_at", ("read_at",)),
        ("ix_customer_notifications_created_at", ("created_at",)),
    ):
        _ensure_index(bind, name, "customer_notifications", columns)

    if not _table_exists(bind, "notification_outbox"):
        op.create_table(
            "notification_outbox",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("notification_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(length=20), nullable=False),
            sa.Column("destination", sa.String(length=320), nullable=False),
            sa.Column("template_key", sa.String(length=80), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="QUEUED",
            ),
            sa.Column("claim_token", sa.String(length=64)),
            sa.Column("claimed_at", sa.DateTime(timezone=True)),
            sa.Column(
                "attempts", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
            sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
            sa.Column("sent_at", sa.DateTime(timezone=True)),
            sa.Column("provider_message_id", sa.String(length=200)),
            sa.Column("error_code", sa.String(length=80)),
            sa.Column("error_detail", sa.String(length=500)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["notification_id"],
                ["customer_notifications.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_users.id"], ondelete="CASCADE"
            ),
            sa.UniqueConstraint("claim_token", name="uq_notification_outbox_claim"),
        )
    for name, columns, unique in (
        ("ix_notification_outbox_notification_id", ("notification_id",), False),
        ("ix_notification_outbox_user_id", ("user_id",), False),
        ("ix_notification_outbox_channel", ("channel",), False),
        ("ix_notification_outbox_status", ("status",), False),
        ("ix_notification_outbox_claim_token", ("claim_token",), True),
        ("ix_notification_outbox_claimed_at", ("claimed_at",), False),
        ("ix_notification_outbox_next_attempt_at", ("next_attempt_at",), False),
        ("ix_notification_outbox_created_at", ("created_at",), False),
    ):
        _ensure_index(bind, name, "notification_outbox", columns, unique=unique)


def _create_support_tables(bind: Connection) -> None:
    if not _table_exists(bind, "support_tickets"):
        op.create_table(
            "support_tickets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer()),
            sa.Column("subject", sa.String(length=200), nullable=False),
            sa.Column("category", sa.String(length=40), nullable=False),
            sa.Column(
                "priority",
                sa.String(length=20),
                nullable=False,
                server_default="NORMAL",
            ),
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="OPEN",
            ),
            sa.Column("resolved_at", sa.DateTime(timezone=True)),
            sa.Column("closed_at", sa.DateTime(timezone=True)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_users.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["orders_orders.id"], ondelete="SET NULL"
            ),
            sa.UniqueConstraint("public_id", name="uq_support_ticket_public_id"),
        )
    for name, columns, unique in (
        ("ix_support_tickets_public_id", ("public_id",), True),
        ("ix_support_tickets_user_id", ("user_id",), False),
        ("ix_support_tickets_order_id", ("order_id",), False),
        ("ix_support_tickets_category", ("category",), False),
        ("ix_support_tickets_priority", ("priority",), False),
        ("ix_support_tickets_status", ("status",), False),
        ("ix_support_tickets_created_at", ("created_at",), False),
        ("ix_support_tickets_updated_at", ("updated_at",), False),
    ):
        _ensure_index(bind, name, "support_tickets", columns, unique=unique)

    if not _table_exists(bind, "support_messages"):
        op.create_table(
            "support_messages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ticket_id", sa.Integer(), nullable=False),
            sa.Column("author_user_id", sa.Integer(), nullable=False),
            sa.Column("author_role", sa.String(length=20), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("request_id", sa.String(length=100)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["ticket_id"], ["support_tickets.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["author_user_id"], ["accounts_users.id"], ondelete="RESTRICT"
            ),
        )
    for name, columns in (
        ("ix_support_messages_ticket_id", ("ticket_id",)),
        ("ix_support_messages_author_user_id", ("author_user_id",)),
        ("ix_support_messages_request_id", ("request_id",)),
        ("ix_support_messages_created_at", ("created_at",)),
    ):
        _ensure_index(bind, name, "support_messages", columns)

    if not _table_exists(bind, "customer_disputes"):
        op.create_table(
            "customer_disputes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("public_id", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("dispute_type", sa.String(length=40), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("requested_resolution", sa.Text(), nullable=False),
            sa.Column(
                "status",
                sa.String(length=30),
                nullable=False,
                server_default="OPEN",
            ),
            sa.Column("resolution_note", sa.Text()),
            sa.Column("decided_by_user_id", sa.Integer()),
            sa.Column("request_id", sa.String(length=100)),
            sa.Column("decided_at", sa.DateTime(timezone=True)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["user_id"], ["accounts_users.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["orders_orders.id"], ondelete="RESTRICT"
            ),
            sa.UniqueConstraint("public_id", name="uq_customer_dispute_public_id"),
        )
    for name, columns, unique in (
        ("ix_customer_disputes_public_id", ("public_id",), True),
        ("ix_customer_disputes_user_id", ("user_id",), False),
        ("ix_customer_disputes_order_id", ("order_id",), False),
        ("ix_customer_disputes_type", ("dispute_type",), False),
        ("ix_customer_disputes_status", ("status",), False),
        ("ix_customer_disputes_request_id", ("request_id",), False),
        ("ix_customer_disputes_created_at", ("created_at",), False),
        ("ix_customer_disputes_updated_at", ("updated_at",), False),
    ):
        _ensure_index(bind, name, "customer_disputes", columns, unique=unique)
    existing_indexes = {
        index.get("name")
        for index in sa.inspect(bind).get_indexes("customer_disputes")
    }
    if "uq_customer_active_dispute_order" not in existing_indexes:
        op.create_index(
            "uq_customer_active_dispute_order",
            "customer_disputes",
            ["user_id", "order_id"],
            unique=True,
            sqlite_where=sa.text("status IN ('OPEN', 'UNDER_REVIEW')"),
            postgresql_where=sa.text("status IN ('OPEN', 'UNDER_REVIEW')"),
        )


def _create_payment_attempt_tables(bind: Connection) -> None:
    if not _table_exists(bind, "orders_payment_proof_attempts"):
        op.create_table(
            "orders_payment_proof_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("payment_id", sa.Integer(), nullable=False),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=False),
            sa.Column("channel", sa.String(length=20), nullable=False),
            sa.Column("trx_id", sa.String(length=80), nullable=False),
            sa.Column("trx_normalized", sa.String(length=80), nullable=False),
            sa.Column("screenshot_url", sa.String(length=500)),
            sa.Column("submitted_by_user_id", sa.Integer(), nullable=False),
            sa.Column("request_id", sa.String(length=100)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["payment_id"], ["orders_manual_payments.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["order_id"], ["orders_orders.id"], ondelete="CASCADE"
            ),
            sa.ForeignKeyConstraint(
                ["submitted_by_user_id"],
                ["accounts_users.id"],
                ondelete="RESTRICT",
            ),
            sa.UniqueConstraint(
                "payment_id",
                "attempt_number",
                name="uq_payment_attempt_number",
            ),
            sa.UniqueConstraint(
                "channel",
                "trx_normalized",
                name="uq_payment_attempt_channel_transaction",
            ),
        )
    for name, columns, unique in (
        ("ix_payment_proof_attempts_payment_id", ("payment_id",), False),
        ("ix_payment_proof_attempts_order_id", ("order_id",), False),
        ("ix_payment_proof_attempts_request_id", ("request_id",), False),
        ("ix_payment_proof_attempts_created_at", ("created_at",), False),
        (
            "ix_payment_proof_attempts_channel_transaction",
            ("channel", "trx_normalized"),
            True,
        ),
    ):
        _ensure_index(
            bind,
            name,
            "orders_payment_proof_attempts",
            columns,
            unique=unique,
        )

    if not _table_exists(bind, "orders_payment_proof_decisions"):
        op.create_table(
            "orders_payment_proof_decisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attempt_id", sa.Integer(), nullable=False),
            sa.Column("decision", sa.String(length=20), nullable=False),
            sa.Column("reason", sa.Text()),
            sa.Column("actor_user_id", sa.Integer()),
            sa.Column("actor_role", sa.String(length=20), nullable=False),
            sa.Column("request_id", sa.String(length=100)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(
                ["attempt_id"],
                ["orders_payment_proof_attempts.id"],
                ondelete="CASCADE",
            ),
        )
    for name, columns in (
        ("ix_payment_proof_decisions_attempt_id", ("attempt_id",)),
        ("ix_payment_proof_decisions_decision", ("decision",)),
        ("ix_payment_proof_decisions_request_id", ("request_id",)),
        ("ix_payment_proof_decisions_created_at", ("created_at",)),
    ):
        _ensure_index(bind, name, "orders_payment_proof_decisions", columns)


def _backfill_payment_attempts(bind: Connection) -> None:
    required = {
        "orders_manual_payments",
        "orders_orders",
        "orders_payment_proof_attempts",
        "orders_payment_proof_decisions",
    }
    if not all(_table_exists(bind, table) for table in required):
        return
    bind.execute(
        sa.text(
            """
            INSERT INTO orders_payment_proof_attempts (
                payment_id, order_id, attempt_number, channel, trx_id,
                trx_normalized, screenshot_url, submitted_by_user_id, created_at
            )
            SELECT
                payment.id,
                payment.order_id,
                1,
                payment.channel,
                payment.trx_id,
                payment.trx_normalized,
                payment.screenshot_url,
                orders.user_id,
                COALESCE(payment.created_at, CURRENT_TIMESTAMP)
            FROM orders_manual_payments AS payment
            JOIN orders_orders AS orders ON orders.id = payment.order_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM orders_payment_proof_attempts AS attempt
                WHERE attempt.payment_id = payment.id
            )
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO orders_payment_proof_decisions (
                attempt_id, decision, reason, actor_user_id, actor_role,
                created_at
            )
            SELECT
                attempt.id,
                payment.decision,
                payment.decision_reason,
                payment.decided_by_user_id,
                CASE
                    WHEN payment.decided_by_user_id IS NULL THEN 'system'
                    ELSE 'operator'
                END,
                COALESCE(
                    payment.decided_at,
                    payment.verified_at,
                    payment.created_at,
                    CURRENT_TIMESTAMP
                )
            FROM orders_manual_payments AS payment
            JOIN orders_payment_proof_attempts AS attempt
              ON attempt.payment_id = payment.id
             AND attempt.attempt_number = 1
            WHERE payment.decision <> 'PENDING'
              AND NOT EXISTS (
                SELECT 1
                FROM orders_payment_proof_decisions AS decision
                WHERE decision.attempt_id = attempt.id
              )
            """
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    _create_customer_profile_tables(bind)
    _create_notification_tables(bind)
    _create_support_tables(bind)
    _create_payment_attempt_tables(bind)

    # Previous code accepted a fourth account role named "seller", although all
    # current RBAC and UI contracts define exactly customer/operator/admin.
    # Convert these stale accounts to unprivileged customers and revoke tokens.
    account_columns = _columns(bind, "accounts_users")
    if {"role", "is_staff", "is_superuser", "auth_version"}.issubset(account_columns):
        bind.execute(
            sa.text(
                """
                UPDATE accounts_users
                SET role = 'customer',
                    is_staff = FALSE,
                    is_superuser = FALSE,
                    auth_version = COALESCE(auth_version, 1) + 1
                WHERE role = 'seller'
                """
            )
        )

    _backfill_payment_attempts(bind)


def downgrade() -> None:
    # Customer records, invoices, support/dispute history, and payment attempt
    # ledgers are durable business/audit data and are not deleted automatically.
    pass
