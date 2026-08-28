from __future__ import annotations

import json

import pytest

from app.config import Settings
from app.services import automation


def _recommendation(risk: str = "Low") -> dict:
    return {
        "recommendations": [
            {
                "country": {"code": "CN", "name": "China"},
                "risk_level": risk,
                "advantages": ["lowest landed cost"],
                "weaknesses": ["delivery time is long"] if risk != "Low" else [],
                "estimated_total_bdt": "12000.00",
            }
        ],
        "data_gaps": ["Carrier quote is not live"],
    }


def test_unconfigured_automation_returns_deterministic_fallback() -> None:
    result = automation.explain_recommendation(
        _recommendation("Medium"),
        Settings(
            database_url="sqlite://",
            automation_webhook_url=None,
            automation_webhook_token=None,
        ),
    )

    assert result.automation_available is False
    assert result.source == "deterministic-fallback"
    assert result.explanation["human_review_required"] is True
    assert result.explanation["confidence"] is None
    assert result.explanation["language"] == "en"
    assert result.explanation["summary"] == result.explanation["summary_bn"]
    assert "China" in result.explanation["summary_bn"]


def test_bangla_fallback_localizes_explanation_fields() -> None:
    recommendation = _recommendation("Low")
    recommendation["response_language"] = "bn"
    recommendation["recommendations"][0]["advantages"] = ["lowest landed cost"]
    recommendation["data_gaps"] = [
        "Shipping and tariff rules are still normalized reference estimates until carrier-specific feeds are connected."
    ]

    result = automation.explain_recommendation(
        recommendation,
        Settings(
            database_url="sqlite://",
            automation_webhook_url=None,
            automation_webhook_token=None,
        ),
    )

    assert result.source == "deterministic-fallback"
    assert result.explanation["language"] == "bn"
    assert result.explanation["summary"] == result.explanation["summary_bn"]
    assert "বর্তমান যাচাইযোগ্য হিসাব" in result.explanation["summary_bn"]
    assert result.explanation["advantages"] == ["সর্বনিম্ন ল্যান্ডেড কস্ট"]
    assert "ক্যারিয়ার-নির্দিষ্ট তথ্য" in result.explanation["missing_information"][0]


def test_automation_response_is_bounded_and_cannot_disable_required_review(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(
                {
                    "explanation": {
                        "summary_bn": "AI explanation",
                        "advantages": ["a"] * 20,
                        "risks": [],
                        "missing_information": [],
                        "recommended_checks": [],
                        "confidence": 3,
                        "human_review_required": False,
                    }
                }
            ).encode()

    monkeypatch.setattr(automation, "urlopen", lambda *_args, **_kwargs: Response())
    settings = Settings(
        database_url="sqlite://",
        automation_webhook_url="http://n8n:5678/webhook/sourceai-quote-explanation",
        automation_webhook_token="secret-token",
    )
    result = automation.explain_recommendation(_recommendation("High"), settings)

    assert result.automation_available is True
    assert result.source == "ollama-via-n8n"
    assert result.explanation["summary_bn"] == "AI explanation"
    assert len(result.explanation["advantages"]) == 8
    assert result.explanation["confidence"] is None
    assert result.explanation["human_review_required"] is True


def test_english_response_rejects_bangla_model_copy_field_by_field(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(
                {
                    "explanation": {
                        "summary": "সোর্সিং সিদ্ধান্তের ব্যাখ্যা",
                        "language": "bn",
                        "advantages": ["কম ল্যান্ডেড কস্ট"],
                        "risks": ["Delivery time is long"],
                        "missing_information": ["ক্যারিয়ার কোট অনুপস্থিত"],
                        "recommended_checks": ["Verify the carrier quote"],
                        "confidence": 0.7,
                        "human_review_required": False,
                    }
                },
                ensure_ascii=False,
            ).encode("utf-8")

    monkeypatch.setattr(automation, "urlopen", lambda *_args, **_kwargs: Response())
    result = automation.explain_recommendation(
        _recommendation(),
        Settings(
            database_url="sqlite://",
            automation_webhook_url="http://n8n:5678/webhook/sourceai-quote-explanation",
            automation_webhook_token="secret-token",
        ),
    )

    assert result.automation_available is True
    assert result.explanation["language"] == "en"
    assert "Based on the current verifiable calculation" in result.explanation["summary"]
    assert result.explanation["summary_bn"] == result.explanation["summary"]
    assert result.explanation["advantages"] == ["lowest landed cost"]
    assert result.explanation["risks"] == ["Delivery time is long"]
    assert result.explanation["missing_information"] == ["Carrier quote is not live"]
    assert result.explanation["recommended_checks"] == ["Verify the carrier quote"]


def test_bangla_response_rejects_english_only_model_copy(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return json.dumps(
                {
                    "explanation": {
                        "summary": "English-only model summary",
                        "language": "en",
                        "advantages": ["lowest landed cost"],
                        "risks": [],
                        "missing_information": ["Carrier quote is not live"],
                        "recommended_checks": ["Verify the carrier quote"],
                        "confidence": 0.7,
                        "human_review_required": False,
                    }
                }
            ).encode()

    monkeypatch.setattr(automation, "urlopen", lambda *_args, **_kwargs: Response())
    recommendation = _recommendation()
    recommendation["response_language"] = "bn"
    result = automation.explain_recommendation(
        recommendation,
        Settings(
            database_url="sqlite://",
            automation_webhook_url="http://n8n:5678/webhook/sourceai-quote-explanation",
            automation_webhook_token="secret-token",
        ),
    )

    assert result.automation_available is True
    assert result.explanation["language"] == "bn"
    assert "বর্তমান যাচাইযোগ্য হিসাব" in result.explanation["summary"]
    assert result.explanation["advantages"] == ["সর্বনিম্ন ল্যান্ডেড কস্ট"]
    assert all(
        any("\u0980" <= character <= "\u09ff" for character in item)
        for key in ("advantages", "missing_information", "recommended_checks")
        for item in result.explanation[key]
    )


def test_invalid_automation_json_falls_back(monkeypatch) -> None:
    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b"not-json"

    monkeypatch.setattr(automation, "urlopen", lambda *_args, **_kwargs: Response())
    result = automation.explain_recommendation(
        _recommendation(),
        Settings(
            database_url="sqlite://",
            automation_webhook_url="http://n8n:5678/webhook/sourceai-quote-explanation",
            automation_webhook_token="secret-token",
        ),
    )

    assert result.automation_available is False
    assert result.source == "deterministic-fallback"


def test_production_automation_requires_https_and_paired_secret() -> None:
    base = {
        "environment": "production",
        "database_url": "postgresql://sourceai:unique-password@db.example.com/cross_border",
        "jwt_secret": "unique-production-jwt-secret-that-is-long-enough",
        "cors_origins": "https://app.example.com",
        "frontend_url": "https://app.example.com",
        "secure_cookies": True,
        "mfa_encryption_key": "EnFxjaW8RPNIWnzKAp9uQz891m0RVLkLxn1QV9gaf0c=",
        "error_monitoring_dsn": "https://public@errors.example.com/1",
        "payment_proof_allowed_hosts": "proofs.example.com",
    }
    with pytest.raises(RuntimeError, match="Automation webhook URL and token"):
        Settings(
            **base,
            automation_webhook_url="https://n8n.example.com/webhook/sourceai",
            automation_webhook_token=None,
        ).validate_runtime_security()
    with pytest.raises(RuntimeError, match="must use HTTPS"):
        Settings(
            **base,
            automation_webhook_url="http://n8n.example.com/webhook/sourceai",
            automation_webhook_token="secret",
        ).validate_runtime_security()


def test_bulk_quote_context_forces_human_review_risk() -> None:
    context = automation.quote_automation_context(
        {
            "offers_top": [{"seller": "Supplier", "rating": "4.5"}],
            "breakdown": {"total_bdt": "12000.00"},
            "eta": {"min_days": 15, "max_days": 20},
        },
        country_code="CN",
        mode="BULK",
    )
    fallback = automation.fallback_explanation(context)
    assert context["recommendations"][0]["risk_level"] == "Medium"
    assert fallback["human_review_required"] is True


def test_country_automation_context_is_bounded() -> None:
    recommendation = {
        "product": {"name": "Webcam", "variant_id": 139},
        "priority": "balanced",
        "qty": 10,
        "recommendations": [
            {
                "rank": index + 1,
                "country": {"code": code, "name": code},
                "mode": "LOCAL",
                "score": "80",
                "estimated_total_bdt": "12000",
                "eta": {"min_days": 10, "max_days": 15},
                "risk_level": "Low",
                "advantages": ["a", "b", "c", "ignored"],
                "weaknesses": [],
                "selected_offer": {"seller_name": f"Supplier {code}", "private": "discard"},
                "large_unused_field": "discard",
            }
            for index, code in enumerate(["CN", "MY", "SG", "TH"])
        ],
        "data_gaps": ["gap"] * 10,
    }

    context = automation.country_automation_context(recommendation)

    assert len(context["recommendations"]) == 3
    assert len(context["recommendations"][0]["advantages"]) == 3
    assert context["recommendations"][0]["supplier"] == "Supplier CN"
    assert "large_unused_field" not in context["recommendations"][0]
    assert len(context["data_gaps"]) == 5
