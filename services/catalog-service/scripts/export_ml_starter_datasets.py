from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean
from typing import Any, Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT_PATH = REPOSITORY_ROOT / "apps" / "web-next" / "data" / "public-catalog.snapshot.json"
GENERAL_GOODS_PATH = (
    REPOSITORY_ROOT
    / "services"
    / "catalog-service"
    / "app"
    / "seed_data"
    / "general_goods_v1.json"
)
DEFAULT_OUTPUT = REPOSITORY_ROOT / "datasets" / "ml-starter-v1"
DATASET_REVISION = "ml-starter-v1"
SIMULATION_VERSION = "synthetic-demand-v1"
SIMULATION_SEED = 20260730
USD_TO_BDT = 121.50


CATALOG_FIELDS = [
    "source_revision",
    "schema_version",
    "record_source",
    "feature_source",
    "label_source",
    "is_synthetic",
    "training_readiness",
    "group_split",
    "product_id",
    "product_slug",
    "product_name",
    "model",
    "category_id",
    "category_slug",
    "category_name",
    "variant_id",
    "variant_name",
    "sku",
    "missing_sku",
    "weight_kg",
    "length_cm",
    "width_cm",
    "height_cm",
    "volume_cm3",
    "volumetric_weight_kg",
    "min_price_usd",
    "origin_country_codes",
    "origin_count",
    "supplier_count",
    "max_supplier_rating",
    "image_kind",
    "has_image",
]

CATEGORY_FIELDS = [
    "example_id",
    "split",
    "product_id",
    "product_name",
    "model",
    "target_category_slug",
    "target_category_name",
    "feature_source",
    "label_source",
    "is_synthetic",
]

OFFER_FIELDS = [
    "example_id",
    "split",
    "category_slug",
    "weight_kg",
    "length_cm",
    "width_cm",
    "height_cm",
    "volume_cm3",
    "origin_country_code",
    "transport_mode",
    "stock",
    "moq",
    "supplier_rating",
    "target_offer_price_usd",
    "feature_source",
    "label_source",
    "is_synthetic",
]

PRODUCT_COUNTRY_FIELDS = [
    "source_revision",
    "product_id",
    "product_slug",
    "category_slug",
    "country_code",
    "feature_source",
    "is_synthetic",
]

TREND_FIELDS = [
    "row_id",
    "feature_period_start",
    "target_period_start",
    "split",
    "product_id",
    "product_slug",
    "category_slug",
    "min_price_usd",
    "weight_kg",
    "volume_cm3",
    "origin_count",
    "supplier_count",
    "max_supplier_rating",
    "product_views",
    "search_impressions",
    "quote_requests",
    "saved_quotes",
    "order_count",
    "ordered_qty",
    "gmv_bdt",
    "cancelled_orders",
    "delivered_orders",
    "on_time_delivery_count",
    "defect_count",
    "ordered_qty_lag_1",
    "ordered_qty_lag_2",
    "ordered_qty_lag_3",
    "ordered_qty_trailing_mean_3",
    "gmv_trailing_mean_3",
    "quote_to_order_rate",
    "target_next_month_order_qty",
    "target_next_month_gmv_bdt",
    "target_next_month_trend",
    "feature_source",
    "label_source",
    "is_synthetic",
    "simulation_version",
    "simulation_seed",
]

OUTCOME_FIELDS = [
    "event_id",
    "anonymous_quote_key",
    "anonymous_order_key",
    "quote_captured_at_utc",
    "outcome_observed_at_utc",
    "product_id",
    "variant_id",
    "category_slug",
    "country_code",
    "transport_mode",
    "delivery_type",
    "quantity",
    "unit_weight_kg",
    "unit_price_origin",
    "origin_currency",
    "fx_rate_to_bdt_at_quote",
    "stock_at_quote",
    "moq_at_quote",
    "supplier_rating_at_quote",
    "estimated_landed_cost_bdt",
    "promised_eta_min_days",
    "promised_eta_max_days",
    "converted_to_order",
    "payment_approved",
    "actual_landed_cost_bdt",
    "actual_delivery_days",
    "delayed_flag",
    "cancelled_flag",
    "refunded_flag",
    "quality_defect_flag",
    "dispute_flag",
    "feature_source",
    "label_source",
    "is_synthetic",
]

DICTIONARY_FIELDS = [
    "dataset",
    "field",
    "data_type",
    "role",
    "description",
    "source",
    "allowed_or_range",
    "leakage_note",
]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_number(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:16], 16)


def _decimal(value: Any, places: int = 4) -> str:
    return f"{float(value):.{places}f}"


def _month_sequence(start_year: int, start_month: int, end_year: int, end_month: int) -> list[date]:
    months: list[date] = []
    year, month = start_year, start_month
    while (year, month) <= (end_year, end_month):
        months.append(date(year, month, 1))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return months


def _group_splits(products: list[dict[str, Any]]) -> dict[str, str]:
    """Stratify by category and keep every product in exactly one split."""
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for product in products:
        by_category[str(product["category"]["slug"])].append(product)

    assignments: dict[str, str] = {}
    for category, members in sorted(by_category.items()):
        ordered = sorted(
            members,
            key=lambda item: (_stable_number(f"{DATASET_REVISION}:{category}:{item['slug']}"), item["slug"]),
        )
        count = len(ordered)
        train_count = max(1, int(count * 0.70))
        validation_count = max(1, int(count * 0.15)) if count >= 3 else 0
        if train_count + validation_count >= count:
            train_count = max(1, count - validation_count - 1)
        for index, product in enumerate(ordered):
            split = "train" if index < train_count else "validation" if index < train_count + validation_count else "test"
            assignments[str(product["slug"])] = split
    return assignments


def _flatten_catalog(
    snapshot: dict[str, Any],
    splits: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    catalog_rows: list[dict[str, Any]] = []
    category_rows: list[dict[str, Any]] = []
    product_country_rows: list[dict[str, Any]] = []
    source_revision = str(snapshot["source_revision"])
    schema_version = int(snapshot["schema_version"])

    for product in snapshot["products"]:
        variants = product.get("variants") or []
        if len(variants) != 1:
            raise RuntimeError(f"Expected one public variant for product {product['id']}")
        variant = variants[0]
        weight = float(variant["weight_kg"])
        length = float(variant["length_cm"])
        width = float(variant["width_cm"])
        height = float(variant["height_cm"])
        volume = length * width * height
        market = product["market"]
        countries = sorted(str(code) for code in market["countries"])
        image_kind = str(product["image_metadata"]["kind"])
        split = splits[str(product["slug"])]
        catalog_rows.append(
            {
                "source_revision": source_revision,
                "schema_version": schema_version,
                "record_source": "public_catalog_snapshot",
                "feature_source": "seed_derived",
                "label_source": "unavailable",
                "is_synthetic": 1,
                "training_readiness": "bootstrap_only",
                "group_split": split,
                "product_id": int(product["id"]),
                "product_slug": str(product["slug"]),
                "product_name": str(product["name"]),
                "model": str(product.get("model") or ""),
                "category_id": int(product["category"]["id"]),
                "category_slug": str(product["category"]["slug"]),
                "category_name": str(product["category"]["name"]),
                "variant_id": int(variant["id"]),
                "variant_name": str(variant.get("variant_name") or ""),
                "sku": str(variant.get("sku") or ""),
                "missing_sku": int(not variant.get("sku")),
                "weight_kg": _decimal(weight, 3),
                "length_cm": _decimal(length, 2),
                "width_cm": _decimal(width, 2),
                "height_cm": _decimal(height, 2),
                "volume_cm3": _decimal(volume, 3),
                "volumetric_weight_kg": _decimal(volume / 5000.0, 4),
                "min_price_usd": _decimal(market["min_price"], 2),
                "origin_country_codes": "|".join(countries),
                "origin_count": len(countries),
                "supplier_count": int(market["supplier_count"]),
                "max_supplier_rating": _decimal(market["max_rating"], 2),
                "image_kind": image_kind,
                "has_image": int(image_kind != "fallback"),
            }
        )
        category_rows.append(
            {
                "example_id": f"category-{product['id']}",
                "split": split,
                "product_id": int(product["id"]),
                "product_name": str(product["name"]),
                "model": str(product.get("model") or ""),
                "target_category_slug": str(product["category"]["slug"]),
                "target_category_name": str(product["category"]["name"]),
                "feature_source": "seed_derived",
                "label_source": "catalog_taxonomy",
                "is_synthetic": 1,
            }
        )
        for country_code in countries:
            product_country_rows.append(
                {
                    "source_revision": source_revision,
                    "product_id": int(product["id"]),
                    "product_slug": str(product["slug"]),
                    "category_slug": str(product["category"]["slug"]),
                    "country_code": country_code,
                    "feature_source": "seed_derived",
                    "is_synthetic": 1,
                }
            )
    return catalog_rows, category_rows, product_country_rows


def _offer_training_rows(manifest: dict[str, Any], splits: dict[str, str]) -> list[dict[str, Any]]:
    supplier_by_country = {item["country_code"]: item for item in manifest["supplier_profiles"]}
    rows: list[dict[str, Any]] = []
    for category in manifest["categories"]:
        for product in category["products"]:
            dimensions = [float(value) for value in product["dimensions_cm"]]
            volume = math.prod(dimensions)
            for strategy_index, strategy in enumerate(manifest["offer_strategy"], start=1):
                origin_position = int(strategy["origin_index"])
                country_code = str(product["origins"][origin_position])
                supplier = supplier_by_country[country_code]
                price = float(product["base_price_usd"]) * float(strategy["price_multiplier"])
                rows.append(
                    {
                        "example_id": f"offer-{product['sku']}-{strategy_index}",
                        "split": splits[str(product["slug"])],
                        "category_slug": str(category["slug"]),
                        "weight_kg": _decimal(product["weight_kg"], 3),
                        "length_cm": _decimal(dimensions[0], 2),
                        "width_cm": _decimal(dimensions[1], 2),
                        "height_cm": _decimal(dimensions[2], 2),
                        "volume_cm3": _decimal(volume, 3),
                        "origin_country_code": country_code,
                        "transport_mode": str(strategy["mode"]),
                        "stock": int(strategy["stock"]),
                        "moq": int(strategy["moq"]),
                        "supplier_rating": _decimal(supplier["rating"], 2),
                        "target_offer_price_usd": _decimal(price, 2),
                        "feature_source": "seed_derived",
                        "label_source": "pseudo_formula",
                        "is_synthetic": 1,
                    }
                )
    return rows


def _simulate_product_months(product: dict[str, Any], months: list[date]) -> list[dict[str, Any]]:
    slug = str(product["product_slug"])
    rng = random.Random(_stable_number(f"{SIMULATION_SEED}:{slug}"))
    price = max(float(product["min_price_usd"]), 0.01)
    weight = float(product["weight_kg"])
    category_factor = 0.78 + (_stable_number(str(product["category_slug"])) % 50) / 100.0
    base_orders = max(2.0, (92.0 / (1.0 + math.log1p(price))) * category_factor + rng.uniform(1.0, 8.0))
    monthly_slope = rng.uniform(-0.004, 0.018)
    average_units = 1.05 if price >= 500 else 1.35 if price >= 100 else rng.uniform(1.7, 3.8)
    cancellation_rate = rng.uniform(0.025, 0.11)
    on_time_rate = rng.uniform(0.78, 0.97)
    defect_rate = rng.uniform(0.005, 0.055)
    history: list[dict[str, Any]] = []

    for index, month in enumerate(months):
        seasonality = {1: 0.88, 4: 1.08, 5: 1.14, 11: 1.24, 12: 1.32}.get(month.month, 1.0)
        demand = base_orders * max(0.45, 1.0 + monthly_slope * index) * seasonality
        demand *= max(0.50, 1.0 + rng.gauss(0.0, 0.14))
        order_count = max(0, int(round(demand)))
        ordered_qty = max(order_count, int(round(order_count * average_units * max(0.65, 1 + rng.gauss(0, 0.08)))))
        save_conversion = rng.uniform(0.48, 0.72)
        quote_conversion = rng.uniform(0.54, 0.79)
        saved_quotes = max(order_count, int(round(order_count / save_conversion))) if order_count else 0
        quote_requests = max(saved_quotes, int(round(saved_quotes / quote_conversion))) if saved_quotes else 0
        product_views = max(quote_requests, int(round(quote_requests / rng.uniform(0.035, 0.105)))) if quote_requests else 0
        search_impressions = max(0, int(round(product_views * rng.uniform(0.42, 0.82))))
        cancelled_orders = min(order_count, int(round(order_count * cancellation_rate * rng.uniform(0.75, 1.25))))
        delivered_orders = max(0, order_count - cancelled_orders)
        on_time = min(delivered_orders, int(round(delivered_orders * on_time_rate * rng.uniform(0.93, 1.05))))
        defects = min(delivered_orders, int(round(delivered_orders * defect_rate * rng.uniform(0.70, 1.35))))
        realized_unit_price = price * USD_TO_BDT * max(0.90, 1.0 + rng.gauss(0.0, 0.025))
        gmv_bdt = ordered_qty * realized_unit_price
        history.append(
            {
                "month": month,
                "product_views": product_views,
                "search_impressions": search_impressions,
                "quote_requests": quote_requests,
                "saved_quotes": saved_quotes,
                "order_count": order_count,
                "ordered_qty": ordered_qty,
                "gmv_bdt": gmv_bdt,
                "cancelled_orders": cancelled_orders,
                "delivered_orders": delivered_orders,
                "on_time_delivery_count": on_time,
                "defect_count": defects,
            }
        )
    return history


def _trend_split(target_month: date) -> str:
    if target_month <= date(2025, 6, 1):
        return "train"
    if target_month == date(2025, 7, 1) or target_month == date(2026, 1, 1):
        return "purge"
    if target_month <= date(2025, 12, 1):
        return "validation"
    return "test"


def _trend_label(current_qty: int, next_qty: int) -> str:
    growth = (next_qty - current_qty) / max(current_qty, 1)
    if growth > 0.10:
        return "UP"
    if growth < -0.10:
        return "DOWN"
    return "STABLE"


def _trend_rows(catalog_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    months = _month_sequence(2023, 1, 2026, 7)
    rows: list[dict[str, Any]] = []
    for product in catalog_rows:
        history = _simulate_product_months(product, months)
        for index in range(3, len(history) - 1):
            current = history[index]
            following = history[index + 1]
            previous = history[index - 3 : index]
            target_month = following["month"]
            rows.append(
                {
                    "row_id": f"trend-{product['product_id']}-{current['month'].isoformat()}",
                    "feature_period_start": current["month"].isoformat(),
                    "target_period_start": target_month.isoformat(),
                    "split": _trend_split(target_month),
                    "product_id": product["product_id"],
                    "product_slug": product["product_slug"],
                    "category_slug": product["category_slug"],
                    "min_price_usd": product["min_price_usd"],
                    "weight_kg": product["weight_kg"],
                    "volume_cm3": product["volume_cm3"],
                    "origin_count": product["origin_count"],
                    "supplier_count": product["supplier_count"],
                    "max_supplier_rating": product["max_supplier_rating"],
                    "product_views": current["product_views"],
                    "search_impressions": current["search_impressions"],
                    "quote_requests": current["quote_requests"],
                    "saved_quotes": current["saved_quotes"],
                    "order_count": current["order_count"],
                    "ordered_qty": current["ordered_qty"],
                    "gmv_bdt": _decimal(current["gmv_bdt"], 2),
                    "cancelled_orders": current["cancelled_orders"],
                    "delivered_orders": current["delivered_orders"],
                    "on_time_delivery_count": current["on_time_delivery_count"],
                    "defect_count": current["defect_count"],
                    "ordered_qty_lag_1": history[index - 1]["ordered_qty"],
                    "ordered_qty_lag_2": history[index - 2]["ordered_qty"],
                    "ordered_qty_lag_3": history[index - 3]["ordered_qty"],
                    "ordered_qty_trailing_mean_3": _decimal(mean(item["ordered_qty"] for item in previous), 4),
                    "gmv_trailing_mean_3": _decimal(mean(item["gmv_bdt"] for item in previous), 2),
                    "quote_to_order_rate": _decimal(
                        current["order_count"] / max(current["quote_requests"], 1),
                        6,
                    ),
                    "target_next_month_order_qty": following["ordered_qty"],
                    "target_next_month_gmv_bdt": _decimal(following["gmv_bdt"], 2),
                    "target_next_month_trend": _trend_label(current["ordered_qty"], following["ordered_qty"]),
                    "feature_source": "synthetic_simulation",
                    "label_source": "synthetic_simulation",
                    "is_synthetic": 1,
                    "simulation_version": SIMULATION_VERSION,
                    "simulation_seed": SIMULATION_SEED,
                }
            )
    return rows


def _dictionary_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(
        dataset: str,
        fields: Iterable[str],
        *,
        targets: set[str] | None = None,
        identifiers: set[str] | None = None,
        source: str,
    ) -> None:
        targets = targets or set()
        identifiers = identifiers or set()
        for field in fields:
            role = "target" if field in targets else "identifier" if field in identifiers else "metadata" if field in {
                "split",
                "group_split",
                "feature_source",
                "label_source",
                "is_synthetic",
                "training_readiness",
                "record_source",
                "source_revision",
                "schema_version",
                "simulation_version",
                "simulation_seed",
            } else "feature"
            data_type = "string"
            if field.endswith("_at_utc") or field.endswith("_period_start"):
                data_type = "datetime"
            elif field.startswith(("is_", "has_", "missing_")) or field.endswith("_flag"):
                data_type = "boolean"
            elif field.endswith(("_id", "_count", "_qty", "_days", "_seed")) or field in {
                "stock",
                "moq",
                "quantity",
                "product_views",
                "search_impressions",
                "quote_requests",
                "saved_quotes",
                "order_count",
                "ordered_qty_lag_1",
                "ordered_qty_lag_2",
                "ordered_qty_lag_3",
            }:
                data_type = "integer"
            elif any(token in field for token in ("price", "cost", "rate", "rating", "weight", "volume", "gmv")):
                data_type = "number"
            description = field.replace("_", " ").capitalize()
            leakage_note = ""
            if role == "target":
                leakage_note = "Never include this target in the input feature matrix."
            if field in {"product_id", "product_slug", "example_id", "row_id", "event_id"}:
                leakage_note = "Use as a key only; exclude from generalization-focused model features."
            rows.append(
                {
                    "dataset": dataset,
                    "field": field,
                    "data_type": data_type,
                    "role": role,
                    "description": description,
                    "source": source,
                    "allowed_or_range": "",
                    "leakage_note": leakage_note,
                }
            )

    add(
        "catalog_bootstrap.csv",
        CATALOG_FIELDS,
        identifiers={"product_id", "product_slug", "variant_id"},
        source="public-catalog.snapshot.json",
    )
    add(
        "category_text_classification.csv",
        CATEGORY_FIELDS,
        targets={"target_category_slug", "target_category_name"},
        identifiers={"example_id", "product_id"},
        source="public-catalog.snapshot.json",
    )
    add(
        "offer_price_regression.csv",
        OFFER_FIELDS,
        targets={"target_offer_price_usd"},
        identifiers={"example_id"},
        source="general_goods_v1.json deterministic offer templates",
    )
    add(
        "product_countries.csv",
        PRODUCT_COUNTRY_FIELDS,
        identifiers={"product_id", "product_slug"},
        source="public-catalog.snapshot.json",
    )
    add(
        "product_monthly_trends_synthetic.csv",
        TREND_FIELDS,
        targets={"target_next_month_order_qty", "target_next_month_gmv_bdt", "target_next_month_trend"},
        identifiers={"row_id", "product_id", "product_slug"},
        source=SIMULATION_VERSION,
    )
    add(
        "real_sourcing_outcomes_template.csv",
        OUTCOME_FIELDS,
        targets={
            "converted_to_order",
            "payment_approved",
            "actual_landed_cost_bdt",
            "actual_delivery_days",
            "delayed_flag",
            "cancelled_flag",
            "refunded_flag",
            "quality_defect_flag",
            "dispute_flag",
        },
        identifiers={"event_id"},
        source="future observed application events",
    )
    return rows


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _csv_profile(path: Path) -> tuple[int, int]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        return sum(1 for _ in reader), len(header)


def _dataset_card(file_profiles: dict[str, dict[str, Any]]) -> str:
    trend_rows = file_profiles["product_monthly_trends_synthetic.csv"]["rows"]
    return f"""# SourceAI ML starter datasets v1

This directory contains reproducible, PII-free datasets for learning and prototyping.
It does **not** contain observed marketplace outcomes and must not support production AI-accuracy claims.

## Files

- `catalog_bootstrap.csv` — 610 static product/variant feature rows for clustering and exploratory price work.
- `category_text_classification.csv` — 610 product-name/model examples with catalog taxonomy labels.
- `offer_price_regression.csv` — 560 seed-derived offer examples with formula-generated price targets.
- `product_countries.csv` — normalized product-to-origin relationships.
- `product_monthly_trends_synthetic.csv` — {trend_rows:,} simulated monthly examples for next-month demand/GMV/trend tutorials.
- `real_sourcing_outcomes_template.csv` — header-only contract for collecting genuine quote/order/delivery outcomes.
- `data_dictionary.csv` — field roles, provenance, and leakage guidance.
- `manifest.json` — source hashes, file hashes, row counts, and safety disclosures.

## What can be trained now

1. Category text classification using `product_name` and `model`.
2. Tutorial offer-price regression. Do not call it a live-market price model: its target is formula-generated.
3. Tutorial next-month quantity/GMV regression or `UP`/`DOWN`/`STABLE` classification using the synthetic trend table.
4. Product similarity or clustering with the static catalog features.

## Split rules

- Static/category/offer files use a category-stratified product-group split. A product never crosses splits.
- The synthetic trend file uses chronological splits. `purge` rows create a one-month gap and must not be trained on.
- Fit encoders, imputers, and scalers on `train` only.

## Critical limitations

- Every row is seed-derived or simulated; `is_synthetic=1` is intentional.
- Snapshot risk and delivery fields were excluded as targets because risk is one class and delivery is constant.
- Snapshot heuristic score was excluded because it is an arithmetic formula, often above 100, and would create circular leakage.
- Product names may contain category words, so category classification can overestimate real-world generalization.
- The trend series is deterministic simulation, not historical demand. It is useful for pipeline practice only.
- Never mix these pseudo labels with a future observed test set.

## Generate and validate

From the repository root:

```powershell
python services/catalog-service/scripts/export_ml_starter_datasets.py
python services/catalog-service/scripts/export_ml_starter_datasets.py --check
```

For a real model, populate the outcome template from event-time snapshots after the observation window closes.
Do not export names, emails, phones, addresses, payment transaction IDs, screenshots, tokens, or support free text.
"""


def _validate_rows(
    catalog_rows: list[dict[str, Any]],
    category_rows: list[dict[str, Any]],
    offer_rows: list[dict[str, Any]],
    product_country_rows: list[dict[str, Any]],
    trend_rows: list[dict[str, Any]],
) -> None:
    if len(catalog_rows) != 610 or len({row["product_id"] for row in catalog_rows}) != 610:
        raise RuntimeError("Catalog bootstrap must contain 610 unique products")
    if len(category_rows) != 610 or len({row["example_id"] for row in category_rows}) != 610:
        raise RuntimeError("Category dataset must contain 610 unique examples")
    if len(offer_rows) != 560 or len({row["example_id"] for row in offer_rows}) != 560:
        raise RuntimeError("Offer dataset must contain 560 unique examples")
    if len(product_country_rows) != 1930:
        raise RuntimeError("Product-country dataset must contain 1,930 relationships")
    product_country_keys = {(row["product_id"], row["country_code"]) for row in product_country_rows}
    if len(product_country_keys) != len(product_country_rows):
        raise RuntimeError("Product-country relationships are not unique")
    if len(trend_rows) != 23790 or len({row["row_id"] for row in trend_rows}) != len(trend_rows):
        raise RuntimeError("Synthetic trend dataset must contain 23,790 unique rows")

    split_by_product: dict[int, set[str]] = defaultdict(set)
    for row in category_rows:
        split_by_product[int(row["product_id"])].add(str(row["split"]))
    if any(len(values) != 1 for values in split_by_product.values()):
        raise RuntimeError("A product crosses category-dataset splits")
    if set(row["split"] for row in category_rows) != {"train", "validation", "test"}:
        raise RuntimeError("Category dataset is missing a required split")
    if set(row["split"] for row in offer_rows) != {"train", "validation", "test"}:
        raise RuntimeError("Offer dataset is missing a required split")
    for row in offer_rows:
        if not 1 <= float(row["supplier_rating"]) <= 5:
            raise RuntimeError("Offer supplier rating is outside 1..5")
        if float(row["target_offer_price_usd"]) <= 0 or int(row["stock"]) < 0 or int(row["moq"]) < 1:
            raise RuntimeError("Offer numeric domain rule failed")

    trend_labels = Counter(str(row["target_next_month_trend"]) for row in trend_rows if row["split"] != "purge")
    if set(trend_labels) != {"UP", "DOWN", "STABLE"} or min(trend_labels.values()) < 500:
        raise RuntimeError("Synthetic trend labels lack useful class coverage")
    if set(row["split"] for row in trend_rows) != {"train", "validation", "test", "purge"}:
        raise RuntimeError("Synthetic trend dataset is missing chronological split markers")
    for row in trend_rows:
        if not (
            int(row["order_count"]) <= int(row["saved_quotes"]) <= int(row["quote_requests"]) <= int(row["product_views"])
        ):
            raise RuntimeError("Synthetic funnel counts are inconsistent")
        if int(row["cancelled_orders"]) + int(row["delivered_orders"]) != int(row["order_count"]):
            raise RuntimeError("Synthetic order outcomes do not reconcile")
        if int(row["on_time_delivery_count"]) > int(row["delivered_orders"]):
            raise RuntimeError("Synthetic on-time count exceeds delivered orders")


def build_dataset_pack(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    snapshot = _read_json(SNAPSHOT_PATH)
    manifest_source = _read_json(GENERAL_GOODS_PATH)
    products = list(snapshot["products"])
    splits = _group_splits(products)
    catalog_rows, category_rows, product_country_rows = _flatten_catalog(snapshot, splits)
    offer_rows = _offer_training_rows(manifest_source, splits)
    trend_rows = _trend_rows(catalog_rows)
    dictionary_rows = _dictionary_rows()
    _validate_rows(catalog_rows, category_rows, offer_rows, product_country_rows, trend_rows)

    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    datasets = {
        "catalog_bootstrap.csv": (CATALOG_FIELDS, catalog_rows, "Static catalog features; bootstrap only"),
        "category_text_classification.csv": (CATEGORY_FIELDS, category_rows, "Catalog taxonomy tutorial"),
        "offer_price_regression.csv": (OFFER_FIELDS, offer_rows, "Formula-label price regression tutorial"),
        "product_countries.csv": (PRODUCT_COUNTRY_FIELDS, product_country_rows, "Product-origin relationship table"),
        "product_monthly_trends_synthetic.csv": (TREND_FIELDS, trend_rows, "Synthetic next-month forecasting tutorial"),
        "real_sourcing_outcomes_template.csv": (OUTCOME_FIELDS, [], "PII-free future observed-outcome contract"),
        "data_dictionary.csv": (DICTIONARY_FIELDS, dictionary_rows, "Field definitions and leakage notes"),
    }
    for filename, (fields, rows, _purpose) in datasets.items():
        _write_csv(output / filename, fields, rows)

    file_profiles: dict[str, dict[str, Any]] = {}
    for filename, (_fields, _rows, purpose) in datasets.items():
        rows, columns = _csv_profile(output / filename)
        file_profiles[filename] = {
            "rows": rows,
            "columns": columns,
            "sha256": _sha256(output / filename),
            "purpose": purpose,
        }

    (output / "README.md").write_text(_dataset_card(file_profiles), encoding="utf-8", newline="\n")
    file_profiles["README.md"] = {
        "rows": None,
        "columns": None,
        "sha256": _sha256(output / "README.md"),
        "purpose": "Dataset card",
    }
    manifest = {
        "schema_version": 1,
        "dataset_revision": DATASET_REVISION,
        "training_readiness": "tutorial_only",
        "contains_pii": False,
        "contains_observed_outcomes": False,
        "sources": [
            {
                "path": SNAPSHOT_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": _sha256(SNAPSHOT_PATH),
                "source_revision": str(snapshot["source_revision"]),
            },
            {
                "path": GENERAL_GOODS_PATH.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": _sha256(GENERAL_GOODS_PATH),
                "source_revision": str(manifest_source["catalog_revision"]),
            },
        ],
        "simulation": {
            "version": SIMULATION_VERSION,
            "seed": SIMULATION_SEED,
            "feature_period_start": "2023-04-01",
            "feature_period_end": "2026-06-01",
            "target_period_end": "2026-07-01",
            "is_real_history": False,
        },
        "files": file_profiles,
        "warnings": [
            "Seed-derived and simulated rows are not observed marketplace outcomes.",
            "Do not use this pack to claim production model accuracy or live market performance.",
            "Do not mix pseudo/synthetic labels into an observed validation or test set.",
        ],
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def check_dataset_pack(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output = output.resolve()
    manifest_path = output / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"Dataset manifest not found: {manifest_path}")
    manifest = _read_json(manifest_path)
    if manifest.get("dataset_revision") != DATASET_REVISION:
        raise RuntimeError("Dataset revision is unsupported")
    for source in manifest["sources"]:
        source_path = REPOSITORY_ROOT / source["path"]
        if _sha256(source_path) != source["sha256"]:
            raise RuntimeError(f"Source changed; regenerate the dataset pack: {source['path']}")
    for filename, profile in manifest["files"].items():
        path = output / filename
        if not path.is_file() or _sha256(path) != profile["sha256"]:
            raise RuntimeError(f"Dataset file checksum mismatch: {filename}")
        if filename.endswith(".csv"):
            rows, columns = _csv_profile(path)
            if rows != profile["rows"] or columns != profile["columns"]:
                raise RuntimeError(f"Dataset file shape mismatch: {filename}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the PII-free SourceAI ML tutorial dataset pack.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Validate the committed pack without changing files.")
    args = parser.parse_args()
    try:
        manifest = check_dataset_pack(args.output) if args.check else build_dataset_pack(args.output)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError, csv.Error) as exc:
        print(f"ML dataset pack failed: {exc}")
        return 1
    total_rows = sum(profile["rows"] or 0 for profile in manifest["files"].values())
    action = "validated" if args.check else "generated"
    print(f"ML dataset pack {action}: files={len(manifest['files'])}, csv_rows={total_rows:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
