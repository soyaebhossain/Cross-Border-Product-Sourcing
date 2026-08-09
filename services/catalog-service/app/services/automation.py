from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import Settings


@dataclass(frozen=True)
class AutomationResult:
    explanation: dict[str, Any]
    source: str
    automation_available: bool


def fallback_explanation(recommendation: dict[str, Any]) -> dict[str, Any]:
    top = (recommendation.get("recommendations") or [{}])[0]
    country = (top.get("country") or {}).get("name", "the selected origin")
    risk_level = str(top.get("risk_level") or "Unknown")
    advantages = [str(value) for value in top.get("advantages") or []][:5]
    weaknesses = [str(value) for value in top.get("weaknesses") or []][:5]
    return {
        "summary_bn": f"{country} বর্তমান যাচাইযোগ্য হিসাব অনুযায়ী শীর্ষ sourcing option। ঝুঁকির মাত্রা: {risk_level}।",
        "advantages": advantages,
        "risks": weaknesses,
        "missing_information": list(recommendation.get("data_gaps") or [])[:5],
        "recommended_checks": [
            "Supplier identity and current stock independently verify করুন।",
            "Final tariff, HS code, certification and carrier quote verify করুন।",
        ],
        "confidence": None,
        "human_review_required": risk_level.lower() in {"medium", "high"},
    }


def validated_explanation(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return fallback
    result = dict(fallback)
    for key in ("summary_bn",):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            result[key] = candidate.strip()[:2000]
    for key in ("advantages", "risks", "missing_information", "recommended_checks"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            result[key] = [str(item).strip()[:500] for item in candidate if str(item).strip()][:8]
    confidence = value.get("confidence")
    if isinstance(confidence, (int, float)) and 0 <= float(confidence) <= 1:
        result["confidence"] = float(confidence)
    if isinstance(value.get("human_review_required"), bool):
        result["human_review_required"] = value["human_review_required"] or fallback["human_review_required"]
    return result


def explain_recommendation(
    recommendation: dict[str, Any],
    settings: Settings,
) -> AutomationResult:
    fallback = fallback_explanation(recommendation)
    if not settings.automation_webhook_url or not settings.automation_webhook_token:
        return AutomationResult(fallback, "deterministic-fallback", False)

    payload = json.dumps(
        {
            "event": "quote.recommendation.explain.v1",
            "recommendation": recommendation,
            "output_contract": {
                "summary_bn": "string",
                "advantages": "string[]",
                "risks": "string[]",
                "missing_information": "string[]",
                "recommended_checks": "string[]",
                "confidence": "number 0..1",
                "human_review_required": "boolean",
            },
        },
        default=str,
    ).encode("utf-8")
    request = Request(
        settings.automation_webhook_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {settings.automation_webhook_token}",
            "Content-Type": "application/json",
            "User-Agent": "SourceAI-Automation/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.automation_timeout_seconds) as response:  # noqa: S310
            if not 200 <= int(response.status) < 300:
                return AutomationResult(fallback, "deterministic-fallback", False)
            body = json.loads(response.read(131_072).decode("utf-8"))
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return AutomationResult(fallback, "deterministic-fallback", False)
    explanation = body.get("explanation", body) if isinstance(body, dict) else body
    return AutomationResult(validated_explanation(explanation, fallback), "ollama-via-n8n", True)


def quote_automation_context(
    quote: dict[str, Any],
    *,
    country_code: str,
    mode: str,
) -> dict[str, Any]:
    offers = quote.get("offers_top") or []
    rating = float((offers[0] if offers else {}).get("rating") or 0)
    eta_max = int((quote.get("eta") or {}).get("max_days") or 0)
    weaknesses: list[str] = []
    risk_points = 0
    if not offers:
        risk_points += 2
        weaknesses.append("No eligible supplier offer is available")
    elif rating < 3.5:
        risk_points += 1
        weaknesses.append("Supplier rating is below the preferred threshold")
    if eta_max > 25:
        risk_points += 1
        weaknesses.append("Delivery time is long")
    if mode == "BULK":
        risk_points += 1
        weaknesses.append("Sea freight has additional delay exposure")
    risk_level = "High" if risk_points >= 2 else "Medium" if risk_points == 1 else "Low"
    return {
        "recommendations": [
            {
                "country": {"code": country_code.upper(), "name": country_code.upper()},
                "mode": mode,
                "risk_level": risk_level,
                "advantages": ["Server-calculated landed cost and delivery estimate"],
                "weaknesses": weaknesses,
                "estimated_total_bdt": (quote.get("breakdown") or {}).get("total_bdt"),
                "eta": quote.get("eta"),
                "selected_offer": offers[0] if offers else None,
            }
        ],
        "data_gaps": [
            "Carrier quote, tariff classification and supplier documents require final verification."
        ],
    }
