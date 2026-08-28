from __future__ import annotations

from decimal import Decimal

from app.models import AIDecisionExplanation, SavedQuote
from app.serializers import serialize_saved_quote


def _saved_quote(*, ai_explanation: AIDecisionExplanation | None = None) -> SavedQuote:
    quote = SavedQuote(
        id=17,
        user_id=4,
        variant_id=30,
        product_name="Lightweight Manual Wheelchair",
        variant_name="Standard",
        country_code="CN",
        mode="LOCAL",
        delivery_type="DOOR",
        qty=1,
        response={"breakdown": {"total_bdt": "8684.51"}, "status": "requested"},
        status="requested",
    )
    quote.orders = []
    quote.ai_explanation = ai_explanation
    return quote


def test_saved_quote_serialization_includes_linked_ollama_explanation_and_metadata() -> None:
    stored = AIDecisionExplanation(
        provider="ollama-via-n8n",
        model="qwen3:1.7b",
        prompt_version="quote-v1",
        deterministic_snapshot={"recommendations": []},
        explanation={
            "summary_bn": "China is the recommended route.",
            "advantages": ["Lower landed cost"],
            "risks": ["Verify the supplier"],
            "missing_information": [],
            "recommended_checks": ["Confirm the carrier quote"],
            "confidence": 0.82,
            "human_review_required": False,
        },
        confidence=Decimal("0.8200"),
        human_review_required=False,
        review_status="NOT_REQUIRED",
    )
    quote = _saved_quote(ai_explanation=stored)

    payload = serialize_saved_quote(quote)

    assert payload["response"]["ai_explanation"] == stored.explanation
    assert payload["response"]["ai_metadata"] == {
        "source": "ollama-via-n8n",
        "model": "qwen3:1.7b",
        "prompt_version": "quote-v1",
        "automation_available": True,
        "monetary_calculations_are_deterministic": True,
    }
    assert "ai_explanation" not in quote.response
    assert "ai_metadata" not in quote.response


def test_saved_quote_serialization_preserves_fallback_metadata_and_missing_confidence() -> None:
    stored = AIDecisionExplanation(
        provider="deterministic-fallback",
        model=None,
        prompt_version="quote-v1",
        deterministic_snapshot={"recommendations": []},
        explanation={"summary_bn": "Deterministic explanation", "advantages": [], "risks": []},
        confidence=None,
        human_review_required=True,
        review_status="PENDING",
    )

    payload = serialize_saved_quote(_saved_quote(ai_explanation=stored))

    assert payload["response"]["ai_explanation"]["confidence"] is None
    assert payload["response"]["ai_explanation"]["human_review_required"] is True
    assert payload["response"]["ai_metadata"]["source"] == "deterministic-fallback"
    assert payload["response"]["ai_metadata"]["automation_available"] is False


def test_saved_quote_without_linked_explanation_keeps_existing_response_contract() -> None:
    quote = _saved_quote()

    payload = serialize_saved_quote(quote)

    assert payload["response"] == quote.response
    assert "ai_explanation" not in payload["response"]
    assert "ai_metadata" not in payload["response"]
