from __future__ import annotations

import csv
import io
from collections import Counter
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...db import get_session
from ...models import Country, Order, Product, SavedQuote, Seller, SellerOffer

router = APIRouter()


def _quote_rows(session: Session) -> list[dict[str, Any]]:
    rows = []
    for quote in session.scalars(select(SavedQuote).order_by(SavedQuote.created_at.desc())).all():
        breakdown = (quote.response or {}).get("breakdown", {})
        rows.append({
            "quote_id": quote.id, "product": quote.product_name, "variant": quote.variant_name,
            "country": quote.country_code, "mode": quote.mode, "quantity": quote.qty,
            "product_cost_bdt": breakdown.get("product_cost_bdt", breakdown.get("origin_price_bdt", "0")),
            "shipping_bdt": breakdown.get("shipping_bdt", "0"),
            "customs_duty_bdt": breakdown.get("customs_duty_bdt", "0"),
            "vat_tax_bdt": breakdown.get("vat_tax_bdt", "0"),
            "handling_charge_bdt": breakdown.get("handling_charge_bdt", breakdown.get("service_fee_bdt", "0")),
            "total_landed_cost_bdt": breakdown.get("total_bdt", "0"),
            "recommendation_score": (quote.response or {}).get("sourcing_score", ""),
            "risk_level": (quote.response or {}).get("risk_level", ""),
            "created_at": quote.created_at.isoformat() if quote.created_at else "",
        })
    return rows


@router.get("/api/research/analytics/")
def analytics(session: Session = Depends(get_session)) -> dict[str, Any]:
    quotes = _quote_rows(session)
    orders = session.scalars(select(Order)).all()
    countries = dict(session.execute(select(Country.code, Country.name)).all())
    country_counts = Counter(row["country"] for row in quotes)
    totals = [Decimal(str(row["total_landed_cost_bdt"] or 0)) for row in quotes]
    active = {"PENDING", "PAID", "PROCESSING", "SHIPPED"}
    return {
        "cards": {
            "total_products": session.scalar(select(func.count(Product.id))) or 0,
            "total_suppliers": session.scalar(select(func.count(Seller.id))) or 0,
            "pending_quotations": len(quotes),
            "active_orders": sum(1 for order in orders if order.status in active),
            "average_landed_cost_bdt": format(sum(totals) / len(totals), ".2f") if totals else "0.00",
            "high_risk_suppliers": session.scalar(select(func.count(Seller.id)).where(Seller.rating < 3)) or 0,
            "quote_to_order_conversion_rate": round((len(orders) / len(quotes) * 100), 2) if quotes else 0,
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
def export_research_csv(session: Session = Depends(get_session)) -> StreamingResponse:
    rows = _quote_rows(session)
    output = io.StringIO()
    fields = list(rows[0].keys()) if rows else ["quote_id", "product", "country", "total_landed_cost_bdt"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader(); writer.writerows(rows)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=sourcing-research.csv"})
