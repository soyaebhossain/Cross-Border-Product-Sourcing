from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.services.ai_insights import build_ai_insights


def test_checked_in_ml_starter_dataset_is_executable_and_discloses_provenance() -> None:
    result = build_ai_insights("iPhone")

    assert result["available"] is True
    assert result["status"] == "tutorial_data"
    assert result["dataset"]["name"] == "ml-starter-v1"
    assert result["dataset"]["training_readiness"] == "tutorial_only"
    assert result["dataset"]["contains_observed_outcomes"] is False
    assert result["dataset"]["is_synthetic"] is True
    assert result["sales"]["matched_rows"] >= 1
    assert "synthetic" in result["methodology"].lower()
    assert "tutorial-only" in result["recommendations"][0].lower()


def test_missing_ai_dataset_returns_an_explicit_unavailable_state(
    tmp_path: Path,
) -> None:
    result = build_ai_insights("phone", data_dir=tmp_path)

    assert result["available"] is False
    assert result["status"] == "unavailable"
    assert result["recommendations"] == []
    assert set(result["missing_files"]) == {
        "manifest.json",
        "catalog_bootstrap.csv",
        "product_monthly_trends_synthetic.csv",
    }
    assert str(tmp_path) not in result["reason"]


def test_production_rejects_an_unusable_ai_dataset_path(tmp_path: Path) -> None:
    settings = Settings(
        environment="production",
        ai_insights_data_path=str(tmp_path),
    )

    with pytest.raises(RuntimeError, match="CATALOG_AI_INSIGHTS_DATA_PATH"):
        settings.validate_runtime_security()
