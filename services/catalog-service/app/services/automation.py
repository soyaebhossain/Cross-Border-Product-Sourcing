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
    language = recommendation.get("response_language", "en")
    translations = {
        "lowest landed cost": "সর্বনিম্ন ল্যান্ডেড কস্ট",
        "fastest ETA": "সবচেয়ে দ্রুত সম্ভাব্য ডেলিভারি",
        "strongest supplier quality": "সাপ্লায়ারের গুণমান সবচেয়ে ভালো",
        "balanced trade-off across cost, ETA, and supplier quality": "খরচ, ডেলিভারি ও সাপ্লায়ারের গুণমানের ভারসাম্যপূর্ণ সমন্বয়",
        "limited supplier reliability": "সাপ্লায়ারের নির্ভরযোগ্যতা সীমিত",
        "quality evidence is below target": "গুণমানের প্রমাণ লক্ষ্যমাত্রার নিচে",
        "delivery time is long": "ডেলিভারি সময় বেশি",
        "sea freight has higher delay exposure": "সমুদ্রপথে বিলম্বের ঝুঁকি বেশি",
        "Supply-chain CSV rows are imported as dataset-backed products, suppliers, stock, MOQ, and origin prices.": "পণ্য, সাপ্লায়ার, স্টক, MOQ ও উৎসের মূল্য dataset থেকে নেওয়া হয়েছে।",
        "Supplier quality is estimated from inspection results and defect rates in the CSV.": "সাপ্লায়ারের গুণমান inspection result ও defect rate থেকে অনুমান করা হয়েছে।",
        "Shipping and tariff rules are still normalized reference estimates until carrier-specific feeds are connected.": "Carrier-specific feed যুক্ত না হওয়া পর্যন্ত shipping ও tariff reference estimate হিসেবে থাকবে।",
        "External marketplace and tariff feeds should replace seeded heuristics before production rollout.": "Production চালুর আগে live marketplace ও tariff feed দিয়ে seeded estimate প্রতিস্থাপন করতে হবে।",
    }
    translate = lambda value: translations.get(str(value), str(value)) if language == "bn" else str(value)  # noqa: E731
    advantages = [translate(value) for value in top.get("advantages") or []][:5]
    weaknesses = [translate(value) for value in top.get("weaknesses") or []][:5]
    return {
        "summary_bn": (
            f"বর্তমান যাচাইযোগ্য হিসাব অনুযায়ী {country} শীর্ষ sourcing option। ঝুঁকির মাত্রা: {risk_level}।"
            if language == "bn"
            else f"Based on the current verifiable calculation, {country} is the top sourcing option. Risk level: {risk_level}."
        ),
        "advantages": advantages,
        "risks": weaknesses,
        "missing_information": [translate(value) for value in recommendation.get("data_gaps") or []][:5],
        "recommended_checks": ([
            "Supplier identity ও বর্তমান stock স্বাধীনভাবে যাচাই করুন।",
            "Final tariff, HS code, certification ও carrier quote যাচাই করুন।",
        ] if language == "bn" else [
            "Independently verify the supplier identity and current stock.",
            "Verify the final tariff, HS code, certification, and carrier quote.",
        ]),
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
    language: str = "en",
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
        "response_language": language,
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


def country_automation_context(recommendation: dict[str, Any], *, language: str = "en") -> dict[str, Any]:
    """Keep the LLM payload small while preserving authoritative ranking facts."""
    compact_routes: list[dict[str, Any]] = []
    for route in (recommendation.get("recommendations") or [])[:3]:
        offer = route.get("selected_offer") or {}
        compact_routes.append(
            {
                "rank": route.get("rank"),
                "country": route.get("country"),
                "mode": route.get("mode"),
                "score": route.get("score"),
                "estimated_total_bdt": route.get("estimated_total_bdt"),
                "eta": route.get("eta"),
                "risk_level": route.get("risk_level"),
                "advantages": list(route.get("advantages") or [])[:3],
                "weaknesses": list(route.get("weaknesses") or [])[:3],
                "supplier": offer.get("seller_name"),
            }
        )
    return {
        "response_language": language,
        "product": recommendation.get("product"),
        "priority": recommendation.get("priority"),
        "qty": recommendation.get("qty"),
        "recommendations": compact_routes,
        "data_gaps": list(recommendation.get("data_gaps") or [])[:5],
    }
