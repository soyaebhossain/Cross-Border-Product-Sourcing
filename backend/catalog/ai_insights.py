from __future__ import annotations

import csv
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings


DATA_DIR = settings.BASE_DIR.parent / "Data"

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


def _mobile_sales_insight(query: str) -> dict:
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
    ram_counter: Counter[str] = Counter()

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
        if row.get("RAM"):
            ram_counter[row["RAM"]] += qty or 1

    average_order_value = total_value / Decimal(total_qty) if total_qty else Decimal("0")
    top_brand = brand_counter.most_common(1)[0][0] if brand_counter else "Unknown"
    top_region = region_counter.most_common(1)[0][0] if region_counter else "Unknown"
    top_product = product_counter.most_common(1)[0][0] if product_counter else "Unknown"
    top_ram = ram_counter.most_common(1)[0][0] if ram_counter else "Unknown"

    return {
        "source": "Data/mobile_sales_data.csv",
        "matched_rows": len(matched),
        "total_quantity_sold": total_qty,
        "average_unit_price": str(average_order_value.quantize(Decimal("1"))) if total_qty else "0",
        "top_brand": top_brand,
        "top_region": top_region,
        "top_product_type": top_product,
        "top_ram": top_ram,
        "summary": (
            f"{top_brand} leads the matched sales sample, with strongest demand in {top_region}. "
            f"Typical matched unit price is about {average_order_value.quantize(Decimal('1'))} BDT."
            if total_qty
            else "No usable sales rows matched this product."
        ),
    }


def _stock_rows(path: Path) -> list[dict[str, str]]:
    rows = _read_csv(path)
    return [row for row in rows if _decimal(row.get("Close") or row.get("close")) is not None]


def _market_signals() -> list[dict]:
    signals: list[dict] = []
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


def _campaign_insights() -> dict:
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


def _supply_chain_insights(query: str) -> dict:
    terms = [part.lower() for part in query.split() if part.strip()]
    rows = _read_csv(DATA_DIR / "supply_chain_data.csv")
    matched = [row for row in rows if _matches(row, terms)]
    if not matched and terms:
        matched = rows

    product_counter: Counter[str] = Counter()
    supplier_counter: Counter[str] = Counter()
    route_counter: Counter[str] = Counter()
    total_revenue = Decimal("0")
    total_defect_rate = Decimal("0")
    usable_defect_rows = 0

    for row in matched:
        product_type = row.get("Product type") or "Unknown"
        supplier = row.get("Supplier name") or "Unknown"
        route = row.get("Routes") or "Unknown"
        product_counter[product_type] += 1
        supplier_counter[supplier] += 1
        route_counter[route] += 1
        total_revenue += _decimal(row.get("Revenue generated")) or Decimal("0")
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
        "total_revenue_generated": str(total_revenue.quantize(Decimal("0.01"))),
        "average_defect_rate": str(average_defect_rate.quantize(Decimal("0.01"))),
        "summary": (
            f"{top_product} has the strongest supply-chain signal, led by {top_supplier} on {top_route}. "
            f"Average defect rate is {average_defect_rate.quantize(Decimal('0.01'))}%."
            if matched
            else "No usable supply-chain rows matched this query."
        ),
    }


def _ml_trends() -> dict:
    """
    ML-style trend engine over mobile_sales_data.csv.
    Computes: monthly momentum, brand growth rate, regional velocity,
    spec popularity, and demand forecast direction.
    """
    rows = _read_csv(DATA_DIR / "mobile_sales_data.csv")

    monthly_qty: dict[str, int] = defaultdict(int)
    monthly_rev: dict[str, float] = defaultdict(float)
    brand_monthly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    region_monthly: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    spec_counter: Counter[str] = Counter()
    processor_counter: Counter[str] = Counter()
    price_sum: dict[str, float] = defaultdict(float)
    price_count: dict[str, int] = defaultdict(int)

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

        monthly_qty[month_key] += qty
        monthly_rev[month_key] += qty * price
        brand_monthly[brand][month_key] += qty
        region_monthly[region][month_key] += qty
        if ram:
            spec_counter[ram] += qty or 1
        if processor and processor != "N/A":
            processor_counter[processor] += qty or 1
        if brand:
            price_sum[brand] += price
            price_count[brand] += 1

    sorted_months = sorted(monthly_qty.keys())

    # Moving average & trend direction (last 3 months vs previous 3)
    def _trend(series: dict[str, int]) -> dict:
        months = sorted(series.keys())
        if len(months) < 4:
            return {"direction": "stable", "change_pct": 0.0, "recent_avg": 0}
        recent = months[-3:]
        previous = months[-6:-3] if len(months) >= 6 else months[:3]
        recent_avg = sum(series[m] for m in recent) / len(recent)
        prev_avg = sum(series[m] for m in previous) / len(previous)
        if prev_avg == 0:
            return {"direction": "stable", "change_pct": 0.0, "recent_avg": int(recent_avg)}
        change_pct = ((recent_avg - prev_avg) / prev_avg) * 100
        direction = "up" if change_pct > 2 else "down" if change_pct < -2 else "stable"
        return {
            "direction": direction,
            "change_pct": round(change_pct, 2),
            "recent_avg": int(recent_avg),
        }

    overall_trend = _trend(monthly_qty)

    # Brand momentum: which brand grew fastest in last 3 months
    brand_trends = []
    for brand, monthly in brand_monthly.items():
        t = _trend(monthly)
        if t["recent_avg"] > 50:  # filter noise
            brand_trends.append({"brand": brand, **t})
    brand_trends.sort(key=lambda x: x["change_pct"], reverse=True)

    # Regional velocity
    region_trends = []
    for region, monthly in region_monthly.items():
        t = _trend(monthly)
        region_trends.append({"region": region, **t})
    region_trends.sort(key=lambda x: x["change_pct"], reverse=True)

    # Monthly summary (last 6 months)
    monthly_series = [
        {
            "month": m,
            "qty": monthly_qty[m],
            "revenue": round(monthly_rev[m], 0),
        }
        for m in sorted_months[-6:]
    ]

    # Average price per top brand
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
            f"Fastest growing brand: {brand_trends[0]['brand'] if brand_trends else 'N/A'} "
            f"({brand_trends[0]['change_pct']:+.1f}%)."
            if brand_trends else "Insufficient data for forecast."
        ),
    }


def build_ai_insights(query: str = "") -> dict:
    sales = _mobile_sales_insight(query)
    supply_chain = _supply_chain_insights(query)
    market = _market_signals()
    campaigns = _campaign_insights()
    trends = _ml_trends()

    recommendations = []
    if supply_chain["matched_rows"]:
        recommendations.append(
            f"Use {supply_chain['top_supplier']} for {supply_chain['top_product_type']} sourcing on {supply_chain['top_route']}."
        )
        recommendations.append(
            f"Monitor QC — matched supply-chain defect rate averages {supply_chain['average_defect_rate']}%."
        )
    if sales["total_quantity_sold"]:
        recommendations.append(f"Prioritize {sales['top_brand']} or similar suppliers for matched demand.")
        recommendations.append(f"Focus stock near {sales['top_region']} demand patterns for local dispatch.")
    if trends["top_growing_brands"]:
        top = trends["top_growing_brands"][0]
        recommendations.append(
            f"ML signal: {top['brand']} demand growing {top['change_pct']:+.1f}% — source inventory proactively."
        )
    if trends["top_ram_specs"]:
        top_ram = trends["top_ram_specs"][0]
        recommendations.append(
            f"Spec trend: {top_ram['ram']} RAM dominates ({top_ram['units']:,} units) — prioritise this spec tier."
        )
    if market:
        strongest = market[0]
        recommendations.append(
            f"Watch {strongest['name']} market movement ({strongest['period_change_percent']}%) before large sourcing."
        )
    if campaigns["campaign_count"]:
        recommendations.append(
            f"Use {campaigns['top_channel']} campaigns with {campaigns['top_discount_type']} discounts for demand testing."
        )

    import_demand = _import_demand_insights(query)

    if import_demand.get("top_scarce_products"):
        top = import_demand["top_scarce_products"][0]
        recommendations.append(
            f"Import opportunity: {top['product_type']} — demand={top['demand_score']}/10, "
            f"BD availability={top['bd_availability']}/10. Best source: {top['best_source']}."
        )

    return {
        "query": query,
        "methodology": "CSV-backed ML trend engine — moving average, brand momentum, regional velocity, spec popularity, import demand.",
        "supply_chain": supply_chain,
        "sales": sales,
        "market_signals": market,
        "campaigns": campaigns,
        "trends": trends,
        "import_demand": import_demand,
        "recommendations": recommendations,
    }


# ── Import Demand ML Engine ───────────────────────────────────────────────────

def _import_demand_insights(query: str = "") -> dict:
    """
    Analyses bangladesh_import_demand.csv to find:
    - Products with high demand but low BD availability
    - Best source country per category
    - Duty/ETA estimates
    - Import risk signals
    """
    rows = _read_csv(DATA_DIR / "bangladesh_import_demand.csv")
    terms = [t.lower() for t in query.split() if t.strip()]

    if terms:
        filtered = [r for r in rows if any(t in " ".join(r.values()).lower() for t in terms)]
        if not filtered:
            filtered = rows
    else:
        filtered = rows

    # Score: demand_score / (bd_availability + 1) — higher = better import opportunity
    scored = []
    for row in filtered:
        try:
            demand = float(row.get("demand_score", 0) or 0)
            avail  = float(row.get("bd_availability", 5) or 5)
            price  = float(row.get("avg_price_usd", 0) or 0)
            duty   = float(row.get("import_duty_pct", 0) or 0)
            vat    = float(row.get("vat_pct", 0) or 0)
            eta_air_min = int(row.get("min_lead_air", 5) or 5)
            eta_air_max = int(row.get("max_lead_air", 10) or 10)
            eta_sea_min = int(row.get("min_lead_sea", 20) or 20)
            eta_sea_max = int(row.get("max_lead_sea", 35) or 35)
            score = demand / (avail + 1)
            source = row.get("source_country", "CN").split("/")[0].strip()

            landed_air = round(price * (1 + (duty + vat) / 100), 2)
            landed_sea = round(price * (1 + (duty + vat) / 100) * 0.97, 2)  # sea cheaper

            scored.append({
                "product_type":   row.get("product_type", "Unknown"),
                "category":       row.get("category_slug", ""),
                "source_country": row.get("source_country", "CN"),
                "best_source":    source,
                "bd_availability": int(avail),
                "demand_score":   int(demand),
                "opportunity_score": round(score, 2),
                "avg_price_usd":  price,
                "hs_code":        row.get("hs_code", ""),
                "import_duty_pct": duty,
                "vat_pct":        vat,
                "landed_price_air_usd": landed_air,
                "landed_price_sea_usd": landed_sea,
                "eta_air":        f"{eta_air_min}-{eta_air_max} days",
                "eta_sea":        f"{eta_sea_min}-{eta_sea_max} days",
                "restriction":    row.get("restriction_level", "low"),
                "note":           row.get("sourcing_note", ""),
            })
        except (ValueError, TypeError):
            continue

    scored.sort(key=lambda x: x["opportunity_score"], reverse=True)

    # Category-level aggregation
    cat_scores: dict[str, list[float]] = defaultdict(list)
    cat_sources: dict[str, Counter] = defaultdict(Counter)
    for item in scored:
        cat_scores[item["category"]].append(item["opportunity_score"])
        cat_sources[item["category"]][item["best_source"]] += 1

    category_summary = []
    for cat, scores in sorted(cat_scores.items(), key=lambda x: -sum(x[1]) / len(x[1])):
        top_src = cat_sources[cat].most_common(1)[0][0] if cat_sources[cat] else "CN"
        category_summary.append({
            "category": cat,
            "avg_opportunity": round(sum(scores) / len(scores), 2),
            "product_count": len(scores),
            "top_source": top_src,
        })

    # High-risk items (restricted or high duty)
    risk_items = [s for s in scored if s["restriction"] in ("medium", "high") or s["import_duty_pct"] > 20]

    return {
        "source": "Data/bangladesh_import_demand.csv",
        "total_products_analysed": len(scored),
        "top_scarce_products": scored[:8],
        "category_opportunities": category_summary[:6],
        "high_restriction_items": risk_items[:5],
        "summary": (
            f"Top import opportunity: {scored[0]['product_type']} "
            f"(demand {scored[0]['demand_score']}/10, BD availability {scored[0]['bd_availability']}/10). "
            f"Best source: {scored[0]['best_source']}."
            if scored else "No import demand data matched."
        ),
    }


def predict_eta(category_slug: str, source_country: str = "CN", qty: int = 1, mode: str = "air") -> dict:
    """
    ML-powered ETA predictor using bangladesh_import_demand.csv.
    Returns recommended source, ETA range, landed cost estimate, and risk.
    """
    rows = _read_csv(DATA_DIR / "bangladesh_import_demand.csv")

    # Find rows matching the category
    cat_rows = [r for r in rows if r.get("category_slug", "") == category_slug]
    if not cat_rows:
        # Fallback: generic estimate
        return {
            "recommended_source": source_country,
            "eta_days_min": 5 if mode == "air" else 20,
            "eta_days_max": 10 if mode == "air" else 35,
            "confidence": "low",
            "avg_duty_pct": 10.0,
            "avg_vat_pct": 15.0,
            "import_risk": "low",
            "note": "No category-specific data. Using generic estimate.",
        }

    # Filter by source country if specified
    country_rows = [r for r in cat_rows if source_country in r.get("source_country", "")]
    if not country_rows:
        country_rows = cat_rows

    # Compute weighted averages
    total = len(country_rows)
    eta_min_key = "min_lead_air" if mode == "air" else "min_lead_sea"
    eta_max_key = "max_lead_air" if mode == "air" else "max_lead_sea"

    def avg_field(rows, key):
        vals = [float(r.get(key, 0) or 0) for r in rows]
        return round(sum(vals) / len(vals), 1) if vals else 0

    avg_eta_min = avg_field(country_rows, eta_min_key)
    avg_eta_max = avg_field(country_rows, eta_max_key)
    avg_duty    = avg_field(country_rows, "import_duty_pct")
    avg_vat     = avg_field(country_rows, "vat_pct")
    avg_price   = avg_field(country_rows, "avg_price_usd")

    # Qty adjustment: sea becomes viable for large orders
    if qty >= 10 and mode == "air":
        mode_recommendation = "Consider sea freight — cheaper for qty >= 10 units"
    elif qty < 3 and mode == "sea":
        mode_recommendation = "Consider air freight — faster and cost-effective for small qty"
    else:
        mode_recommendation = f"{mode.title()} freight optimal for this order size"

    # Risk
    restrictions = Counter(r.get("restriction_level", "low") for r in country_rows)
    dominant_risk = restrictions.most_common(1)[0][0]

    # Best source by frequency
    source_counter = Counter()
    for r in country_rows:
        for s in r.get("source_country", "CN").split("/"):
            source_counter[s.strip()] += 1
    recommended_src = source_counter.most_common(1)[0][0] if source_counter else source_country

    confidence = "high" if total >= 5 else "medium" if total >= 2 else "low"

    return {
        "category": category_slug,
        "source_country": source_country,
        "recommended_source": recommended_src,
        "mode": mode,
        "qty": qty,
        "eta_days_min": int(avg_eta_min),
        "eta_days_max": int(avg_eta_max),
        "eta_label": f"{int(avg_eta_min)}-{int(avg_eta_max)} days via {mode}",
        "avg_duty_pct": avg_duty,
        "avg_vat_pct": avg_vat,
        "landed_cost_multiplier": round(1 + (avg_duty + avg_vat) / 100, 3),
        "avg_unit_price_usd": avg_price,
        "import_risk": dominant_risk,
        "confidence": confidence,
        "mode_recommendation": mode_recommendation,
        "data_points": total,
    }
