from __future__ import annotations

from scripts.migrate_catalog_to_postgres import (
    CATALOG_TABLE_NAMES,
    catalog_tables,
)


def test_catalog_migration_scope_excludes_pii_and_operations() -> None:
    assert {table.name for table in catalog_tables()} == CATALOG_TABLE_NAMES
    assert not any(
        name.startswith(
            (
                "accounts_",
                "customer_",
                "orders_",
                "support_",
                "notification_",
                "admin_",
            )
        )
        for name in CATALOG_TABLE_NAMES
    )


def test_catalog_migration_tables_follow_foreign_key_order() -> None:
    names = [table.name for table in catalog_tables()]
    assert names.index("catalog_categories") < names.index("catalog_products")
    assert names.index("catalog_products") < names.index("catalog_product_variants")
    assert names.index("catalog_product_variants") < names.index(
        "sourcing_seller_offers"
    )
    assert names.index("sourcing_countries") < names.index("sourcing_sellers")
