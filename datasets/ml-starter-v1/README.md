# SourceAI ML starter datasets v1

This directory contains reproducible, PII-free datasets for learning and prototyping.
It does **not** contain observed marketplace outcomes and must not support production AI-accuracy claims.

## Files

- `catalog_bootstrap.csv` — 610 static product/variant feature rows for clustering and exploratory price work.
- `category_text_classification.csv` — 610 product-name/model examples with catalog taxonomy labels.
- `offer_price_regression.csv` — 560 seed-derived offer examples with formula-generated price targets.
- `product_countries.csv` — normalized product-to-origin relationships.
- `product_monthly_trends_synthetic.csv` — 23,790 simulated monthly examples for next-month demand/GMV/trend tutorials.
- `real_sourcing_outcomes_template.csv` — header-only contract for collecting genuine quote/order/delivery outcomes.
- `data_dictionary.csv` — field roles, provenance, and leakage guidance.
- `manifest.json` — source hashes, file hashes, row counts, and safety disclosures.

## What can be trained now

1. Category text classification using `product_name` and `model`.
2. Tutorial offer-price regression. Do not call it a live-market price model: its target is formula-generated.
3. Tutorial next-month quantity/GMV regression or `UP`/`DOWN`/`STABLE` classification using the synthetic trend table.
4. Product similarity or clustering with the static catalog features.

## Split rules

- Static/category/offer files use a category-stratified product-group split. A product never crosses splits.
- The synthetic trend file uses chronological splits. `purge` rows create a one-month gap and must not be trained on.
- Fit encoders, imputers, and scalers on `train` only.

## Critical limitations

- Every row is seed-derived or simulated; `is_synthetic=1` is intentional.
- Snapshot risk and delivery fields were excluded as targets because risk is one class and delivery is constant.
- Snapshot heuristic score was excluded because it is an arithmetic formula, often above 100, and would create circular leakage.
- Product names may contain category words, so category classification can overestimate real-world generalization.
- The trend series is deterministic simulation, not historical demand. It is useful for pipeline practice only.
- Never mix these pseudo labels with a future observed test set.

## Generate and validate

From the repository root:

```powershell
python services/catalog-service/scripts/export_ml_starter_datasets.py
python services/catalog-service/scripts/export_ml_starter_datasets.py --check
```

For a real model, populate the outcome template from event-time snapshots after the observation window closes.
Do not export names, emails, phones, addresses, payment transaction IDs, screenshots, tokens, or support free text.
