from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_session
from ...config import Settings
from ...models import Country
from ...services.market_intelligence import country_risk_map, fx_outlook
from ...schemas import CheapestCountryRecommendIn, QuoteRecommendIn, QuoteRequestIn
from ...services.sourcing import build_country_recommendations, build_quote, recommend_routes
from ...services.automation import country_automation_context, explain_recommendation, quote_automation_context


router = APIRouter()


@router.post("/api/quote/")
def quote(payload: QuoteRequestIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    return build_quote(session, payload)


@router.post("/api/quote/ai-explanation/")
def quote_ai_explanation(
    payload: QuoteRequestIn,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    quote_result = build_quote(session, payload)
    context = quote_automation_context(
        quote_result,
        country_code=payload.country,
        mode=payload.mode,
        language=payload.language,
    )
    settings: Settings = request.app.state.catalog_settings
    automation = explain_recommendation(context, settings)
    return {
        **quote_result,
        "ai_explanation": automation.explanation,
        "ai_metadata": {
            "source": automation.source,
            "model": automation.model if automation.automation_available else None,
            "prompt_version": "quote-v1",
            "automation_available": automation.automation_available,
            "unsupported_numbers_removed": len(automation.unsupported_numbers),
            "monetary_calculations_are_deterministic": True,
        },
    }


@router.get("/api/market/fx-outlook/")
def market_fx_outlook(
    request: Request,
    currency: str = "USD",
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    settings: Settings = request.app.state.catalog_settings
    return fx_outlook(session, currency[:10], settings.fx_outlook_horizon_days)


@router.get("/api/market/country-risk/")
def market_country_risk(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    risks = country_risk_map(session)
    countries = session.scalars(select(Country).order_by(Country.name.asc())).all()
    return [{"code": country.code, "name": country.name, "risk": risks.get(country.id)} for country in countries]


@router.post("/api/quote/recommend/")
def quote_recommend(payload: QuoteRecommendIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    routes = recommend_routes(session, payload)
    if not routes:
        raise HTTPException(status_code=404, detail="No routes available")
    return {
        "priority": payload.priority,
        "routes": routes,
    }


@router.post("/api/recommendations/cheapest-country/")
def cheapest_country_recommendation(
    payload: CheapestCountryRecommendIn,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    return build_country_recommendations(session, payload)


@router.post("/api/recommendations/cheapest-country/ai-explanation/")
def cheapest_country_ai_explanation(
    payload: CheapestCountryRecommendIn,
    request: Request,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    recommendation = build_country_recommendations(session, payload)
    settings: Settings = request.app.state.catalog_settings
    automation = explain_recommendation(country_automation_context(recommendation, language=payload.language), settings)
    return {
        **recommendation,
        "ai_explanation": automation.explanation,
        "ai_metadata": {
            "source": automation.source,
            "model": automation.model if automation.automation_available else None,
            "automation_available": automation.automation_available,
            "unsupported_numbers_removed": len(automation.unsupported_numbers),
            "monetary_calculations_are_deterministic": True,
        },
    }
