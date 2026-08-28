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


def normalize_explanation_language(value: Any) -> str:
    """Return the only locale values supported by the public explanation API."""
    return "bn" if str(value or "").strip().lower() == "bn" else "en"


def _contains_bangla(value: str) -> bool:
    return any("\u0980" <= character <= "\u09ff" for character in value)


def _matches_explanation_language(value: str, language: str) -> bool:
    """Reject cross-locale model output instead of leaking it into the UI.

    Bangla copy can legitimately include Latin product names and technical
    terms, but it must contain some Bangla script. English copy must not
    contain Bangla script at all.
    """
    has_bangla = _contains_bangla(value)
    return has_bangla if language == "bn" else not has_bangla


def fallback_explanation(recommendation: dict[str, Any]) -> dict[str, Any]:
    top = (recommendation.get("recommendations") or [{}])[0]
    country = (top.get("country") or {}).get("name", "the selected origin")
    risk_level = str(top.get("risk_level") or "Unknown")
    language = normalize_explanation_language(recommendation.get("response_language"))
    translations = {
        "lowest landed cost": "সর্বনিম্ন ল্যান্ডেড কস্ট",
        "fastest ETA": "সবচেয়ে দ্রুত সম্ভাব্য ডেলিভারি",
        "strongest supplier quality": "সাপ্লায়ারের গুণমান সবচেয়ে ভালো",
        "balanced trade-off across cost, ETA, and supplier quality": "খরচ, ডেলিভারি ও সাপ্লায়ারের গুণমানের ভারসাম্যপূর্ণ সমন্বয়",
        "limited supplier reliability": "সাপ্লায়ারের নির্ভরযোগ্যতা সীমিত",
        "quality evidence is below target": "গুণমানের প্রমাণ লক্ষ্যমাত্রার নিচে",
        "delivery time is long": "ডেলিভারি সময় বেশি",
        "sea freight has higher delay exposure": "সমুদ্রপথে বিলম্বের ঝুঁকি বেশি",
        "Supply-chain CSV rows are imported as dataset-backed products, suppliers, stock, MOQ, and origin prices.": "সাপ্লাই-চেইন CSV থেকে পণ্য, সাপ্লায়ার, মজুত, MOQ ও উৎসের মূল্য নেওয়া হয়েছে।",
        "Supplier quality is estimated from inspection results and defect rates in the CSV.": "CSV-এর পরিদর্শন ফলাফল ও ত্রুটির হার থেকে সাপ্লায়ারের গুণমান অনুমান করা হয়েছে।",
        "Shipping and tariff rules are still normalized reference estimates until carrier-specific feeds are connected.": "ক্যারিয়ার-নির্দিষ্ট তথ্য সংযুক্ত না হওয়া পর্যন্ত শিপিং ও ট্যারিফের পরিমাণ রেফারেন্স অনুমান হিসেবে থাকবে।",
        "External marketplace and tariff feeds should replace seeded heuristics before production rollout.": "প্রোডাকশন চালুর আগে লাইভ মার্কেটপ্লেস ও ট্যারিফ তথ্য দিয়ে প্রাথমিক অনুমান প্রতিস্থাপন করতে হবে।",
        "Server-calculated landed cost and delivery estimate": "সার্ভারে হিসাব করা ল্যান্ডেড কস্ট ও ডেলিভারি অনুমান",
        "No eligible supplier offer is available": "কোনো যোগ্য সাপ্লায়ার অফার পাওয়া যায়নি",
        "Supplier rating is below the preferred threshold": "সাপ্লায়ারের রেটিং পছন্দের সীমার নিচে",
        "Delivery time is long": "ডেলিভারি সময় বেশি",
        "Sea freight has additional delay exposure": "সমুদ্রপথে অতিরিক্ত বিলম্বের ঝুঁকি রয়েছে",
        "Carrier quote, tariff classification and supplier documents require final verification.": "ক্যারিয়ার কোট, ট্যারিফ শ্রেণিবিন্যাস ও সাপ্লায়ারের নথি চূড়ান্তভাবে যাচাই করা প্রয়োজন।",
        "Carrier quote is not live": "লাইভ ক্যারিয়ার কোট পাওয়া যায়নি",
    }
    translate = lambda value: translations.get(str(value), str(value)) if language == "bn" else str(value)  # noqa: E731
    advantages = [translate(value) for value in top.get("advantages") or []][:5]
    weaknesses = [translate(value) for value in top.get("weaknesses") or []][:5]
    localized_risk_level = {
        "low": "কম",
        "medium": "মাঝারি",
        "high": "উচ্চ",
        "unknown": "অজানা",
    }.get(risk_level.lower(), risk_level)
    summary = (
        f"বর্তমান যাচাইযোগ্য হিসাব অনুযায়ী {country} শীর্ষ সোর্সিং বিকল্প। ঝুঁকির মাত্রা: {localized_risk_level}।"
        if language == "bn"
        else f"Based on the current verifiable calculation, {country} is the top sourcing option. Risk level: {risk_level}."
    )
    return {
        "summary": summary,
        # Backward-compatible alias for older web clients. Despite the legacy
        # name, its value always follows the requested response language.
        "summary_bn": summary,
        "language": language,
        "advantages": advantages,
        "risks": weaknesses,
        "missing_information": [translate(value) for value in recommendation.get("data_gaps") or []][:5],
        "recommended_checks": ([
            "সাপ্লায়ারের পরিচয় ও বর্তমান মজুত স্বাধীনভাবে যাচাই করুন।",
            "চূড়ান্ত ট্যারিফ, HS কোড, সনদ এবং ক্যারিয়ার কোট যাচাই করুন।",
        ] if language == "bn" else [
            "Independently verify the supplier identity and current stock.",
            "Verify the final tariff, HS code, certification, and carrier quote.",
        ]),
        "confidence": None,
        "human_review_required": risk_level.lower() in {"medium", "high"},
    }


def validated_explanation(
    value: Any,
    fallback: dict[str, Any],
    *,
    language: str | None = None,
) -> dict[str, Any]:
    expected_language = normalize_explanation_language(language or fallback.get("language"))
    if not isinstance(value, dict):
        return fallback
    result = dict(fallback)
    result["language"] = expected_language
    summary = str(result.get("summary") or result.get("summary_bn") or "").strip()[:2000]
    for key in ("summary", "summary_bn"):
        candidate = value.get(key)
        if (
            isinstance(candidate, str)
            and candidate.strip()
            and _matches_explanation_language(candidate.strip(), expected_language)
        ):
            summary = candidate.strip()[:2000]
            break
    result["summary"] = summary
    result["summary_bn"] = summary
    for key in ("advantages", "risks", "missing_information", "recommended_checks"):
        candidate = value.get(key)
        if isinstance(candidate, list):
            source_items = [str(item).strip()[:500] for item in candidate if str(item).strip()]
            localized_items = [
                item for item in source_items if _matches_explanation_language(item, expected_language)
            ][:8]
            # An explicitly empty list is meaningful. If the model supplied
            # only the wrong language, retain the deterministic localized copy.
            if not source_items or localized_items:
                result[key] = localized_items
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
    language = normalize_explanation_language(recommendation.get("response_language"))
    fallback = fallback_explanation(recommendation)
    if not settings.automation_webhook_url or not settings.automation_webhook_token:
        return AutomationResult(fallback, "deterministic-fallback", False)

    payload = json.dumps(
        {
            "event": "quote.recommendation.explain.v1",
            "recommendation": recommendation,
            "output_contract": {
                "summary": f"string in {language}",
                "summary_bn": "string",
                "language": language,
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
    return AutomationResult(
        validated_explanation(explanation, fallback, language=language),
        "ollama-via-n8n",
        True,
    )


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
