from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT
    / "apps"
    / "web-next"
    / "data"
    / "public-catalog.snapshot.json"
)

# The exporter deliberately reads only these public catalog/sourcing tables.
# Accounts, orders, quotes, payments, customer data, support and audit tables
# must never be added to this allowlist.
PUBLIC_SOURCE_TABLES = {
    "alembic_version",
    "catalog_categories",
    "catalog_products",
    "catalog_product_variants",
    "sourcing_countries",
    "sourcing_sellers",
    "sourcing_seller_offers",
}

BANNED_PUBLIC_KEYS = {
    "address",
    "archived_by_user_id",
    "audit",
    "email",
    "ip_address",
    "note",
    "order_id",
    "password",
    "payment",
    "phone",
    "refresh_token",
    "seller_id",
    "seller_name",
    "source_url",
    "trx_id",
    "user_id",
}
EMAIL_PATTERN = re.compile(r"\b[^@\s]+@[^@\s]+\.[^@\s]+\b")
LOCAL_IMAGE_PATTERN = re.compile(
    r"^products/(?:[A-Za-z0-9][A-Za-z0-9_-]*/)*"
    r"[A-Za-z0-9][A-Za-z0-9._-]*\.(?:avif|gif|jpe?g|png|webp)$",
    re.IGNORECASE,
)


def _decimal_string(value: Any, places: int) -> str:
    if value is None:
        value = 0
    return format(Decimal(str(value)), f".{places}f")


def _public_image_path(value: str | None) -> str | None:
    """Keep owned relative assets only; never make the fallback call third parties."""
    normalized = (value or "").strip().replace("\\", "/").lstrip("/")
    if not normalized or not LOCAL_IMAGE_PATTERN.fullmatch(normalized):
        return None
    return f"/media/{normalized}"


def _public_image_metadata(
    product_name: str,
    image_url: str | None,
) -> dict[str, str | None]:
    kind = (
        "fallback"
        if not image_url
        else "illustrative"
        if "/illustrative/" in image_url
        else "owned"
    )
    return {
        "url": image_url,
        "alt": product_name,
        "kind": kind,
        # The database currently has no verified credit/provenance column.
        "credit": None,
    }


def _required_tables(connection: sqlite3.Connection) -> None:
    discovered = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    missing = PUBLIC_SOURCE_TABLES - discovered
    if missing:
        raise RuntimeError(
            "Snapshot source is missing required tables: "
            + ", ".join(sorted(missing))
        )


def _market_summaries(
    connection: sqlite3.Connection,
    product_ids: set[int],
) -> dict[int, dict[str, Any]]:
    working: dict[int, dict[str, Any]] = {
        product_id: {"countries": set(), "seller_ids": set()}
        for product_id in product_ids
    }
    rows = connection.execute(
        """
        SELECT
            variant.product_id,
            offer.price_origin,
            offer.currency,
            offer.mode,
            country.code AS country_code,
            seller.rating,
            seller.id AS seller_id
        FROM catalog_product_variants AS variant
        JOIN catalog_products AS product ON product.id = variant.product_id
        JOIN catalog_categories AS category ON category.id = product.category_id
        JOIN sourcing_seller_offers AS offer ON offer.variant_id = variant.id
        JOIN sourcing_countries AS country ON country.id = offer.country_id
        JOIN sourcing_sellers AS seller ON seller.id = offer.seller_id
        WHERE
            variant.is_active = 1
            AND product.is_active = 1
            AND category.is_active = 1
            AND offer.is_active = 1
            AND seller.is_active = 1
        ORDER BY offer.id
        """
    )
    for row in rows:
        product_id = int(row["product_id"])
        if product_id not in working:
            continue
        summary = working[product_id]
        summary["countries"].add(str(row["country_code"]))
        summary["seller_ids"].add(int(row["seller_id"]))
        price = float(row["price_origin"])
        rating = float(row["rating"] or 0)
        delivery_days = 14 if str(row["mode"]) == "LOCAL" else 30
        if "min_price" not in summary or price < summary["min_price"]:
            summary["min_price"] = price
            summary["currency"] = str(row["currency"])
        summary["max_rating"] = max(float(summary.get("max_rating", 0)), rating)
        summary["min_delivery_days"] = min(
            int(summary.get("min_delivery_days", delivery_days)),
            delivery_days,
        )

    public: dict[int, dict[str, Any]] = {}
    for product_id, summary in working.items():
        rating = float(summary.get("max_rating", 0))
        delivery_days = int(summary.get("min_delivery_days", 99))
        price = float(summary.get("min_price", 0))
        risk_level = (
            "Low" if rating >= 4.5 else "Medium" if rating >= 3.5 else "High"
        )
        item: dict[str, Any] = {
            "countries": sorted(summary["countries"]),
            "supplier_count": len(summary["seller_ids"]),
            "max_rating": rating,
            "risk_level": risk_level,
            "recommended_score": round(
                rating * 18
                + max(0, 20 - delivery_days / 2)
                + (10 if risk_level == "Low" else 5)
                - min(price / 1000, 10),
                2,
            ),
        }
        for key in ("min_price", "currency", "min_delivery_days"):
            if key in summary:
                item[key] = summary[key]
        public[product_id] = item
    return public


def build_public_catalog_snapshot(
    connection: sqlite3.Connection,
    *,
    minimum_products: int = 350,
) -> dict[str, Any]:
    if minimum_products < 1:
        raise ValueError("minimum_products must be positive")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    _required_tables(connection)

    revision_row = connection.execute(
        "SELECT version_num FROM alembic_version LIMIT 1"
    ).fetchone()
    if revision_row is None:
        raise RuntimeError("Snapshot source is not managed by Alembic")

    categories = [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "slug": str(row["slug"]),
        }
        for row in connection.execute(
            """
            SELECT id, name, slug
            FROM catalog_categories
            WHERE is_active = 1
            ORDER BY lower(name), id
            """
        )
    ]
    category_by_id = {category["id"]: category for category in categories}

    variant_rows: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in connection.execute(
        """
        SELECT
            variant.id,
            variant.product_id,
            variant.sku,
            variant.variant_name,
            variant.weight_kg,
            variant.length_cm,
            variant.width_cm,
            variant.height_cm
        FROM catalog_product_variants AS variant
        JOIN catalog_products AS product ON product.id = variant.product_id
        JOIN catalog_categories AS category ON category.id = product.category_id
        WHERE
            variant.is_active = 1
            AND product.is_active = 1
            AND category.is_active = 1
        ORDER BY variant.id
        """
    ):
        variant_rows[int(row["product_id"])].append(
            {
                "id": int(row["id"]),
                "sku": row["sku"],
                "variant_name": row["variant_name"],
                "weight_kg": _decimal_string(row["weight_kg"], 3),
                "length_cm": _decimal_string(row["length_cm"], 2),
                "width_cm": _decimal_string(row["width_cm"], 2),
                "height_cm": _decimal_string(row["height_cm"], 2),
            }
        )

    product_source_rows = list(
        connection.execute(
            """
            SELECT
                product.id,
                product.name,
                product.slug,
                product.model,
                product.image,
                product.category_id
            FROM catalog_products AS product
            JOIN catalog_categories AS category ON category.id = product.category_id
            WHERE product.is_active = 1 AND category.is_active = 1
            ORDER BY product.id
            """
        )
    )
    if len(product_source_rows) < minimum_products:
        raise RuntimeError(
            "Source product count is below the required safety threshold "
            f"({len(product_source_rows)} < {minimum_products})"
        )
    product_ids = {int(row["id"]) for row in product_source_rows}
    markets = _market_summaries(connection, product_ids)

    products: list[dict[str, Any]] = []
    for row in product_source_rows:
        product_id = int(row["id"])
        variants = variant_rows[product_id]
        image_url = _public_image_path(row["image"])
        products.append(
            {
                "id": product_id,
                "name": str(row["name"]),
                "slug": str(row["slug"]),
                "model": row["model"],
                # Free-text descriptions are intentionally excluded because they
                # are not constrained against personal or customer information.
                "description": None,
                "image": image_url,
                "image_metadata": _public_image_metadata(
                    str(row["name"]),
                    image_url,
                ),
                "category": category_by_id[int(row["category_id"])],
                "variants": variants,
                "default_variant_id": variants[0]["id"] if variants else None,
                "market": markets[product_id],
            }
        )

    countries = [
        {
            "id": int(row["id"]),
            "code": str(row["code"]),
            "name": str(row["name"]),
        }
        for row in connection.execute(
            "SELECT id, code, name FROM sourcing_countries ORDER BY lower(name), id"
        )
    ]
    snapshot = {
        "schema_version": 2,
        "source_revision": str(revision_row["version_num"]),
        "counts": {
            "categories": len(categories),
            "countries": len(countries),
            "products": len(products),
            "variants": sum(len(product["variants"]) for product in products),
        },
        "categories": categories,
        "countries": countries,
        "products": products,
    }
    validate_public_catalog_snapshot(snapshot, minimum_products=minimum_products)
    return snapshot


def _walk_public_payload(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in BANNED_PUBLIC_KEYS:
                raise RuntimeError(f"Snapshot contains forbidden key: {key}")
            _walk_public_payload(child)
        return
    if isinstance(value, list):
        for child in value:
            _walk_public_payload(child)
        return
    if isinstance(value, str) and EMAIL_PATTERN.search(value):
        raise RuntimeError("Snapshot contains an email-like value")


def validate_public_catalog_snapshot(
    snapshot: dict[str, Any],
    *,
    minimum_products: int = 350,
) -> None:
    schema_version = snapshot.get("schema_version")
    if schema_version not in {1, 2}:
        raise RuntimeError("Snapshot schema version is unsupported")
    products = snapshot.get("products")
    categories = snapshot.get("categories")
    countries = snapshot.get("countries")
    if not isinstance(products, list) or len(products) < minimum_products:
        raise RuntimeError("Snapshot does not contain the minimum product count")
    if not isinstance(categories, list) or not categories:
        raise RuntimeError("Snapshot does not contain categories")
    if not isinstance(countries, list) or not countries:
        raise RuntimeError("Snapshot does not contain countries")

    product_ids = [product["id"] for product in products]
    product_slugs = [str(product["slug"]).casefold() for product in products]
    category_slugs = [
        str(category["slug"]).casefold() for category in categories
    ]
    variant_ids = [
        variant["id"]
        for product in products
        for variant in product.get("variants", [])
    ]
    if len(product_ids) != len(set(product_ids)):
        raise RuntimeError("Snapshot product IDs are not unique")
    if len(product_slugs) != len(set(product_slugs)):
        raise RuntimeError("Snapshot product slugs are not case-insensitively unique")
    if len(category_slugs) != len(set(category_slugs)):
        raise RuntimeError("Snapshot category slugs are not case-insensitively unique")
    if len(variant_ids) != len(set(variant_ids)):
        raise RuntimeError("Snapshot variant IDs are not unique")
    if any(product.get("description") is not None for product in products):
        raise RuntimeError("Snapshot free-text descriptions must be omitted")
    if any(
        product.get("image")
        and not str(product["image"]).startswith("/media/products/")
        for product in products
    ):
        raise RuntimeError("Snapshot image paths must reference owned local media")
    if schema_version >= 2:
        for product in products:
            metadata = product.get("image_metadata")
            if (
                not isinstance(metadata, dict)
                or metadata.get("url") != product.get("image")
                or metadata.get("alt") != product.get("name")
                or metadata.get("kind") not in {"owned", "illustrative", "fallback"}
                or metadata.get("credit") is not None
            ):
                raise RuntimeError("Snapshot image metadata is missing or inconsistent")
            expected_kind = (
                "fallback"
                if not product.get("image")
                else "illustrative"
                if "/illustrative/" in str(product["image"])
                else "owned"
            )
            if metadata["kind"] != expected_kind:
                raise RuntimeError("Snapshot image metadata kind is inconsistent")

    _walk_public_payload(snapshot)


def serialize_public_catalog_snapshot(snapshot: dict[str, Any]) -> bytes:
    return (
        json.dumps(
            snapshot,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def export_public_catalog_snapshot(
    source: Path,
    output: Path,
    *,
    minimum_products: int = 350,
) -> tuple[dict[str, Any], str]:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise ValueError("The SQLite snapshot source does not exist")
    connection = sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True)
    try:
        snapshot = build_public_catalog_snapshot(
            connection,
            minimum_products=minimum_products,
        )
    finally:
        connection.close()

    serialized = serialize_public_catalog_snapshot(snapshot)
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(serialized)
    return snapshot, hashlib.sha256(serialized).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export a deterministic, read-only, PII-free public catalog snapshot "
            "for the Next.js storefront."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=os.getenv("CATALOG_SNAPSHOT_SOURCE_PATH"),
        help="Migrated SQLite source path (or CATALOG_SNAPSHOT_SOURCE_PATH).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Snapshot output path (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "--minimum-products",
        type=int,
        default=350,
        help="Abort if the public source has fewer products (default: 350).",
    )
    args = parser.parse_args()
    if args.source is None:
        parser.error("--source or CATALOG_SNAPSHOT_SOURCE_PATH is required")
    try:
        snapshot, digest = export_public_catalog_snapshot(
            args.source,
            args.output,
            minimum_products=args.minimum_products,
        )
    except (OSError, RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"Public catalog snapshot failed: {exc}")
        return 1

    counts = snapshot["counts"]
    print(
        "Public catalog snapshot passed: "
        f"categories={counts['categories']}, "
        f"products={counts['products']}, "
        f"variants={counts['variants']}, "
        f"countries={counts['countries']}, "
        f"sha256={digest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
