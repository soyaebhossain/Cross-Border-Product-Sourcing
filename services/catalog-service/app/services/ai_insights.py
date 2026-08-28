from __future__ import annotations

import csv
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import get_settings


ML_STARTER_REQUIRED_FILES = (
    "manifest.json",
    "catalog_bootstrap.csv",
    "product_monthly_trends_synthetic.csv",
)
LEGACY_REQUIRED_FILES = (
    "mobile_sales_data.csv",
    "supply_chain_data.csv",
)

STOCK_FILES = {
    "Apple": "AAPL.csv",
    "Amazon": "Amazon stock data 2000-2025.csv",
    "Alibaba": "BABA.csv",
    "NVIDIA": "NVIDIA_STOCK.csv",
    "Samsung": "Samsung Dataset.csv",
    "Tesla": "TSLA.csv",
    "Intel": "data.csv",
}


@lru_cache(maxsize=16)
def _cached_csv_rows(path_value: str, modified_ns: int) -> tuple[dict[str, str], ...]:
    del modified_ns  # Included in the cache key so replaced datasets are re-read.
    path = Path(path_value)
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    str(key or "").strip(): str(value or "").strip()
                    for key, value in row.items()
                }
            )
    return tuple(rows)


def _read_csv(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows = _cached_csv_rows(str(path.resolve()), path.stat().st_mtime_ns)
    selected = rows if limit is None else rows[:limit]
    return list(selected)


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = str(value).replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _matches(row: dict[str, str], terms: list[str]) -> bool:
    if not terms:
        return True
    haystack = " ".join(row.values()).lower()
    return any(term in haystack for term in terms)


def _mobile_sales_insight(query: str, data_dir: Path) -> dict[str, Any]:
    terms = [part.lower() for part in query.split() if part.strip()]
    rows = _read_csv(data_dir / "mobile_sales_data.csv")
    matched = [row for row in rows if _matches(row, terms)]
    if not matched and terms:
        matched = rows

    total_qty = 0
    total_value = Decimal("0")
    brand_counter: Counter[str] = Counter()
    region_counter: Counter[str] = Counter()
    product_counter: Counter[str] = Counter()

    for row in matched:
        qty = int(_decimal(row.get("Quantity Sold")) or 0)
        price = _decimal(row.get("Price")) or Decimal("0")
        total_qty += qty
        total_value += price * qty
        if row.get("Brand"):
            brand_counter[row["Brand"]] += qty or 1
        if row.get("Region"):
            region_counter[row["Region"]] += qty or 1
        if row.get("Product"):
            product_counter[row["Product"]] += qty or 1

    average_order_value = total_value / Decimal(total_qty) if total_qty else Decimal("0")
    top_brand = brand_counter.most_common(1)[0][0] if brand_counter else "Unknown"
    top_region = region_counter.most_common(1)[0][0] if region_counter else "Unknown"
    top_product = product_counter.most_common(1)[0][0] if product_counter else "Unknown"

    return {
        "source": "Data/mobile_sales_data.csv",
        "matched_rows": len(matched),
        "total_quantity_sold": total_qty,
        "average_unit_price": str(average_order_value.quantize(Decimal("1"))) if total_qty else "0",
        "top_brand": top_brand,
        "top_region": top_region,
        "top_product_type": top_product,
        "summary": (
            f"{top_brand} leads the matched sales sample, with strongest demand in {top_region}."
            if total_qty
            else "No usable sales rows matched this product."
        ),
    }


def _stock_rows(path: Path) -> list[dict[str, str]]:
    rows = _read_csv(path)
    return [row for row in rows if _decimal(row.get("Close") or row.get("close")) is not None]


def _market_signals(data_dir: Path) -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for name, filename in STOCK_FILES.items():
        rows = _stock_rows(data_dir / filename)
        if len(rows) < 2:
            continue
        first = _decimal(rows[0].get("Close") or rows[0].get("close"))
        last = _decimal(rows[-1].get("Close") or rows[-1].get("close"))
        if first is None or last is None or first == 0:
            continue
        change = ((last - first) / first) * Decimal("100")
        signals.append(
            {
                "name": name,
                "source": f"Data/{filename}",
                "latest_close": str(last),
                "period_change_percent": str(change.quantize(Decimal("0.01"))),
                "direction": "up" if change >= 0 else "down",
            }
        )
    return sorted(signals, key=lambda item: abs(Decimal(item["period_change_percent"])), reverse=True)[:5]


def _campaign_insights(data_dir: Path) -> dict[str, Any]:
    rows = _read_csv(data_dir / "dataset_fashion_store_campaigns.csv")
    channel_counter: Counter[str] = Counter()
    discount_counter: Counter[str] = Counter()
    for row in rows:
        if row.get("channel"):
            channel_counter[row["channel"]] += 1
        if row.get("discount_type"):
            discount_counter[row["discount_type"]] += 1

    return {
        "source": "Data/dataset_fashion_store_campaigns.csv",
        "campaign_count": len(rows),
        "top_channel": channel_counter.most_common(1)[0][0] if channel_counter else "Unknown",
        "top_discount_type": discount_counter.most_common(1)[0][0] if discount_counter else "Unknown",
    }


def _supply_chain_insights(query: str, data_dir: Path) -> dict[str, Any]:
    terms = [part.lower() for part in query.split() if part.strip()]
    rows = _read_csv(data_dir / "supply_chain_data.csv")
    matched = [row for row in rows if _matches(row, terms)]
    if not matched and terms:
        matched = rows

    product_counter: Counter[str] = Counter()
    supplier_counter: Counter[str] = Counter()
    route_counter: Counter[str] = Counter()
    total_defect_rate = Decimal("0")
    usable_defect_rows = 0

    for row in matched:
        product_counter[row.get("Product type") or "Unknown"] += 1
        supplier_counter[row.get("Supplier name") or "Unknown"] += 1
        route_counter[row.get("Routes") or "Unknown"] += 1
        defect_rate = _decimal(row.get("Defect rates"))
        if defect_rate is not None:
            total_defect_rate += defect_rate
            usable_defect_rows += 1

    average_defect_rate = total_defect_rate / Decimal(usable_defect_rows) if usable_defect_rows else Decimal("0")
    top_product = product_counter.most_common(1)[0][0] if product_counter else "Unknown"
    top_supplier = supplier_counter.most_common(1)[0][0] if supplier_counter else "Unknown"
    top_route = route_counter.most_common(1)[0][0] if route_counter else "Unknown"

    return {
        "source": "Data/supply_chain_data.csv",
        "matched_rows": len(matched),
        "top_product_type": top_product,
        "top_supplier": top_supplier,
        "top_route": top_route,
        "average_defect_rate": str(average_defect_rate.quantize(Decimal("0.01"))),
        "summary": (
            f"{top_product} has the strongest supply-chain signal, led by {top_supplier} on {top_route}."
            if matched
            else "No usable supply-chain rows matched this query."
        ),
    }


def _ml_trends(data_dir: Path) -> dict[str, Any]:
    rows = _read_csv(data_dir / "mobile_sales_data.csv")

    monthly_qty: dict[str, int] = {}
    monthly_rev: dict[str, float] = {}
    brand_monthly: dict[str, dict[str, int]] = {}
    region_monthly: dict[str, dict[str, int]] = {}
    spec_counter: Counter[str] = Counter()
    processor_counter: Counter[str] = Counter()
    price_sum: dict[str, float] = {}
    price_count: dict[str, int] = {}

    for row in rows:
        date_str = row.get("Inward Date", "")
        try:
            parts = date_str.split("/")
            month_key = f"{parts[2]}-{int(parts[0]):02d}"
        except Exception:
            continue

        qty = int(_decimal(row.get("Quantity Sold")) or 0)
        price = float(_decimal(row.get("Price")) or 0)
        brand = row.get("Brand", "Unknown")
        region = row.get("Region", "Unknown")
        ram = row.get("RAM", "")
        processor = row.get("Processor Specification", "")

        monthly_qty[month_key] = monthly_qty.get(month_key, 0) + qty
        monthly_rev[month_key] = monthly_rev.get(month_key, 0.0) + qty * price
        if brand not in brand_monthly:
            brand_monthly[brand] = {}
        brand_monthly[brand][month_key] = brand_monthly[brand].get(month_key, 0) + qty
        if region not in region_monthly:
            region_monthly[region] = {}
        region_monthly[region][month_key] = region_monthly[region].get(month_key, 0) + qty
        if ram:
            spec_counter[ram] += qty or 1
        if processor and processor != "N/A":
            processor_counter[processor] += qty or 1
        if brand:
            price_sum[brand] = price_sum.get(brand, 0.0) + price
            price_count[brand] = price_count.get(brand, 0) + 1

    sorted_months = sorted(monthly_qty.keys())

    def _trend(series: dict[str, int]) -> dict[str, Any]:
        months = sorted(series.keys())
        if len(months) < 4:
            return {"direction": "stable", "change_pct": 0.0, "recent_avg": 0}
        recent = months[-3:]
        previous = months[-6:-3] if len(months) >= 6 else months[:3]
        recent_avg = sum(series[m] for m in recent) / len(recent)
        prev_avg = sum(series[m] for m in previous) / max(len(previous), 1)
        if prev_avg == 0:
            return {"direction": "stable", "change_pct": 0.0, "recent_avg": int(recent_avg)}
        change_pct = ((recent_avg - prev_avg) / prev_avg) * 100
        direction = "up" if change_pct > 2 else "down" if change_pct < -2 else "stable"
        return {"direction": direction, "change_pct": round(change_pct, 2), "recent_avg": int(recent_avg)}

    overall_trend = _trend(monthly_qty)

    brand_trends: list[dict[str, Any]] = []
    for brand, monthly in brand_monthly.items():
        t = _trend(monthly)
        if t["recent_avg"] > 50:
            brand_trends.append({"brand": brand, **t})
    brand_trends.sort(key=lambda x: x["change_pct"], reverse=True)

    region_trends: list[dict[str, Any]] = []
    for region, monthly in region_monthly.items():
        t = _trend(monthly)
        region_trends.append({"region": region, **t})
    region_trends.sort(key=lambda x: x["change_pct"], reverse=True)

    monthly_series = [
        {"month": m, "qty": monthly_qty[m], "revenue": round(monthly_rev.get(m, 0), 0)}
        for m in sorted_months[-6:]
    ]

    brand_avg_price = {
        b: round(price_sum[b] / price_count[b], 0)
        for b in sorted(price_count, key=lambda x: price_count[x], reverse=True)[:5]
    }

    return {
        "source": "Data/mobile_sales_data.csv",
        "overall_trend": overall_trend,
        "top_growing_brands": brand_trends[:5],
        "regional_velocity": region_trends[:5],
        "top_ram_specs": [{"ram": k, "units": v} for k, v in spec_counter.most_common(5)],
        "top_processors": [{"processor": k, "units": v} for k, v in processor_counter.most_common(5)],
        "monthly_series": monthly_series,
        "brand_avg_price": brand_avg_price,
        "forecast": (
            f"Demand trending {overall_trend['direction']} ({overall_trend['change_pct']:+.1f}% vs prior period). "
            f"Fastest growing brand: {brand_trends[0]['brand'] if brand_trends else 'N/A'}."
            if brand_trends else "Insufficient data."
        ),
    }


def _starter_dataset_insights(query: str, data_dir: Path) -> dict[str, Any]:
    try:
        manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _unavailable_insights(
            query,
            data_dir,
            reason=f"The ML starter manifest cannot be read: {type(exc).__name__}",
        )

    catalog_rows = _read_csv(data_dir / "catalog_bootstrap.csv")
    trend_rows = _read_csv(data_dir / "product_monthly_trends_synthetic.csv")
    terms = [part.casefold() for part in query.split() if part.strip()]
    matched_catalog = [row for row in catalog_rows if _matches(row, terms)]
    matched_product_ids = {
        row.get("product_id", "") for row in matched_catalog if row.get("product_id")
    }
    matched_trends = [
        row
        for row in trend_rows
        if not terms or row.get("product_id", "") in matched_product_ids
    ]
    latest_period = max(
        (row.get("feature_period_start", "") for row in matched_trends),
        default="",
    )
    latest_rows = [
        row
        for row in matched_trends
        if row.get("feature_period_start", "") == latest_period
    ]

    category_by_product = {
        row.get("product_id", ""): row.get("category_name")
        or row.get("category_slug")
        or "Unknown"
        for row in catalog_rows
    }
    name_by_product = {
        row.get("product_id", ""): row.get("product_name")
        or row.get("product_slug")
        or "Unknown"
        for row in catalog_rows
    }
    category_forecast: Counter[str] = Counter()
    origin_counter: Counter[str] = Counter()
    forecast_rows: list[dict[str, Any]] = []
    total_forecast_qty = 0
    total_quotes = 0
    total_orders = 0
    trend_counter: Counter[str] = Counter()

    for row in matched_catalog:
        for country_code in row.get("origin_country_codes", "").split("|"):
            if country_code:
                origin_counter[country_code] += 1

    for row in latest_rows:
        product_id = row.get("product_id", "")
        forecast_qty = int(_decimal(row.get("target_next_month_order_qty")) or 0)
        total_forecast_qty += forecast_qty
        total_quotes += int(_decimal(row.get("quote_requests")) or 0)
        total_orders += int(_decimal(row.get("order_count")) or 0)
        category_forecast[category_by_product.get(product_id, "Unknown")] += forecast_qty
        trend_counter[row.get("target_next_month_trend") or "UNKNOWN"] += 1
        forecast_rows.append(
            {
                "product_id": product_id,
                "product": name_by_product.get(product_id, "Unknown"),
                "forecast_quantity": forecast_qty,
                "trend": row.get("target_next_month_trend") or "UNKNOWN",
            }
        )

    forecast_rows.sort(
        key=lambda item: (item["forecast_quantity"], item["product"]),
        reverse=True,
    )
    price_values = [
        value
        for row in matched_catalog
        if (value := _decimal(row.get("min_price_usd"))) is not None
    ]
    average_price = (
        sum(price_values, start=Decimal("0")) / Decimal(len(price_values))
        if price_values
        else Decimal("0")
    )
    top_category = (
        category_forecast.most_common(1)[0][0]
        if category_forecast
        else "No matching category"
    )
    top_origin = origin_counter.most_common(1)[0][0] if origin_counter else "Not available"
    training_readiness = str(manifest.get("training_readiness") or "tutorial_only")
    is_synthetic = bool(manifest.get("simulation", {}).get("is_real_history") is False)

    recommendations = [
        "Treat these values as tutorial-only synthetic signals, not observed demand or live market evidence."
    ]
    if latest_rows:
        recommendations.append(
            f"The synthetic next-month scenario is strongest for {top_category}; validate it with real quote and order outcomes before stocking."
        )
    if forecast_rows:
        recommendations.append(
            f"Review {forecast_rows[0]['product']} first in a controlled sourcing test; do not use the simulated forecast as an automated purchasing instruction."
        )

    return {
        "available": True,
        "status": "tutorial_data",
        "query": query,
        "dataset": {
            "name": "ml-starter-v1",
            "revision": manifest.get("dataset_revision"),
            "schema_version": manifest.get("schema_version"),
            "training_readiness": training_readiness,
            "contains_observed_outcomes": bool(
                manifest.get("contains_observed_outcomes", False)
            ),
            "is_synthetic": is_synthetic,
            "latest_feature_period": latest_period or None,
        },
        "methodology": (
            "Deterministic aggregation of the checked-in SourceAI ML starter dataset. "
            "The demand rows are synthetic and suitable for tutorial and pipeline validation only."
        ),
        "sales": {
            "matched_rows": len(matched_catalog),
            "total_quantity_sold": total_forecast_qty,
            "average_unit_price": format(average_price, ".2f"),
            "top_brand": "Not provided by this dataset",
            "top_region": top_origin,
            "top_product_type": top_category,
            "summary": (
                f"{len(latest_rows)} synthetic latest-period rows match this query."
                if latest_rows
                else "No tutorial dataset rows match this query."
            ),
        },
        "trends": {
            "latest_feature_period": latest_period or None,
            "matched_forecast_rows": len(latest_rows),
            "synthetic_next_month_quantity": total_forecast_qty,
            "quote_requests": total_quotes,
            "orders": total_orders,
            "trend_distribution": dict(sorted(trend_counter.items())),
            "top_products": forecast_rows[:5],
        },
        "market_signals": [],
        "campaigns": {
            "campaign_count": 0,
            "top_channel": "Not provided by this dataset",
            "top_discount_type": "Not provided by this dataset",
        },
        "recommendations": recommendations,
    }


def _unavailable_insights(
    query: str,
    data_dir: Path,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    missing = [
        filename for filename in ML_STARTER_REQUIRED_FILES if not (data_dir / filename).is_file()
    ]
    detail = reason or (
        f"Required dataset files are missing: {', '.join(missing)}"
        if missing
        else "The configured dataset layout is not supported"
    )
    return {
        "available": False,
        "status": "unavailable",
        "query": query,
        "dataset": {
            "name": "ml-starter-v1",
            "training_readiness": "unavailable",
            "contains_observed_outcomes": False,
            "is_synthetic": None,
        },
        "methodology": "AI insights are unavailable because the configured source data cannot be validated.",
        "reason": detail,
        "missing_files": missing,
        "market_signals": [],
        "recommendations": [],
    }


def build_ai_insights(
    query: str = "",
    *,
    data_dir: Path | None = None,
) -> dict[str, Any]:
    configured_data_dir = data_dir or get_settings().resolved_ai_insights_data_path()
    if all((configured_data_dir / name).is_file() for name in ML_STARTER_REQUIRED_FILES):
        return _starter_dataset_insights(query, configured_data_dir)
    if not all((configured_data_dir / name).is_file() for name in LEGACY_REQUIRED_FILES):
        return _unavailable_insights(query, configured_data_dir)

    sales = _mobile_sales_insight(query, configured_data_dir)
    supply_chain = _supply_chain_insights(query, configured_data_dir)
    market = _market_signals(configured_data_dir)
    campaigns = _campaign_insights(configured_data_dir)
    trends = _ml_trends(configured_data_dir)

    recommendations: list[str] = []
    if supply_chain["matched_rows"]:
        recommendations.append(
            f"Use {supply_chain['top_supplier']} for {supply_chain['top_product_type']} sourcing on {supply_chain['top_route']}."
        )
    if sales["total_quantity_sold"]:
        recommendations.append(f"Prioritize {sales['top_brand']} or similar suppliers for matched demand.")
    if trends["top_growing_brands"]:
        top = trends["top_growing_brands"][0]
        recommendations.append(
            f"ML signal: {top['brand']} demand growing {top['change_pct']:+.1f}% — source inventory proactively."
        )
    if trends["top_ram_specs"]:
        top_ram = trends["top_ram_specs"][0]
        recommendations.append(
            f"Spec trend: {top_ram['ram']} RAM dominates ({top_ram['units']:,} units) — prioritise this tier."
        )
    if market:
        strongest = market[0]
        recommendations.append(
            f"Watch {strongest['name']} market ({strongest['period_change_percent']}%) before large sourcing."
        )
    if campaigns["campaign_count"]:
        recommendations.append(
            f"Use {campaigns['top_channel']} campaigns with {campaigns['top_discount_type']} discounts for demand testing."
        )

    return {
        "available": True,
        "status": "legacy_data",
        "query": query,
        "dataset": {
            "name": "legacy-csv",
            "training_readiness": "unverified",
            "contains_observed_outcomes": None,
            "is_synthetic": None,
        },
        "methodology": "CSV-backed trend engine — moving average, brand momentum, regional velocity, and spec popularity.",
        "supply_chain": supply_chain,
        "sales": sales,
        "market_signals": market,
        "campaigns": campaigns,
        "trends": trends,
        "recommendations": recommendations,
    }
