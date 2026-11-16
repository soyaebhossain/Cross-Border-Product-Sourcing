"""Load the public demo catalog into the configured database.

A fresh production database is empty after migrations. This command fills it
with the committed, PII-free catalog snapshot: categories, products, variants,
sourcing countries, demo suppliers and their offers, and reference shipping,
currency and duty rules. It creates no accounts, orders, quotes or payments.

It is safe to run on every deploy: rows that already exist are left as an
operator changed them, and only missing catalog rows are added.

The container runs it after migrations when CATALOG_SEED_PUBLIC_CATALOG=true.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import get_settings  # noqa: E402
from app.models import Category, Product, SellerOffer  # noqa: E402
from app.seed import seed_database  # noqa: E402

ENABLE_FLAG = "CATALOG_SEED_PUBLIC_CATALOG"


def seed_enabled() -> bool:
    return (os.getenv(ENABLE_FLAG) or "").strip().lower() in {"1", "true", "yes"}


def seed_public_catalog(database_url: str) -> dict[str, int]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            seed_database(session)
            return {
                "categories": session.scalar(select(func.count(Category.id))) or 0,
                "products": session.scalar(select(func.count(Product.id))) or 0,
                "offers": session.scalar(select(func.count(SellerOffer.id))) or 0,
            }
    finally:
        engine.dispose()


def main() -> int:
    if not seed_enabled():
        print(f"Catalog seed skipped: set {ENABLE_FLAG}=true to load the demo catalog.")
        return 0
    started = time.monotonic()
    try:
        counts = seed_public_catalog(get_settings().database_url)
    except Exception as exc:  # report and fail the deploy instead of serving an empty catalog
        print(f"Catalog seed failed: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return 1
    print(
        "Catalog seed finished in "
        f"{time.monotonic() - started:.1f}s: "
        f"categories={counts['categories']}, products={counts['products']}, offers={counts['offers']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
