"""Create the baseline schema and add operations-integrity fields safely.

Revision ID: 20260729_01
Revises:
"""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "20260729_01"
down_revision = None
branch_labels = None
depends_on = None


class _ConnectionBoundEngine:
    """Expose one Alembic connection through the tiny Engine API SQLite needs."""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.dialect = connection.dialect

    def begin(self) -> Any:
        return nullcontext(self.connection)


def _create_missing_tables(bind: Connection) -> None:
    # This first revision is also the baseline for previously unmanaged
    # databases. checkfirst=True creates only absent tables and never rebuilds
    # or replaces a table that already contains application data.
    from app.db import Base
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=bind, checkfirst=True)


def _table_exists(bind: Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _column_map(bind: Connection, table_name: str) -> dict[str, dict[str, Any]]:
    if not _table_exists(bind, table_name):
        return {}
    return {
        column["name"]: column
        for column in sa.inspect(bind).get_columns(table_name)
    }


def _ensure_column(bind: Connection, table_name: str, column: sa.Column[Any]) -> None:
    if column.name not in _column_map(bind, table_name):
        op.add_column(table_name, column)


def _ensure_index(
    bind: Connection,
    name: str,
    table_name: str,
    columns: tuple[str, ...],
) -> None:
    if not _table_exists(bind, table_name):
        return
    for index in sa.inspect(bind).get_indexes(table_name):
        indexed_columns = tuple(index.get("column_names") or ())
        if index.get("name") == name or indexed_columns == columns:
            return
    op.create_index(name, table_name, list(columns))


def _ensure_foreign_key(
    bind: Connection,
    name: str,
    table_name: str,
    local_columns: tuple[str, ...],
    referred_table: str,
    remote_columns: tuple[str, ...],
) -> None:
    for foreign_key in sa.inspect(bind).get_foreign_keys(table_name):
        if (
            tuple(foreign_key.get("constrained_columns") or ()) == local_columns
            and foreign_key.get("referred_table") == referred_table
            and tuple(foreign_key.get("referred_columns") or ()) == remote_columns
        ):
            return
    op.create_foreign_key(
        name,
        table_name,
        referred_table,
        list(local_columns),
        list(remote_columns),
        ondelete="SET NULL",
    )


def _has_unique_key(
    bind: Connection,
    table_name: str,
    columns: tuple[str, ...],
) -> bool:
    inspector = sa.inspect(bind)
    for constraint in inspector.get_unique_constraints(table_name):
        if tuple(constraint.get("column_names") or ()) == columns:
            return True
    for index in inspector.get_indexes(table_name):
        if index.get("unique") and tuple(index.get("column_names") or ()) == columns:
            return True
    return False


def _ensure_unique_constraint(
    bind: Connection,
    name: str,
    table_name: str,
    columns: tuple[str, ...],
    duplicate_query: str,
) -> None:
    if _has_unique_key(bind, table_name, columns):
        return
    # Preserve a legacy database even if it contains duplicates. New writes
    # remain protected by the service layer, and an operator can resolve old
    # duplicates before adding the physical constraint in a later revision.
    if bind.scalar(sa.text(duplicate_query)) is not None:
        return
    op.create_unique_constraint(name, table_name, list(columns))


def _upgrade_postgresql_compatible(bind: Connection) -> None:
    _ensure_column(
        bind,
        "orders_saved_quotes",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="requested",
        ),
    )
    _ensure_column(
        bind,
        "orders_saved_quotes",
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    _ensure_column(
        bind,
        "orders_saved_quotes",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    _ensure_column(
        bind,
        "orders_orders",
        sa.Column("saved_quote_id", sa.Integer()),
    )
    _ensure_column(
        bind,
        "orders_orders",
        sa.Column("quote_snapshot", sa.JSON()),
    )
    _ensure_column(
        bind,
        "orders_orders",
        sa.Column("idempotency_key", sa.String(length=80)),
    )
    _ensure_column(
        bind,
        "orders_orders",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    _ensure_column(
        bind,
        "orders_manual_payments",
        sa.Column("trx_normalized", sa.String(length=80)),
    )
    _ensure_column(
        bind,
        "orders_manual_payments",
        sa.Column(
            "decision",
            sa.String(length=20),
            nullable=False,
            server_default="PENDING",
        ),
    )
    _ensure_column(
        bind,
        "orders_manual_payments",
        sa.Column("decision_reason", sa.Text()),
    )
    _ensure_column(
        bind,
        "orders_manual_payments",
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    _ensure_column(
        bind,
        "orders_manual_payments",
        sa.Column("decided_by_user_id", sa.Integer()),
    )

    op.execute(
        sa.text(
            """
            UPDATE orders_saved_quotes
            SET status = COALESCE(NULLIF(status, ''), 'requested'),
                updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE orders_orders
            SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE orders_manual_payments
            SET trx_normalized = COALESCE(
                    NULLIF(trx_normalized, ''),
                    lower(replace(replace(trim(trx_id), ' ', ''), '-', ''))
                ),
                decision = CASE
                    WHEN verified IS TRUE THEN 'APPROVED'
                    WHEN decision IS NULL OR decision = '' THEN 'PENDING'
                    ELSE decision
                END,
                decided_at = CASE
                    WHEN verified IS TRUE THEN COALESCE(decided_at, verified_at)
                    ELSE decided_at
                END
            """
        )
    )

    payment_columns = _column_map(bind, "orders_manual_payments")
    normalized_column = payment_columns.get("trx_normalized")
    if (
        normalized_column
        and normalized_column.get("nullable", True)
        and bind.scalar(
            sa.text(
                """
                SELECT 1
                FROM orders_manual_payments
                WHERE trx_normalized IS NULL
                LIMIT 1
                """
            )
        )
        is None
    ):
        op.alter_column(
            "orders_manual_payments",
            "trx_normalized",
            existing_type=sa.String(length=80),
            nullable=False,
        )

    _ensure_foreign_key(
        bind,
        "fk_orders_saved_quote",
        "orders_orders",
        ("saved_quote_id",),
        "orders_saved_quotes",
        ("id",),
    )
    _ensure_unique_constraint(
        bind,
        "uq_order_user_idempotency",
        "orders_orders",
        ("user_id", "idempotency_key"),
        """
        SELECT 1
        FROM orders_orders
        WHERE idempotency_key IS NOT NULL
        GROUP BY user_id, idempotency_key
        HAVING count(*) > 1
        LIMIT 1
        """,
    )
    _ensure_unique_constraint(
        bind,
        "uq_manual_payment_channel_transaction",
        "orders_manual_payments",
        ("channel", "trx_normalized"),
        """
        SELECT 1
        FROM orders_manual_payments
        WHERE trx_normalized IS NOT NULL AND trx_normalized <> ''
        GROUP BY channel, trx_normalized
        HAVING count(*) > 1
        LIMIT 1
        """,
    )

    for name, table_name, columns in (
        ("ix_saved_quotes_status", "orders_saved_quotes", ("status",)),
        ("ix_saved_quotes_expires_at", "orders_saved_quotes", ("expires_at",)),
        ("ix_orders_saved_quote_id", "orders_orders", ("saved_quote_id",)),
        ("ix_orders_created_at", "orders_orders", ("created_at",)),
        ("ix_orders_status", "orders_orders", ("status",)),
        ("ix_manual_payments_decision", "orders_manual_payments", ("decision",)),
        ("ix_manual_payments_created_at", "orders_manual_payments", ("created_at",)),
        ("ix_admin_audit_actor", "admin_audit_events", ("actor_user_id",)),
        ("ix_admin_audit_action", "admin_audit_events", ("action",)),
        (
            "ix_admin_audit_entity",
            "admin_audit_events",
            ("entity_type", "entity_id"),
        ),
        ("ix_admin_audit_created_at", "admin_audit_events", ("created_at",)),
    ):
        _ensure_index(bind, name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    _create_missing_tables(bind)

    if bind.dialect.name == "sqlite":
        # Use Alembic's active connection. Opening another SQLite connection
        # while this transaction holds DDL locks can produce "database locked".
        from app.schema_upgrade import upgrade_sqlite_schema

        upgrade_sqlite_schema(_ConnectionBoundEngine(bind))  # type: ignore[arg-type]
        return

    _upgrade_postgresql_compatible(bind)


def downgrade() -> None:
    # This baseline intentionally has no destructive downgrade. Dropping the
    # audit table or operations columns would discard production data.
    pass
