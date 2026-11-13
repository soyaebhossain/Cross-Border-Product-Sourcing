"""Measure how often the explanation model states something the data does not support.

For a sample of real catalog quotes this asks the configured model for an
explanation and scores the raw answer, before the server's validation removes
anything:

- unsupported numbers: figures that are not in the server-calculated quote
- wrong language: text not in the requested language
- missing price caveat: an indicative quote not described as needing re-verification
- missing review flag: a risky or indicative quote not marked for human review

Each model call is billed by the provider. Run from services/catalog-service:

    python -m scripts.evaluate_explanations --sample 50 --language both --output evaluation-results

With no model configured every case is a deterministic fallback and the report says so.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Country, SellerOffer
from app.schemas import QuoteRequestIn
from app.services.automation import (
    FALLBACK_SOURCE,
    _matches_explanation_language,
    explain_recommendation,
    quote_automation_context,
    supported_numbers,
    unsupported_numbers,
)
from app.services.sourcing import build_quote

TEXT_FIELDS = ("advantages", "risks", "missing_information", "recommended_checks")
PRICE_CAVEAT_WORDS = ("indicative", "re-verif", "reverif", "verify", "আনুমানিক", "যাচাই")


def explanation_texts(explanation: dict[str, Any]) -> list[str]:
    texts = [str(explanation.get("summary") or "")]
    for field in TEXT_FIELDS:
        value = explanation.get(field)
        if isinstance(value, list):
            texts.extend(str(item) for item in value)
    return [text for text in texts if text.strip()]


def score_explanation(raw: dict[str, Any], context: dict[str, Any], language: str) -> dict[str, Any]:
    """Score one raw model answer against the data it was asked to explain."""

    texts = explanation_texts(raw)
    allowed = supported_numbers(context)
    invented = [number for text in texts for number in unsupported_numbers(text, allowed)]
    wrong_language = [text for text in texts if not _matches_explanation_language(text, language)]
    route = (context.get("recommendations") or [{}])[0]
    indicative = context.get("pricing_status") == "indicative"
    needs_review = indicative or str(route.get("risk_level") or "").lower() in {"medium", "high"}
    joined = " ".join(texts).lower()
    return {
        "statements": len(texts),
        "unsupported_numbers": len(invented),
        "unsupported_number_examples": invented[:5],
        "wrong_language_statements": len(wrong_language),
        "price_caveat_required": indicative,
        "price_caveat_present": (not indicative) or any(word in joined for word in PRICE_CAVEAT_WORDS),
        "review_required": needs_review,
        "review_flag_correct": (not needs_review) or raw.get("human_review_required") is True,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [row for row in rows if row["source"] != FALLBACK_SOURCE]

    def rate(count: int, total: int) -> float | None:
        return round(count / total * 100, 2) if total else None

    statements = sum(row["statements"] for row in scored)
    caveat_cases = [row for row in scored if row["price_caveat_required"]]
    review_cases = [row for row in scored if row["review_required"]]
    return {
        "cases": len(rows),
        "model_answers": len(scored),
        "fallback_cases": len(rows) - len(scored),
        "statements": statements,
        "answers_with_unsupported_numbers": sum(1 for row in scored if row["unsupported_numbers"]),
        "answers_with_unsupported_numbers_percent": rate(sum(1 for row in scored if row["unsupported_numbers"]), len(scored)),
        "unsupported_numbers_total": sum(row["unsupported_numbers"] for row in scored),
        "wrong_language_statement_percent": rate(sum(row["wrong_language_statements"] for row in scored), statements),
        "price_caveat_missing_percent": rate(sum(1 for row in caveat_cases if not row["price_caveat_present"]), len(caveat_cases)),
        "review_flag_missing_percent": rate(sum(1 for row in review_cases if not row["review_flag_correct"]), len(review_cases)),
    }


def sample_cases(session, sample: int) -> list[tuple[int, str]]:
    """Evenly spaced (variant id, country code) pairs with an active air-freight offer."""

    pairs = session.execute(
        select(SellerOffer.variant_id, Country.code)
        .join(Country, Country.id == SellerOffer.country_id)
        .where(SellerOffer.is_active.is_(True), SellerOffer.mode == "LOCAL")
        .order_by(SellerOffer.variant_id, Country.code)
    ).all()
    unique = list(dict.fromkeys((int(variant_id), str(code)) for variant_id, code in pairs))
    if len(unique) <= sample:
        return unique
    step = len(unique) / sample
    return [unique[int(index * step)] for index in range(sample)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, default=50, help="Number of quotes per language (default 50).")
    parser.add_argument("--language", choices=("en", "bn", "both"), default="both")
    parser.add_argument("--output", type=Path, default=Path("evaluation-results"))
    args = parser.parse_args()

    settings = get_settings()
    languages = ("en", "bn") if args.language == "both" else (args.language,)
    rows: list[dict[str, Any]] = []
    with SessionLocal() as session:
        cases = sample_cases(session, max(1, args.sample))
        print(f"Evaluating {len(cases)} quotes x {len(languages)} language(s); each model answer is a billed request.")
        for variant_id, country in cases:
            try:
                quote = build_quote(
                    session,
                    QuoteRequestIn(variant_id=variant_id, country=country, mode="LOCAL", qty=10, delivery_type="DOOR"),
                )
            except HTTPException:
                continue
            for language in languages:
                context = quote_automation_context(quote, country_code=country, mode="LOCAL", language=language)
                result = explain_recommendation(context, settings)
                row: dict[str, Any] = {
                    "variant_id": variant_id,
                    "country": country,
                    "language": language,
                    "source": result.source,
                    "model": result.model,
                    "statements": 0,
                    "unsupported_numbers": 0,
                    "unsupported_number_examples": [],
                    "wrong_language_statements": 0,
                    "price_caveat_required": context.get("pricing_status") == "indicative",
                    "price_caveat_present": True,
                    "review_required": False,
                    "review_flag_correct": True,
                }
                if result.raw_explanation is not None:
                    row.update(score_explanation(result.raw_explanation, context, language))
                rows.append(row)

    summary = summarize(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    (args.output / f"explanation-evaluation-{stamp}.json").write_text(
        json.dumps({"generated_at": stamp, "summary": summary, "cases": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with (args.output / f"explanation-evaluation-{stamp}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else ["variant_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "unsupported_number_examples": " ".join(row["unsupported_number_examples"])})
    print(json.dumps(summary, indent=2))
    if not summary["model_answers"]:
        print("No model answered: every case used the deterministic fallback. Configure the model and its credit, then rerun.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
