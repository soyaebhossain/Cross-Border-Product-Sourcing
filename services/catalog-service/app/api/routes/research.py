from __future__ import annotations

import csv
import io
from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...db import get_session
from ...models import Country, Order, Product, SavedQuote, Seller, SellerOffer

router = APIRouter()
ACTIVE_ORDER_STATUSES = {
    "PENDING",
    "CONFIRMED",
    "PURCHASED",
    "IN_TRANSIT",
    "CUSTOMS",
    "LOCAL_DISPATCH",
}
PENDING_QUOTE_STATUSES = {"requested", "received"}
KNOWN_QUOTE_STATUSES = PENDING_QUOTE_STATUSES | {"approved", "expired"}


def get_research_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return current_user


def _safe_decimal(value: Any) -> Decimal | None:
    text = str(value or "0").strip()
    if not text or len(text) > 64:
        return None
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite() or parsed < 0:
        return None
    return parsed


def _spreadsheet_safe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _quote_rows(session: Session) -> list[dict[str, Any]]:
    rows = []
    for quote in session.scalars(select(SavedQuote).order_by(SavedQuote.created_at.desc())).all():
        response = quote.response or {}
        if not isinstance(response, dict):
            response = {}
        breakdown = response.get("breakdown", {})
        if not isinstance(breakdown, dict):
            breakdown = {}
        raw_status = str(quote.status or response.get("status", "requested")).strip().lower()
        quote_status = raw_status if raw_status in KNOWN_QUOTE_STATUSES else "unknown"
        rows.append({
            "quote_id": quote.id, "product": quote.product_name, "variant": quote.variant_name,
            "country": quote.country_code, "mode": quote.mode, "quantity": quote.qty,
            "product_cost_bdt": breakdown.get("product_cost_bdt", breakdown.get("origin_price_bdt", "0")),
            "shipping_bdt": breakdown.get("shipping_bdt", "0"),
            "customs_duty_bdt": breakdown.get("customs_duty_bdt", "0"),
            "vat_tax_bdt": breakdown.get("vat_tax_bdt", "0"),
            "handling_charge_bdt": breakdown.get("handling_charge_bdt", breakdown.get("service_fee_bdt", "0")),
            "total_landed_cost_bdt": breakdown.get("total_bdt", "0"),
            "recommendation_score": response.get("sourcing_score", ""),
            "risk_level": response.get("risk_level", ""),
            "status": quote_status,
            "created_at": quote.created_at.isoformat() if quote.created_at else "",
        })
    return rows


@router.get("/api/research/analytics/")
def analytics(
    session: Session = Depends(get_session),
    _current_user: dict[str, Any] = Depends(get_research_admin),
) -> dict[str, Any]:
    quotes = _quote_rows(session)
    orders = session.scalars(select(Order)).all()
    countries = dict(session.execute(select(Country.code, Country.name)).all())
    country_counts = Counter(row["country"] for row in quotes)
    totals = [
        parsed
        for row in quotes
        if (parsed := _safe_decimal(row["total_landed_cost_bdt"])) is not None
    ]
    pending_quote_count = sum(1 for row in quotes if row["status"] in PENDING_QUOTE_STATUSES)
    converted_quote_count = min(
        len({
            order.saved_quote_id
            for order in orders
            if order.saved_quote_id is not None
        }),
        len(quotes),
    )
    return {
        "cards": {
            "total_products": session.scalar(select(func.count(Product.id))) or 0,
            "total_suppliers": session.scalar(select(func.count(Seller.id))) or 0,
            "pending_quotations": pending_quote_count,
            "active_orders": sum(1 for order in orders if order.status in ACTIVE_ORDER_STATUSES),
            "average_landed_cost_bdt": format(sum(totals) / len(totals), ".2f") if totals else "0.00",
            "high_risk_suppliers": session.scalar(select(func.count(Seller.id)).where(Seller.rating < 3)) or 0,
            "quote_to_order_conversion_rate": round((converted_quote_count / len(quotes) * 100), 2) if quotes else 0,
        },
        "top_sourcing_countries": [{"country": countries.get(code, code), "quotes": count} for code, count in country_counts.most_common(5)],
        "evaluation": {
            "supplier_ranking": {"precision_at_k": None, "ndcg": None, "status": "Needs labelled relevance data"},
            "cost_prediction": {"mae": None, "rmse": None, "status": "Needs actual post-import costs"},
            "risk_prediction": {"accuracy": None, "f1": None, "status": "Needs confirmed risk outcomes"},
            "ux": {"decision_time": None, "user_satisfaction": None, "task_completion": None, "status": "Needs usability study events"},
        },
    }


@router.get("/api/research/export.csv")
def export_research_csv(
    session: Session = Depends(get_session),
    _current_user: dict[str, Any] = Depends(get_research_admin),
) -> StreamingResponse:
    rows = _quote_rows(session)
    output = io.StringIO()
    fields = list(rows[0].keys()) if rows else ["quote_id", "product", "country", "total_landed_cost_bdt"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(
        {key: _spreadsheet_safe(value) for key, value in row.items()}
        for row in rows
    )
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": "attachment; filename=sourcing-research.csv",
        },
    )
