from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from ...config import Settings, get_settings
from ...db import get_session
from ...serializers import serialize_category, serialize_country, serialize_product
from ...services.ai_insights import build_ai_insights
from ...services.catalog import (
    browse_products,
    build_market_summaries,
    get_product_by_slug_or_404,
    list_categories,
    list_countries,
    list_products,
)


router = APIRouter()
READINESS_QUERIES = (
    "SELECT id, role, is_active FROM accounts_users LIMIT 1",
    "SELECT id, status, expires_at FROM orders_saved_quotes LIMIT 1",
    "SELECT id, saved_quote_id, idempotency_key FROM orders_orders LIMIT 1",
    "SELECT id, trx_normalized, decision FROM orders_manual_payments LIMIT 1",
    "SELECT id, request_id FROM admin_audit_events LIMIT 1",
)


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "catalog-service"}


@router.head("/api/health", include_in_schema=False)
def health_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


def _runtime_settings(request: Request) -> Settings:
    return getattr(request.app.state, "catalog_settings", None) or get_settings()


@router.get("/api/ready", response_model=None)
def readiness(
    session: Session = Depends(get_session),
    runtime_settings: Settings = Depends(_runtime_settings),
) -> dict[str, str | bool] | JSONResponse:
    password_reset_email_configured = runtime_settings.password_reset_email_configured
    signed_proxy_identity_configured = runtime_settings.signed_proxy_identity_configured
    try:
        for statement in READINESS_QUERIES:
            session.execute(text(statement))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unavailable",
                "service": "catalog-service",
                "database": "unavailable",
                "password_reset_email_configured": password_reset_email_configured,
                "signed_proxy_identity_configured": signed_proxy_identity_configured,
            },
        )
    return {
        "status": "ready",
        "service": "catalog-service",
        "database": "ready",
        "password_reset_email_configured": password_reset_email_configured,
        "signed_proxy_identity_configured": signed_proxy_identity_configured,
    }


@router.head("/api/ready", include_in_schema=False)
def readiness_head(
    session: Session = Depends(get_session),
    runtime_settings: Settings = Depends(_runtime_settings),
) -> Response:
    result = readiness(session=session, runtime_settings=runtime_settings)
    status_code = result.status_code if isinstance(result, JSONResponse) else status.HTTP_200_OK
    return Response(status_code=status_code)


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
    product = get_product_by_slug_or_404(session, slug)
    data = serialize_product(product)
    data["market"] = build_market_summaries(session, [product])[product.id]
    return data


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
