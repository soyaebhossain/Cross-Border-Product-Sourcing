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
        Settings(database_url="sqlite://"),
    )

    assert result.automation_available is False
    assert result.source == "deterministic-fallback"
    assert result.explanation["human_review_required"] is True
    assert result.explanation["confidence"] is None
    assert "China" in result.explanation["summary_bn"]


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
        Settings(**base, automation_webhook_url="https://n8n.example.com/webhook/sourceai").validate_runtime_security()
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
