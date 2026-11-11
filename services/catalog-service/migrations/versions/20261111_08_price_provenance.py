"""Record where each price input came from and when it was last verified.

Adds price_source, source_reference, verified_at and valid_until to supplier
offers, currency rates, shipping rate cards and duty rules. Existing rows are
marked as seeded with no verified_at, because nobody has confirmed them against
a source; quotes therefore report them as unverified instead of current.
Currency rates are widened to eight decimal places for live FX values.

Revision ID: 20261111_08
Revises: 20260827_07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261111_08"
down_revision = "20260827_07"
branch_labels = None
depends_on = None

PRICED_TABLES = (
    "sourcing_seller_offers",
    "pricing_currency_rates",
    "shipping_rate_cards",
    "pricing_duty_rules",
)


def _columns(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in PRICED_TABLES:
        if not inspector.has_table(table_name):
            continue
        existing = _columns(bind, table_name)
        if "price_source" not in existing:
            op.add_column(
                table_name,
                sa.Column("price_source", sa.String(length=30), nullable=False, server_default="seeded"),
            )
        if "source_reference" not in existing:
            op.add_column(table_name, sa.Column("source_reference", sa.String(length=500)))
        if "verified_at" not in existing:
            op.add_column(table_name, sa.Column("verified_at", sa.DateTime(timezone=True)))
        if "valid_until" not in existing:
            op.add_column(table_name, sa.Column("valid_until", sa.DateTime(timezone=True)))
    if inspector.has_table("pricing_currency_rates"):
        # Live rates such as BDT per VND need more than four decimal places.
        with op.batch_alter_table("pricing_currency_rates") as batch:
            batch.alter_column(
                "rate_to_bdt",
                type_=sa.Numeric(18, 8),
                existing_type=sa.Numeric(12, 4),
                existing_nullable=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in PRICED_TABLES:
        if not sa.inspect(bind).has_table(table_name):
            continue
        existing = _columns(bind, table_name)
        with op.batch_alter_table(table_name) as batch:
            for column in ("valid_until", "verified_at", "source_reference", "price_source"):
                if column in existing:
                    batch.drop_column(column)
