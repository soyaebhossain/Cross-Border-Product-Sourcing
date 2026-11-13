from __future__ import annotations

from decimal import Decimal

from app.services import automation
from scripts.evaluate_explanations import score_explanation, summarize


def _context(language: str = "en", pricing_status: str = "verified", risk: str = "Low") -> dict:
    return {
        "response_language": language,
        "pricing_status": pricing_status,
        "recommendations": [
            {
                "country": {"code": "CN", "name": "China"},
                "risk_level": risk,
                "advantages": ["lowest landed cost"],
                "weaknesses": [],
                "estimated_total_bdt": "12077.45",
                "eta": {"min_days": 7, "max_days": 12},
                "selected_offer": {"seller": "Lamp Works", "price_origin": "15.38", "rating": "4.6"},
            }
        ],
        "data_gaps": ["Carrier quote is not live"],
    }


def _model_answer(**overrides) -> dict:
    answer = {
        "summary": "China is the best option at BDT 12,077.45 with delivery in 7 to 12 days.",
        "language": "en",
        "advantages": ["Lowest landed cost"],
        "risks": [],
        "missing_information": [],
        "recommended_checks": ["Confirm the HS code"],
        "confidence": 0.7,
        "human_review_required": False,
    }
    answer.update(overrides)
    return answer


def test_numbers_from_the_data_are_accepted_including_rounded_forms() -> None:
    allowed = automation.supported_numbers(_context())

    assert automation.unsupported_numbers("Total BDT 12,077.45, delivery 7-12 days, rating 4.6.", allowed) == []
    assert automation.unsupported_numbers("About BDT 12,077 or 12,077.5 landed.", allowed) == []
    assert Decimal("12077.45") in allowed


def test_invented_numbers_are_reported() -> None:
    allowed = automation.supported_numbers(_context())

    assert automation.unsupported_numbers("Total BDT 9,500 with a 15% discount in 3 days.", allowed) == ["9,500", "15", "3"]


def test_bangla_digits_are_checked_too() -> None:
    allowed = automation.supported_numbers(_context("bn"))

    assert automation.unsupported_numbers("মোট খরচ ১২,০৭৭.৪৫ টাকা, ৭ থেকে ১২ দিনে পৌঁছাবে।", allowed) == []
    assert automation.unsupported_numbers("মোট খরচ ৯,৫০০ টাকা।", allowed) == ["9,500"]


def test_summary_with_an_invented_figure_is_replaced_by_the_deterministic_one() -> None:
    context = _context()
    fallback = automation.fallback_explanation(context)

    explanation, unsupported = automation.check_explanation(
        _model_answer(summary="China is cheapest at BDT 9,500, saving you 21%."),
        fallback,
        language="en",
        source=context,
    )

    assert unsupported == ("9,500", "21")
    assert explanation["summary"] == fallback["summary"]
    assert "9,500" not in explanation["summary"]
    assert explanation["human_review_required"] is True


def test_only_the_list_items_with_invented_figures_are_removed() -> None:
    context = _context()
    explanation, unsupported = automation.check_explanation(
        _model_answer(
            advantages=["Lowest landed cost at BDT 12,077.45", "Supplier ships within 2 days"],
            risks=["Customs duty may rise to 35%"],
        ),
        automation.fallback_explanation(context),
        language="en",
        source=context,
    )

    assert explanation["advantages"] == ["Lowest landed cost at BDT 12,077.45"]
    assert explanation["risks"] == []
    assert set(unsupported) == {"2", "35"}
    assert explanation["summary"].startswith("China is the best option")


def test_grounded_answer_passes_unchanged_and_without_source_nothing_is_checked() -> None:
    context = _context()
    fallback = automation.fallback_explanation(context)

    explanation, unsupported = automation.check_explanation(_model_answer(), fallback, language="en", source=context)
    assert unsupported == ()
    assert explanation["summary"] == _model_answer()["summary"]
    assert explanation["human_review_required"] is False

    unchecked = automation.validated_explanation(_model_answer(summary="Total BDT 9,500."), fallback, language="en")
    assert unchecked["summary"] == "Total BDT 9,500."


def test_evaluation_scores_each_failure_mode() -> None:
    context = _context(pricing_status="indicative", risk="Medium")

    good = score_explanation(
        _model_answer(
            summary="China is the best option at BDT 12,077.45. Prices are indicative and must be re-verified.",
            human_review_required=True,
        ),
        context,
        "en",
    )
    assert (good["unsupported_numbers"], good["wrong_language_statements"]) == (0, 0)
    assert good["price_caveat_present"] is True and good["review_flag_correct"] is True

    bad = score_explanation(
        _model_answer(summary="China costs BDT 9,500.", advantages=["সর্বনিম্ন খরচ"], human_review_required=False),
        context,
        "en",
    )
    assert bad["unsupported_numbers"] == 1 and bad["unsupported_number_examples"] == ["9,500"]
    assert bad["wrong_language_statements"] == 1
    assert bad["price_caveat_present"] is False and bad["review_flag_correct"] is False


def test_evaluation_summary_reports_rates_over_model_answers_only() -> None:
    base = {"statements": 4, "wrong_language_statements": 0, "price_caveat_required": True, "price_caveat_present": True,
            "review_required": True, "review_flag_correct": True}
    rows = [
        {**base, "source": "claude-api", "unsupported_numbers": 0},
        {**base, "source": "claude-api", "unsupported_numbers": 2, "price_caveat_present": False},
        {**base, "source": "deterministic-fallback", "unsupported_numbers": 0},
    ]

    summary = summarize(rows)

    assert (summary["cases"], summary["model_answers"], summary["fallback_cases"]) == (3, 2, 1)
    assert summary["answers_with_unsupported_numbers_percent"] == 50.0
    assert summary["unsupported_numbers_total"] == 2
    assert summary["price_caveat_missing_percent"] == 50.0
    assert summary["review_flag_missing_percent"] == 0.0
