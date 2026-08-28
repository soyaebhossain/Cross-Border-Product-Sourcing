"""Require explicit duty configuration and repair known legacy catalog rows.

Revision ID: 20260827_07
Revises: 20260826_06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "20260827_07"
down_revision = "20260826_06"
branch_labels = None
depends_on = None


def _table_exists(bind: Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _seed_explicit_country_duty_rules(bind: Connection) -> None:
    if not (
        _table_exists(bind, "sourcing_countries")
        and _table_exists(bind, "pricing_duty_rules")
    ):
        return
    bind.execute(
        sa.text(
            """
            INSERT INTO pricing_duty_rules (
                country_id, category_id, percent, fixed_bdt, is_active, updated_at
            )
            SELECT country.id, NULL, 5.00, 0.00, TRUE, CURRENT_TIMESTAMP
            FROM sourcing_countries AS country
            WHERE NOT EXISTS (
                SELECT 1
                FROM pricing_duty_rules AS rule
                WHERE rule.country_id = country.id
                  AND rule.category_id IS NULL
                  AND rule.is_active IS TRUE
            )
            """
        )
    )


def _repair_known_legacy_catalog_rows(bind: Connection) -> None:
    if not (
        _table_exists(bind, "catalog_products")
        and _table_exists(bind, "catalog_product_variants")
    ):
        return

    corrections = (
        {
            "old_name": "Buttom Phones",
            "old_slug": "Phone",
            "name": "Nokia 1100 Feature Phone",
            "slug": "nokia-1100-feature-phone",
            "model": "NOKIA-1100",
            "sku": "NOKIA-1100-STD",
            "variant_name": "Standard",
            "weight_kg": "0.120",
            "length_cm": "10.60",
            "width_cm": "4.60",
            "height_cm": "2.00",
        },
        {
            "old_name": "Light",
            "old_slug": "Touch_1122",
            "name": "Rechargeable LED Work Light",
            "slug": "rechargeable-led-work-light",
            "model": "LED-WORK-1122",
            "sku": "LED-WORK-1122-STD",
            "variant_name": "Standard",
            "weight_kg": "0.200",
            "length_cm": "10.00",
            "width_cm": "6.00",
            "height_cm": "2.00",
        },
        {
            "old_name": "Fan",
            "old_slug": "electronics",
            "name": "Nova Air Pedestal Fan",
            "slug": "nova-air-pedestal-fan",
            "model": "NOVA-AIR-55W",
            "sku": "NOVA-AIR-55W-STD",
            "variant_name": "55W Standard",
            "weight_kg": "3.500",
            "length_cm": "40.00",
            "width_cm": "40.00",
            "height_cm": "130.00",
        },
    )
    for item in corrections:
        row = bind.execute(
            sa.text(
                """
                SELECT id
                FROM catalog_products
                WHERE name = :old_name AND slug = :old_slug
                LIMIT 1
                """
            ),
            item,
        ).first()
        if row is None:
            continue
        product_id = int(row[0])
        slug_owner = bind.execute(
            sa.text(
                "SELECT id FROM catalog_products WHERE lower(slug) = lower(:slug) AND id <> :id LIMIT 1"
            ),
            {"slug": item["slug"], "id": product_id},
        ).first()
        sku_owner = bind.execute(
            sa.text(
                "SELECT id FROM catalog_product_variants WHERE upper(sku) = upper(:sku) AND product_id <> :id LIMIT 1"
            ),
            {"sku": item["sku"], "id": product_id},
        ).first()
        if slug_owner is not None or sku_owner is not None:
            continue
        bind.execute(
            sa.text(
                """
                UPDATE catalog_products
                SET name = :name, slug = :slug, model = :model,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """
            ),
            {**item, "id": product_id},
        )
        bind.execute(
            sa.text(
                """
                UPDATE catalog_product_variants
                SET sku = :sku, variant_name = :variant_name,
                    weight_kg = :weight_kg, length_cm = :length_cm,
                    width_cm = :width_cm, height_cm = :height_cm,
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_id = :id
                """
            ),
            {**item, "id": product_id},
        )


def upgrade() -> None:
    bind = op.get_bind()
    _seed_explicit_country_duty_rules(bind)
    _repair_known_legacy_catalog_rows(bind)


def downgrade() -> None:
    # These reference-data and spelling corrections are intentionally retained.
    pass
