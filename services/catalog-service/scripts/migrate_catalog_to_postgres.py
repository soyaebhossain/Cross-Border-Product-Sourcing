from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, create_engine, func, insert, inspect, select, text
from sqlalchemy.engine import Engine, make_url


SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app import models  # noqa: E402, F401 - registers SQLAlchemy metadata
from app.db import Base  # noqa: E402


# This scope intentionally excludes accounts, quotes, orders, payments, support,
# notifications, invoices, and audit records. It is safe for moving the owned
# catalog into a newly provisioned production database without carrying legacy
# credentials or customer PII with it.
CATALOG_TABLE_NAMES = {
    "catalog_categories",
    "catalog_products",
    "catalog_product_variants",
    "pricing_currency_rates",
    "pricing_duty_rules",
    "pricing_service_fee_rules",
    "shipping_eta_rules",
    "shipping_rate_cards",
    "sourcing_countries",
    "sourcing_sellers",
    "sourcing_seller_offers",
}


def catalog_tables() -> list[Any]:
    tables = [
        table
        for table in Base.metadata.sorted_tables
        if table.name in CATALOG_TABLE_NAMES
    ]
    discovered = {table.name for table in tables}
    if discovered != CATALOG_TABLE_NAMES:
        missing = ", ".join(sorted(CATALOG_TABLE_NAMES - discovered))
        raise RuntimeError(f"Catalog migration metadata is incomplete: {missing}")
    return tables


def database_revision(connection: Connection) -> str | None:
    if not inspect(connection).has_table("alembic_version"):
        return None
    return connection.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))


def table_counts(connection: Connection, tables: Iterable[Any]) -> dict[str, int]:
    return {
        table.name: int(connection.scalar(select(func.count()).select_from(table)) or 0)
        for table in tables
    }


def _validated_engines(source_url: str, target_url: str) -> tuple[Engine, Engine]:
    source_parsed = make_url(source_url)
    target_parsed = make_url(target_url)
    if source_parsed.get_backend_name() != "sqlite":
        raise ValueError("CATALOG_MIGRATION_SOURCE_URL must reference SQLite")
    if target_parsed.get_backend_name() != "postgresql":
        raise ValueError("CATALOG_DATABASE_URL must reference PostgreSQL")
    if source_parsed.database in {None, "", ":memory:"}:
        raise ValueError("The SQLite source must be a file-backed database")
    source_path = Path(str(source_parsed.database)).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError("The SQLite source database does not exist")
    return create_engine(source_url), create_engine(target_url)


def _copy_rows(
    source: Connection,
    target: Connection,
    table: Any,
    *,
    chunk_size: int = 500,
) -> int:
    copied = 0
    batch: list[dict[str, Any]] = []
    for row in source.execute(select(table)).mappings():
        payload = dict(row)
        # Archived-by references point at accounts, which this deliberately
        # PII-free migration does not transfer.
        if "archived_by_user_id" in payload:
            payload["archived_by_user_id"] = None
        batch.append(payload)
        if len(batch) >= chunk_size:
            target.execute(insert(table), batch)
            copied += len(batch)
            batch = []
    if batch:
        target.execute(insert(table), batch)
        copied += len(batch)
    return copied


def _reset_postgres_sequence(connection: Connection, table_name: str) -> None:
    sequence = connection.scalar(
        text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
        {"table_name": table_name},
    )
    if not sequence:
        return
    maximum = int(
        connection.scalar(text(f'SELECT COALESCE(MAX(id), 0) FROM "{table_name}"'))
        or 0
    )
    connection.execute(
        text("SELECT setval(CAST(:sequence AS regclass), :value, :called)"),
        {
            "sequence": sequence,
            "value": maximum if maximum else 1,
            "called": bool(maximum),
        },
    )


def migrate_catalog(
    source_engine: Engine,
    target_engine: Engine,
    *,
    minimum_products: int,
) -> dict[str, int]:
    tables = catalog_tables()
    with source_engine.connect() as source:
        source_revision = database_revision(source)
        if not source_revision:
            raise RuntimeError("SQLite source is not managed by Alembic; migrate it first")
        source_counts = table_counts(source, tables)
        if source_counts["catalog_products"] < minimum_products:
            raise RuntimeError(
                "Source product count is below the required safety threshold "
                f"({source_counts['catalog_products']} < {minimum_products})"
            )

        with target_engine.begin() as target:
            target_revision = database_revision(target)
            if target_revision != source_revision:
                raise RuntimeError(
                    "Source and target Alembic revisions differ; upgrade both before copying"
                )
            populated = {
                name: count
                for name, count in table_counts(target, tables).items()
                if count
            }
            if populated:
                raise RuntimeError(
                    "PostgreSQL target is not empty; refusing to merge or overwrite catalog data"
                )

            copied = {
                table.name: _copy_rows(source, target, table)
                for table in tables
            }
            for table in tables:
                if "id" in table.c:
                    _reset_postgres_sequence(target, table.name)

            target_counts = table_counts(target, tables)
            mismatches = {
                name: (source_counts[name], target_counts[name])
                for name in source_counts
                if source_counts[name] != target_counts[name]
            }
            if mismatches:
                raise RuntimeError(f"Catalog row-count verification failed: {mismatches}")
            return copied


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy the PII-free catalog/configuration scope from migrated SQLite "
            "into an empty, Alembic-migrated PostgreSQL database."
        )
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required acknowledgement; without it no target connection is opened.",
    )
    parser.add_argument(
        "--minimum-products",
        type=int,
        default=350,
        help="Abort if the source has fewer products (default: 350).",
    )
    args = parser.parse_args()
    if not args.execute:
        parser.error("--execute is required")
    if args.minimum_products < 1:
        parser.error("--minimum-products must be positive")

    source_url = (os.getenv("CATALOG_MIGRATION_SOURCE_URL") or "").strip()
    target_url = (os.getenv("CATALOG_DATABASE_URL") or "").strip()
    if not source_url or not target_url:
        parser.error(
            "CATALOG_MIGRATION_SOURCE_URL and CATALOG_DATABASE_URL are required"
        )

    source_engine: Engine | None = None
    target_engine: Engine | None = None
    try:
        source_engine, target_engine = _validated_engines(source_url, target_url)
        copied = migrate_catalog(
            source_engine,
            target_engine,
            minimum_products=args.minimum_products,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Catalog migration failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if source_engine is not None:
            source_engine.dispose()
        if target_engine is not None:
            target_engine.dispose()

    print(
        "Catalog migration passed: "
        + ", ".join(f"{name}={count}" for name, count in copied.items())
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
