from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...db import get_session
from ...serializers import serialize_category, serialize_country, serialize_product
from ...services.ai_insights import build_ai_insights
from ...services.catalog import browse_products, get_product_by_slug_or_404, list_categories, list_countries, list_products


router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "catalog-service"}


@router.get("/api/categories/")
def categories(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [serialize_category(category) for category in list_categories(session)]


@router.get("/api/countries/")
def countries(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    return [serialize_country(country) for country in list_countries(session)]


@router.get("/api/ai/insights/")
def ai_insights(q: str = Query(default="")) -> dict[str, Any]:
    return build_ai_insights(q.strip())


@router.get("/api/products/")
def products(
    q: str = Query(default="", max_length=120),
    session: Session = Depends(get_session),
) -> list[dict[str, Any]]:
    return [serialize_product(product) for product in list_products(session, q=q)]


@router.get("/api/products/{slug}/")
def product_by_slug(slug: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    return serialize_product(get_product_by_slug_or_404(session, slug))


@router.get("/api/catalog/browse/")
def product_browser(q: str = Query(default="", max_length=120), category: str = Query(default=""),
                    page: int = Query(default=1, ge=1), page_size: int = Query(default=24, ge=1, le=60),
                    sort: str = Query(default="name", pattern="^(name|name_desc|cheapest|fastest|highest_rated|recommended)$"),
                    country: str = Query(default="", max_length=2), min_price: float | None = Query(default=None, ge=0),
                    max_price: float | None = Query(default=None, ge=0), max_delivery: int | None = Query(default=None, ge=1),
                    min_rating: float | None = Query(default=None, ge=0, le=5),
                    risk: str = Query(default="", pattern="^(|Low|Medium|High)$"),
                    session: Session = Depends(get_session)) -> dict[str, Any]:
    items, total, summaries = browse_products(session, q, category, page, page_size, sort, country, min_price,
                                               max_price, max_delivery, min_rating, risk)
    serialized = []
    for item in items:
        data = serialize_product(item); data["market"] = summaries[item.id]; serialized.append(data)
    return {"items": serialized, "total": total, "page": page,
            "page_size": page_size, "pages": max(1, (total + page_size - 1) // page_size)}
