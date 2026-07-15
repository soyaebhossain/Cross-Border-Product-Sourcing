from __future__ import annotations

import csv
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..config import ROOT_DIR


DATA_DIR = ROOT_DIR / "Data"

STOCK_FILES = {
    "Apple": "AAPL.csv",
    "Amazon": "Amazon stock data 2000-2025.csv",
    "Alibaba": "BABA.csv",
    "NVIDIA": "NVIDIA_STOCK.csv",
    "Samsung": "Samsung Dataset.csv",
    "Tesla": "TSLA.csv",
    "Intel": "data.csv",
}


def _read_csv(path: Path, limit: int | None = None) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if limit is not None and index >= limit:
                break
            rows.append({str(key or "").strip(): str(value or "").strip() for key, value in row.items()})
    return rows


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


def _mobile_sales_insight(query: str) -> dict[str, Any]:
    terms = [part.lower() for part in query.split() if part.strip()]
    rows = _read_csv(DATA_DIR / "mobile_sales_data.csv")
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


def _market_signals() -> list[dict[str, str]]:
    signals: list[dict[str, str]] = []
    for name, filename in STOCK_FILES.items():
        rows = _stock_rows(DATA_DIR / filename)
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


def _campaign_insights() -> dict[str, Any]:
    rows = _read_csv(DATA_DIR / "dataset_fashion_store_campaigns.csv")
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


def _supply_chain_insights(query: str) -> dict[str, Any]:
    terms = [part.lower() for part in query.split() if part.strip()]
    rows = _read_csv(DATA_DIR / "supply_chain_data.csv")
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


def _ml_trends() -> dict[str, Any]:
    rows = _read_csv(DATA_DIR / "mobile_sales_data.csv")

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


def build_ai_insights(query: str = "") -> dict[str, Any]:
    sales = _mobile_sales_insight(query)
    supply_chain = _supply_chain_insights(query)
    market = _market_signals()
    campaigns = _campaign_insights()
    trends = _ml_trends()

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
        "query": query,
        "methodology": "CSV-backed ML trend engine — moving average, brand momentum, regional velocity, spec popularity.",
        "supply_chain": supply_chain,
        "sales": sales,
        "market_signals": market,
        "campaigns": campaigns,
        "trends": trends,
        "recommendations": recommendations,
    }
