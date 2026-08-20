from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from scripts.export_ml_starter_datasets import DEFAULT_OUTPUT, build_dataset_pack, check_dataset_pack


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_committed_ml_dataset_pack_is_current_and_safe() -> None:
    manifest = check_dataset_pack(DEFAULT_OUTPUT)

    assert manifest["training_readiness"] == "tutorial_only"
    assert manifest["contains_pii"] is False
    assert manifest["contains_observed_outcomes"] is False
    assert manifest["files"]["catalog_bootstrap.csv"]["rows"] == 610
    assert manifest["files"]["category_text_classification.csv"]["rows"] == 610
    assert manifest["files"]["offer_price_regression.csv"]["rows"] == 560
    assert manifest["files"]["product_monthly_trends_synthetic.csv"]["rows"] == 23_790
    assert manifest["files"]["real_sourcing_outcomes_template.csv"]["rows"] == 0


def test_ml_dataset_export_is_byte_reproducible(tmp_path: Path) -> None:
    generated = tmp_path / "ml-starter-v1"
    build_dataset_pack(generated)

    expected_names = sorted(path.name for path in DEFAULT_OUTPUT.iterdir() if path.is_file())
    generated_names = sorted(path.name for path in generated.iterdir() if path.is_file())
    assert generated_names == expected_names
    for filename in expected_names:
        assert (generated / filename).read_bytes() == (DEFAULT_OUTPUT / filename).read_bytes()


def test_product_groups_do_not_cross_static_splits() -> None:
    category_rows = _rows(DEFAULT_OUTPUT / "category_text_classification.csv")
    split_by_product: dict[str, set[str]] = defaultdict(set)
    for row in category_rows:
        split_by_product[row["product_id"]].add(row["split"])

    assert len(split_by_product) == 610
    assert all(len(splits) == 1 for splits in split_by_product.values())
    assert {row["split"] for row in category_rows} == {"train", "validation", "test"}


def test_synthetic_trends_are_chronological_and_multi_class() -> None:
    trend_rows = _rows(DEFAULT_OUTPUT / "product_monthly_trends_synthetic.csv")
    labels = Counter(row["target_next_month_trend"] for row in trend_rows if row["split"] != "purge")
    target_months: dict[str, set[str]] = defaultdict(set)
    for row in trend_rows:
        target_months[row["split"]].add(row["target_period_start"])
        assert row["feature_period_start"] < row["target_period_start"]
        assert int(row["order_count"]) <= int(row["saved_quotes"]) <= int(row["quote_requests"])
        assert int(row["cancelled_orders"]) + int(row["delivered_orders"]) == int(row["order_count"])

    assert set(labels) == {"UP", "DOWN", "STABLE"}
    assert min(labels.values()) >= 500
    assert max(target_months["train"]) < min(target_months["validation"])
    assert max(target_months["validation"]) < min(target_months["test"])


def test_outcome_contract_contains_no_direct_customer_pii_fields() -> None:
    with (DEFAULT_OUTPUT / "real_sourcing_outcomes_template.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        header = next(csv.reader(handle))

    forbidden = {
        "name",
        "email",
        "phone",
        "address",
        "password",
        "token",
        "transaction_id",
        "screenshot_url",
        "support_note",
    }
    assert forbidden.isdisjoint(header)
