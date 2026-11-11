"""Store daily FX history and published country risk indicators.

Revision ID: 20261112_09
Revises: 20261111_08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261112_09"
down_revision = "20261111_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("pricing_fx_rate_history"):
        op.create_table(
            "pricing_fx_rate_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("currency", sa.String(length=10), nullable=False),
            sa.Column("rate_date", sa.Date(), nullable=False),
            sa.Column("rate_to_bdt", sa.Numeric(18, 8), nullable=False),
            sa.Column("source", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("currency", "rate_date", name="uq_fx_history_currency_date"),
        )
        op.create_index("ix_pricing_fx_rate_history_currency", "pricing_fx_rate_history", ["currency"])
        op.create_index("ix_pricing_fx_rate_history_rate_date", "pricing_fx_rate_history", ["rate_date"])
    if not inspector.has_table("sourcing_country_risk_indicators"):
        op.create_table(
            "sourcing_country_risk_indicators",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("country_id", sa.Integer(), sa.ForeignKey("sourcing_countries.id"), nullable=False),
            sa.Column("indicator_code", sa.String(length=40), nullable=False),
            sa.Column("indicator_name", sa.String(length=160), nullable=False),
            sa.Column("score", sa.Numeric(6, 2), nullable=False),
            sa.Column("data_year", sa.Integer(), nullable=False),
            sa.Column("source", sa.String(length=160), nullable=False),
            sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("country_id", "indicator_code", name="uq_country_risk_indicator"),
        )
        op.create_index(
            "ix_sourcing_country_risk_indicators_country_id", "sourcing_country_risk_indicators", ["country_id"]
        )


def downgrade() -> None:
    op.drop_table("sourcing_country_risk_indicators")
    op.drop_table("pricing_fx_rate_history")
