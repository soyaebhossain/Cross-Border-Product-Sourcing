"""Add audited admin operations, finance adjustments, and fulfilment outcomes.

Revision ID: 20260730_03
Revises: 20260730_02
"""

from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "20260730_03"
down_revision = "20260730_02"
branch_labels = None
depends_on = None


def _table_exists(bind: Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: Connection, table_name: str) -> set[str]:
    if not _table_exists(bind, table_name):
        return set()
    return {item["name"] for item in sa.inspect(bind).get_columns(table_name)}


def _ensure_column(bind: Connection, table_name: str, column: sa.Column[Any]) -> None:
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


def _ensure_unique_if_clean(
    bind: Connection,
    name: str,
    table_name: str,
    columns: tuple[str, ...],
    duplicate_sql: str,
) -> None:
    if bind.scalar(sa.text(duplicate_sql)) is not None:
        # Preserve legacy rows. The service layer rejects future duplicates;
        # operators can reconcile historical duplicates before adding the
        # physical constraint.
        return
    _ensure_index(bind, name, table_name, columns, unique=True)


def _create_duty_rules(bind: Connection) -> None:
    if not _table_exists(bind, "pricing_duty_rules"):
        op.create_table(
            "pricing_duty_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("country_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer()),
            sa.Column("percent", sa.Numeric(6, 2), nullable=False, server_default="0"),
            sa.Column("fixed_bdt", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("effective_from", sa.DateTime(timezone=True)),
            sa.Column("effective_to", sa.DateTime(timezone=True)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("archived_at", sa.DateTime(timezone=True)),
            sa.Column("archived_by_user_id", sa.Integer()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.ForeignKeyConstraint(["country_id"], ["sourcing_countries.id"]),
            sa.ForeignKeyConstraint(["category_id"], ["catalog_categories.id"]),
        )
    _ensure_index(bind, "ix_duty_rules_is_active", "pricing_duty_rules", ("is_active",))


def _create_payment_adjustments(bind: Connection) -> None:
    if not _table_exists(bind, "orders_payment_adjustments"):
        op.create_table(
            "orders_payment_adjustments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("order_id", sa.Integer(), nullable=False),
            sa.Column("payment_id", sa.Integer()),
            sa.Column("adjustment_type", sa.String(length=30), nullable=False),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="POSTED",
            ),
            sa.Column("amount_bdt", sa.Numeric(12, 2), nullable=False),
            sa.Column("transaction_id", sa.String(length=80), nullable=False),
            sa.Column("reason", sa.Text(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("reversed_by_user_id", sa.Integer()),
            sa.Column("reversed_at", sa.DateTime(timezone=True)),
            sa.Column("reversal_reason", sa.Text()),
            sa.ForeignKeyConstraint(["order_id"], ["orders_orders.id"]),
            sa.ForeignKeyConstraint(["payment_id"], ["orders_manual_payments.id"]),
            sa.UniqueConstraint(
                "transaction_id", name="uq_payment_adjustment_transaction"
            ),
        )
    for name, columns in (
        ("ix_payment_adjustments_order_id", ("order_id",)),
        ("ix_payment_adjustments_payment_id", ("payment_id",)),
        ("ix_payment_adjustments_type", ("adjustment_type",)),
        ("ix_payment_adjustments_status", ("status",)),
        ("ix_payment_adjustments_created_at", ("created_at",)),
    ):
        _ensure_index(bind, name, "orders_payment_adjustments", columns)


def upgrade() -> None:
    bind = op.get_bind()
    common_tables = (
        "catalog_categories",
        "catalog_products",
        "catalog_product_variants",
        "sourcing_sellers",
        "sourcing_seller_offers",
        "pricing_currency_rates",
        "pricing_service_fee_rules",
        "shipping_rate_cards",
        "shipping_eta_rules",
    )
    for table_name in common_tables:
        for column in (
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("archived_at", sa.DateTime(timezone=True)),
            sa.Column("archived_by_user_id", sa.Integer()),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        ):
            _ensure_column(bind, table_name, column)

    for column in (
        sa.Column("actual_cost_bdt", sa.Numeric(12, 2)),
        sa.Column("promised_delivery_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column(
            "quality_defect_reported",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    ):
        _ensure_column(bind, "orders_orders", column)

    for column in (
        sa.Column("previous_status", sa.String(length=20)),
        sa.Column("actor_user_id", sa.Integer()),
        sa.Column("actor_role", sa.String(length=20)),
        sa.Column("request_id", sa.String(length=100)),
    ):
        _ensure_column(bind, "orders_status_history", column)

    _create_duty_rules(bind)
    _create_payment_adjustments(bind)

    for table_name in common_tables:
        if _table_exists(bind, table_name):
            op.execute(
                sa.text(
                    f"""
                    UPDATE {table_name}
                    SET is_active = COALESCE(is_active, TRUE),
                        updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
                    """
                )
            )

    for name, table_name, columns in (
        ("ix_categories_is_active", "catalog_categories", ("is_active",)),
        ("ix_products_is_active", "catalog_products", ("is_active",)),
        ("ix_variants_is_active", "catalog_product_variants", ("is_active",)),
        ("ix_sellers_is_active", "sourcing_sellers", ("is_active",)),
        ("ix_offers_is_active", "sourcing_seller_offers", ("is_active",)),
        ("ix_currency_rates_is_active", "pricing_currency_rates", ("is_active",)),
        ("ix_service_fee_rules_is_active", "pricing_service_fee_rules", ("is_active",)),
        ("ix_shipping_rates_is_active", "shipping_rate_cards", ("is_active",)),
        ("ix_eta_rules_is_active", "shipping_eta_rules", ("is_active",)),
        ("ix_orders_promised_delivery_at", "orders_orders", ("promised_delivery_at",)),
        ("ix_orders_delivered_at", "orders_orders", ("delivered_at",)),
        ("ix_order_history_request_id", "orders_status_history", ("request_id",)),
    ):
        _ensure_index(bind, name, table_name, columns)

    _ensure_unique_if_clean(
        bind,
        "uq_orders_saved_quote",
        "orders_orders",
        ("saved_quote_id",),
        """
        SELECT 1
        FROM orders_orders
        WHERE saved_quote_id IS NOT NULL
        GROUP BY saved_quote_id
        HAVING count(*) > 1
        LIMIT 1
        """,
    )


def downgrade() -> None:
    # Finance adjustments, audit attribution, and archive state are durable
    # business records. Automated rollback must not delete them.
    pass
