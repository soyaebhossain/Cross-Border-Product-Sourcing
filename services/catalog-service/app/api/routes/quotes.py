from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...db import get_session
from ...schemas import CheapestCountryRecommendIn, QuoteRecommendIn, QuoteRequestIn
from ...services.sourcing import build_country_recommendations, build_quote, recommend_routes


router = APIRouter()


@router.post("/api/quote/")
def quote(payload: QuoteRequestIn, session: Session = Depends(get_session)) -> dict[str, Any]:
    return build_quote(session, payload)


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
