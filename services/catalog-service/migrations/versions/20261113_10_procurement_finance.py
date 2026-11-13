"""Add purchase orders, goods receipts and supplier payments.

Revision ID: 20261113_10
Revises: 20261112_09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261113_10"
down_revision = "20261112_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("procurement_purchase_orders"):
        op.create_table(
            "procurement_purchase_orders",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("po_number", sa.String(length=30), unique=True),
            sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders_orders.id"), nullable=False),
            sa.Column("seller_id", sa.Integer(), sa.ForeignKey("sourcing_sellers.id"), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("fx_rate_to_bdt", sa.Numeric(18, 8), nullable=False),
            sa.Column("total_origin", sa.Numeric(14, 2), nullable=False),
            sa.Column("total_bdt", sa.Numeric(14, 2), nullable=False),
            sa.Column("expected_at", sa.DateTime(timezone=True)),
            sa.Column("note", sa.Text()),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_procurement_purchase_orders_order_id", "procurement_purchase_orders", ["order_id"])
        op.create_index("ix_procurement_purchase_orders_seller_id", "procurement_purchase_orders", ["seller_id"])
        op.create_index("ix_procurement_purchase_orders_status", "procurement_purchase_orders", ["status"])
    if not inspector.has_table("procurement_purchase_order_items"):
        op.create_table(
            "procurement_purchase_order_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "purchase_order_id", sa.Integer(), sa.ForeignKey("procurement_purchase_orders.id"), nullable=False
            ),
            sa.Column("variant_id", sa.Integer(), nullable=False),
            sa.Column("product_name", sa.String(length=200), nullable=False),
            sa.Column("variant_name", sa.String(length=200), nullable=False),
            sa.Column("qty", sa.Integer(), nullable=False),
            sa.Column("unit_cost_origin", sa.Numeric(12, 2), nullable=False),
        )
        op.create_index(
            "ix_procurement_purchase_order_items_purchase_order_id",
            "procurement_purchase_order_items",
            ["purchase_order_id"],
        )
    if not inspector.has_table("procurement_goods_receipts"):
        op.create_table(
            "procurement_goods_receipts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "purchase_order_id", sa.Integer(), sa.ForeignKey("procurement_purchase_orders.id"), nullable=False
            ),
            sa.Column("received_qty", sa.Integer(), nullable=False),
            sa.Column("accepted_qty", sa.Integer(), nullable=False),
            sa.Column("rejected_qty", sa.Integer(), nullable=False),
            sa.Column("qc_note", sa.Text()),
            sa.Column("received_by_user_id", sa.Integer(), nullable=False),
            sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index(
            "ix_procurement_goods_receipts_purchase_order_id", "procurement_goods_receipts", ["purchase_order_id"]
        )
    if not inspector.has_table("finance_supplier_payments"):
        op.create_table(
            "finance_supplier_payments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "purchase_order_id", sa.Integer(), sa.ForeignKey("procurement_purchase_orders.id"), nullable=False
            ),
            sa.Column("amount_origin", sa.Numeric(14, 2), nullable=False),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("fx_rate_to_bdt", sa.Numeric(18, 8), nullable=False),
            sa.Column("amount_bdt", sa.Numeric(14, 2), nullable=False),
            sa.Column("method", sa.String(length=40), nullable=False),
            sa.Column("reference", sa.String(length=120)),
            sa.Column("paid_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("reversed_at", sa.DateTime(timezone=True)),
            sa.Column("reversed_by_user_id", sa.Integer()),
            sa.Column("reversal_reason", sa.Text()),
        )
        op.create_index(
            "ix_finance_supplier_payments_purchase_order_id", "finance_supplier_payments", ["purchase_order_id"]
        )


def downgrade() -> None:
    op.drop_table("finance_supplier_payments")
    op.drop_table("procurement_goods_receipts")
    op.drop_table("procurement_purchase_order_items")
    op.drop_table("procurement_purchase_orders")
