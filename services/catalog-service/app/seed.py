from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import (
    Category,
    Country,
    CurrencyRate,
    DutyRule,
    ETARule,
    Product,
    ProductVariant,
    Seller,
    SellerOffer,
    ServiceFeeRule,
    ShippingRateCard,
)

_GENERAL_GOODS_MANIFEST_PATH = (
    Path(__file__).resolve().parent / "seed_data" / "general_goods_v1.json"
)
_PUBLIC_CATALOG_SNAPSHOT_FILENAME = "public-catalog.snapshot.json"
_PUBLIC_CATALOG_EXPECTED_COUNTS = {
    "categories": 27,
    "countries": 7,
    "products": 610,
    "variants": 610,
}
_OWNED_PRODUCT_IMAGE_PATTERN = re.compile(
    r"^products/(?:[A-Za-z0-9][A-Za-z0-9_-]*/)*"
    r"[A-Za-z0-9][A-Za-z0-9._-]*\.(?:avif|gif|jpe?g|png|webp)$",
    re.IGNORECASE,
)


def _resolve_public_catalog_snapshot_path(explicit_path: Path | None = None) -> Path:
    if explicit_path is not None:
        path = Path(explicit_path)
        if path.is_file():
            return path
        raise RuntimeError(f"Public catalog seed snapshot is missing: {path}")

    service_root = Path(__file__).resolve().parent.parent
    candidates = [
        service_root.parent.parent
        / "apps"
        / "web-next"
        / "data"
        / _PUBLIC_CATALOG_SNAPSHOT_FILENAME,
        Path(__file__).resolve().parent
        / "seed_data"
        / _PUBLIC_CATALOG_SNAPSHOT_FILENAME,
    ]
    for path in candidates:
        if path.is_file():
            return path
    searched = ", ".join(str(path) for path in candidates)
    raise RuntimeError(
        "Public catalog seed snapshot is unavailable. "
        f"Expected {_PUBLIC_CATALOG_SNAPSHOT_FILENAME} at one of: {searched}"
    )


def _snapshot_required_text(value: Any, label: str, *, max_length: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Public catalog snapshot {label} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise RuntimeError(
            f"Public catalog snapshot {label} exceeds {max_length} characters"
        )
    return normalized


def _snapshot_positive_decimal(value: Any, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise RuntimeError(
            f"Public catalog snapshot {label} must be numeric"
        ) from exc
    if not parsed.is_finite() or parsed <= 0:
        raise RuntimeError(f"Public catalog snapshot {label} must be greater than zero")
    return parsed


def _snapshot_owned_image_path(value: Any, label: str) -> str | None:
    if value in (None, ""):
        return None
    public_path = _snapshot_required_text(value, label, max_length=507)
    if not public_path.startswith("/media/"):
        raise RuntimeError(
            f"Public catalog snapshot {label} must be an owned /media/ path"
        )
    owned_path = _owned_product_image_path(public_path.removeprefix("/media/"), label)
    if owned_path is None:
        return None
    media_file = Path(__file__).resolve().parent.parent / "media" / owned_path
    if not media_file.is_file():
        raise RuntimeError(
            f"Public catalog snapshot {label} points to missing media: {public_path}"
        )
    return owned_path


def _load_public_catalog_snapshot(path: Path | None = None) -> dict[str, Any]:
    snapshot_path = _resolve_public_catalog_snapshot_path(path)
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Public catalog seed snapshot is unreadable: {snapshot_path}"
        ) from exc
    if not isinstance(snapshot, dict):
        raise RuntimeError("Public catalog snapshot root must be an object")
    if snapshot.get("schema_version") != 2:
        raise RuntimeError("Public catalog snapshot schema_version must be 2")

    categories = snapshot.get("categories")
    countries = snapshot.get("countries")
    products = snapshot.get("products")
    counts = snapshot.get("counts")
    if not isinstance(categories, list) or not isinstance(countries, list) or not isinstance(products, list):
        raise RuntimeError(
            "Public catalog snapshot categories, countries and products must be arrays"
        )
    if not isinstance(counts, dict):
        raise RuntimeError("Public catalog snapshot counts must be an object")

    category_slugs: set[str] = set()
    category_ids: set[int] = set()
    for index, category in enumerate(categories):
        if not isinstance(category, dict):
            raise RuntimeError(f"Public catalog snapshot category #{index + 1} must be an object")
        category_id = category.get("id")
        if not isinstance(category_id, int) or category_id <= 0 or category_id in category_ids:
            raise RuntimeError("Public catalog snapshot category IDs must be unique positive integers")
        category_ids.add(category_id)
        _snapshot_required_text(category.get("name"), f"category #{category_id} name", max_length=120)
        slug = _snapshot_required_text(category.get("slug"), f"category #{category_id} slug", max_length=120)
        normalized_slug = slug.casefold()
        if normalized_slug in category_slugs:
            raise RuntimeError("Public catalog snapshot category slugs must be case-insensitively unique")
        category_slugs.add(normalized_slug)

    country_codes: set[str] = set()
    country_ids: set[int] = set()
    for index, country in enumerate(countries):
        if not isinstance(country, dict):
            raise RuntimeError(f"Public catalog snapshot country #{index + 1} must be an object")
        country_id = country.get("id")
        if not isinstance(country_id, int) or country_id <= 0 or country_id in country_ids:
            raise RuntimeError("Public catalog snapshot country IDs must be unique positive integers")
        country_ids.add(country_id)
        code = _snapshot_required_text(country.get("code"), f"country #{country_id} code", max_length=2).upper()
        if len(code) != 2 or code in country_codes:
            raise RuntimeError("Public catalog snapshot country codes must be unique ISO alpha-2 values")
        country_codes.add(code)
        _snapshot_required_text(country.get("name"), f"country {code} name", max_length=80)

    product_slugs: set[str] = set()
    product_ids: set[int] = set()
    variant_ids: set[int] = set()
    variant_skus: set[str] = set()
    variant_count = 0
    for index, product in enumerate(products):
        if not isinstance(product, dict):
            raise RuntimeError(f"Public catalog snapshot product #{index + 1} must be an object")
        product_id = product.get("id")
        if not isinstance(product_id, int) or product_id <= 0 or product_id in product_ids:
            raise RuntimeError("Public catalog snapshot product IDs must be unique positive integers")
        product_ids.add(product_id)
        _snapshot_required_text(product.get("name"), f"product #{product_id} name", max_length=200)
        slug = _snapshot_required_text(product.get("slug"), f"product #{product_id} slug", max_length=200)
        normalized_slug = slug.casefold()
        if normalized_slug in product_slugs:
            raise RuntimeError("Public catalog snapshot product slugs must be case-insensitively unique")
        product_slugs.add(normalized_slug)
        model = product.get("model")
        if model not in (None, ""):
            _snapshot_required_text(model, f"product {slug} model", max_length=120)
        _snapshot_owned_image_path(product.get("image"), f"product {slug} image")

        category = product.get("category")
        if not isinstance(category, dict):
            raise RuntimeError(f"Public catalog snapshot product {slug} category must be an object")
        category_slug = _snapshot_required_text(
            category.get("slug"), f"product {slug} category slug", max_length=120
        )
        if category_slug.casefold() not in category_slugs:
            raise RuntimeError(
                f"Public catalog snapshot product {slug} references unknown category {category_slug}"
            )

        market = product.get("market")
        if not isinstance(market, dict):
            raise RuntimeError(f"Public catalog snapshot product {slug} market must be an object")
        eligible_countries = market.get("countries")
        if not isinstance(eligible_countries, list) or not eligible_countries:
            raise RuntimeError(
                f"Public catalog snapshot product {slug} must have eligible countries"
            )
        for code in eligible_countries:
            normalized_code = _snapshot_required_text(
                code, f"product {slug} country code", max_length=2
            ).upper()
            if normalized_code not in country_codes:
                raise RuntimeError(
                    f"Public catalog snapshot product {slug} references unknown country {normalized_code}"
                )
        currency = _snapshot_required_text(
            market.get("currency"), f"product {slug} currency", max_length=10
        ).upper()
        if currency != "USD":
            raise RuntimeError(
                f"Public catalog snapshot product {slug} must use the USD reference currency"
            )
        _snapshot_positive_decimal(market.get("min_price"), f"product {slug} minimum price")

        variants = product.get("variants")
        if not isinstance(variants, list) or not variants:
            raise RuntimeError(f"Public catalog snapshot product {slug} must have variants")
        local_variant_ids: set[int] = set()
        for variant_index, variant in enumerate(variants):
            if not isinstance(variant, dict):
                raise RuntimeError(
                    f"Public catalog snapshot product {slug} variant #{variant_index + 1} must be an object"
                )
            variant_id = variant.get("id")
            if not isinstance(variant_id, int) or variant_id <= 0 or variant_id in variant_ids:
                raise RuntimeError("Public catalog snapshot variant IDs must be unique positive integers")
            variant_ids.add(variant_id)
            local_variant_ids.add(variant_id)
            variant_count += 1
            sku = variant.get("sku")
            if sku not in (None, ""):
                normalized_sku = _snapshot_required_text(
                    sku, f"product {slug} variant SKU", max_length=80
                ).casefold()
                if normalized_sku in variant_skus:
                    raise RuntimeError(
                        "Public catalog snapshot non-empty variant SKUs must be case-insensitively unique"
                    )
                variant_skus.add(normalized_sku)
            variant_name = variant.get("variant_name")
            if variant_name not in (None, ""):
                _snapshot_required_text(
                    variant_name, f"product {slug} variant name", max_length=120
                )
            for field in ("weight_kg", "length_cm", "width_cm", "height_cm"):
                _snapshot_positive_decimal(
                    variant.get(field), f"product {slug} variant {field}"
                )
        if product.get("default_variant_id") not in local_variant_ids:
            raise RuntimeError(
                f"Public catalog snapshot product {slug} default variant is invalid"
            )

    actual_counts = {
        "categories": len(categories),
        "countries": len(countries),
        "products": len(products),
        "variants": variant_count,
    }
    if counts != actual_counts:
        raise RuntimeError(
            f"Public catalog snapshot counts are inconsistent: declared {counts}, actual {actual_counts}"
        )
    if actual_counts != _PUBLIC_CATALOG_EXPECTED_COUNTS:
        raise RuntimeError(
            "Public catalog snapshot must contain the canonical launch catalog: "
            f"expected {_PUBLIC_CATALOG_EXPECTED_COUNTS}, got {actual_counts}"
        )
    return snapshot


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "item"


def _decimal_from_row(row: dict[str, str], key: str, default: str = "0") -> Decimal:
    try:
        return Decimal(str(row.get(key) or default))
    except Exception:
        return Decimal(default)


def _int_from_row(row: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(Decimal(str(row.get(key) or default)))
    except Exception:
        return default


def _positive_manifest_decimal(value: Any, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise RuntimeError(f"{label} must be a decimal number") from exc
    if parsed <= 0:
        raise RuntimeError(f"{label} must be greater than zero")
    return parsed


def _nonnegative_manifest_decimal(value: Any, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise RuntimeError(f"{label} must be a decimal number") from exc
    if parsed < 0:
        raise RuntimeError(f"{label} must not be negative")
    return parsed


def _owned_product_image_path(value: Any, label: str) -> str | None:
    """Return the canonical database value for an owned product asset.

    Seed manifests are intentionally limited to project-owned media. Remote
    hotlinks are mutable, can leak visitor requests to third parties, and make
    deterministic public snapshots impossible.
    """
    if value is None:
        return None
    normalized = str(value).strip().replace("\\", "/").lstrip("/")
    if normalized.startswith("media/"):
        normalized = normalized.removeprefix("media/")
    if not normalized:
        return None
    if len(normalized) > 500 or not _OWNED_PRODUCT_IMAGE_PATTERN.fullmatch(normalized):
        raise RuntimeError(
            f"{label} must be an owned relative product image path such as "
            "products/example.webp"
        )
    return normalized


def _merge_seed_image(current: str | None, proposed: str | None) -> str | None:
    """Fill an empty image without overwriting an operator-managed value."""
    if current and current.strip():
        return current
    return proposed


def _load_general_goods_manifest(path: Path | None = None) -> dict[str, Any]:
    manifest_path = path or _GENERAL_GOODS_MANIFEST_PATH
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load general-goods seed manifest: {manifest_path}") from exc

    if not isinstance(manifest, dict) or not str(manifest.get("catalog_revision") or "").strip():
        raise RuntimeError("General-goods manifest requires a catalog_revision")

    new_origins = manifest.get("new_origins")
    supplier_profiles = manifest.get("supplier_profiles")
    offer_strategy = manifest.get("offer_strategy")
    categories = manifest.get("categories")
    if not isinstance(new_origins, list) or not isinstance(supplier_profiles, list):
        raise RuntimeError("General-goods manifest requires origin and supplier profile lists")
    if not isinstance(offer_strategy, list) or len(offer_strategy) != 4:
        raise RuntimeError("General-goods manifest requires exactly four offer strategies")
    if not isinstance(categories, list):
        raise RuntimeError("General-goods manifest requires a category list")

    base_origin_codes = {"CN", "IN", "SG", "TH"}
    new_origin_codes: set[str] = set()
    for origin in new_origins:
        code = str(origin.get("code") or "").upper()
        if (
            not re.fullmatch(r"[A-Z]{2}", code)
            or code in base_origin_codes
            or code in new_origin_codes
        ):
            raise RuntimeError(f"Invalid or duplicate new origin code: {code}")
        new_origin_codes.add(code)
        if not str(origin.get("name") or "").strip():
            raise RuntimeError(f"Origin {code} requires a name")

        shipping_rates = origin.get("shipping_rates")
        eta_rules = origin.get("eta_rules")
        if not isinstance(shipping_rates, list) or len(shipping_rates) != 4:
            raise RuntimeError(f"Origin {code} requires four lightweight shipping bands")
        shipping_keys: set[tuple[str, str, str]] = set()
        for rate in shipping_rates:
            method = str(rate.get("method") or "").upper()
            minimum = _nonnegative_manifest_decimal(
                rate.get("min_kg"),
                f"{code} shipping min_kg",
            )
            maximum = _positive_manifest_decimal(
                rate.get("max_kg"),
                f"{code} shipping max_kg",
            )
            if method not in {"AIR", "SEA"}:
                raise RuntimeError(f"Origin {code} has an unsupported shipping method")
            if maximum < minimum:
                raise RuntimeError(f"Origin {code} has an invalid shipping range")
            _positive_manifest_decimal(rate.get("cost_bdt"), f"{code} shipping cost")
            shipping_keys.add((method, str(minimum), str(maximum)))
        if len(shipping_keys) != 4 or {item[0] for item in shipping_keys} != {"AIR", "SEA"}:
            raise RuntimeError(f"Origin {code} shipping bands must be unique and cover AIR and SEA")

        if not isinstance(eta_rules, list) or len(eta_rules) != 4:
            raise RuntimeError(f"Origin {code} requires four ETA rules")
        eta_keys: set[tuple[str, str]] = set()
        for rule in eta_rules:
            mode = str(rule.get("mode") or "").upper()
            delivery_type = str(rule.get("delivery_type") or "").upper()
            min_days = int(rule.get("min_days") or 0)
            max_days = int(rule.get("max_days") or 0)
            if mode not in {"LOCAL", "BULK"} or delivery_type not in {"DOOR", "PICKUP"}:
                raise RuntimeError(f"Origin {code} has an unsupported ETA rule")
            if min_days < 1 or max_days < min_days:
                raise RuntimeError(f"Origin {code} has an invalid ETA range")
            eta_keys.add((mode, delivery_type))
        expected_eta_keys = {
            ("LOCAL", "DOOR"),
            ("LOCAL", "PICKUP"),
            ("BULK", "DOOR"),
            ("BULK", "PICKUP"),
        }
        if eta_keys != expected_eta_keys:
            raise RuntimeError(f"Origin {code} ETA rules must cover every mode and delivery type")

    supplier_codes: set[str] = set()
    for profile in supplier_profiles:
        code = str(profile.get("country_code") or "").upper()
        if not re.fullmatch(r"[A-Z]{2}", code) or code in supplier_codes:
            raise RuntimeError(f"Invalid or duplicate supplier country profile: {code}")
        supplier_codes.add(code)
        if not str(profile.get("name") or "").strip():
            raise RuntimeError(f"Supplier profile {code} requires a name")
        rating = _positive_manifest_decimal(profile.get("rating"), f"{code} supplier rating")
        if rating > Decimal("5"):
            raise RuntimeError(f"Supplier profile {code} rating must not exceed five")

    known_country_codes = base_origin_codes | new_origin_codes
    unsupported_supplier_codes = supplier_codes - known_country_codes
    if unsupported_supplier_codes:
        raise RuntimeError(
            "Supplier profiles reference unsupported origins: "
            + ", ".join(sorted(unsupported_supplier_codes))
        )

    offer_keys: set[tuple[int, str]] = set()
    for strategy in offer_strategy:
        origin_index = int(strategy.get("origin_index", -1))
        mode = str(strategy.get("mode") or "").upper()
        if origin_index not in {0, 1, 2} or mode not in {"LOCAL", "BULK"}:
            raise RuntimeError("Offer strategy has an invalid origin index or mode")
        key = (origin_index, mode)
        if key in offer_keys:
            raise RuntimeError("Offer strategies must use unique origin/mode pairs")
        offer_keys.add(key)
        _positive_manifest_decimal(strategy.get("price_multiplier"), "Offer price multiplier")
        stock = int(strategy.get("stock") or 0)
        moq = int(strategy.get("moq") or 0)
        if stock < 1 or moq < 1 or stock < moq:
            raise RuntimeError("Offer strategy stock and MOQ must be positive and compatible")

    expected_category_count = int(manifest.get("expected_category_count") or 0)
    expected_product_count = int(manifest.get("expected_product_count") or 0)
    if len(categories) != expected_category_count:
        raise RuntimeError("General-goods manifest category count does not match its expectation")

    category_codes: set[str] = set()
    category_slugs: set[str] = set()
    product_slugs: set[str] = set()
    product_models: set[str] = set()
    product_skus: set[str] = set()
    total_products = 0
    for category in categories:
        code = str(category.get("code") or "").upper()
        slug = str(category.get("slug") or "")
        name = str(category.get("name") or "")
        products = category.get("products")
        if not re.fullmatch(r"[A-Z]{3}", code) or code in category_codes:
            raise RuntimeError(f"Invalid or duplicate category code: {code}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in category_slugs:
            raise RuntimeError(f"Invalid or duplicate category slug: {slug}")
        if not name.strip() or not isinstance(products, list):
            raise RuntimeError(f"Category {slug} requires a name and product list")
        expected_category_products = int(category.get("expected_product_count") or 0)
        if len(products) != expected_category_products:
            raise RuntimeError(f"Category {slug} product count does not match its expectation")
        category_codes.add(code)
        category_slugs.add(slug)

        for position, product in enumerate(products, start=1):
            product_slug = str(product.get("slug") or "")
            model = str(product.get("model") or "")
            sku = str(product.get("sku") or "")
            expected_model = f"{code}-{position:03d}"
            if not str(product.get("name") or "").strip():
                raise RuntimeError(f"Category {slug} has a product without a name")
            if (
                not product_slug.startswith(f"{slug}-")
                or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", product_slug)
                or product_slug in product_slugs
            ):
                raise RuntimeError(f"Invalid or duplicate product slug: {product_slug}")
            if model != expected_model or model in product_models:
                raise RuntimeError(f"Invalid or duplicate product model: {model}")
            if sku != f"{model}-STD" or sku in product_skus:
                raise RuntimeError(f"Invalid or duplicate product SKU: {sku}")
            _positive_manifest_decimal(product.get("base_price_usd"), f"{sku} base price")
            _positive_manifest_decimal(product.get("weight_kg"), f"{sku} weight")
            dimensions = product.get("dimensions_cm")
            if not isinstance(dimensions, list) or len(dimensions) != 3:
                raise RuntimeError(f"{sku} requires three package dimensions")
            for dimension in dimensions:
                _positive_manifest_decimal(dimension, f"{sku} package dimension")
            origins = product.get("origins")
            if (
                not isinstance(origins, list)
                or len(origins) != 3
                or len(set(origins)) != 3
                or any(origin not in known_country_codes for origin in origins)
                or any(origin not in supplier_codes for origin in origins)
            ):
                raise RuntimeError(f"{sku} requires three supported, unique origin codes")
            if not str(product.get("spec_caveat") or "").strip():
                raise RuntimeError(f"{sku} requires a specification caveat")
            _owned_product_image_path(product.get("image"), f"{sku} image")
            product_slugs.add(product_slug)
            product_models.add(model)
            product_skus.add(sku)
            total_products += 1

    if total_products != expected_product_count:
        raise RuntimeError("General-goods manifest product count does not match its expectation")
    return manifest


def _ensure_reference_data(
    session: Session,
    new_origins: list[dict[str, Any]] | None = None,
) -> dict[str, Country]:
    country_specs = [
        ("CN", "China"),
        ("SG", "Singapore"),
        ("TH", "Thailand"),
        ("IN", "India"),
    ]
    for origin in new_origins or []:
        country_specs.append((str(origin["code"]).upper(), str(origin["name"])))

    country_codes = [code for code, _name in country_specs]
    countries = {
        country.code: country
        for country in session.scalars(select(Country).where(Country.code.in_(country_codes))).all()
    }

    for code, name in country_specs:
        if code not in countries:
            countries[code] = Country(code=code, name=name)
            session.add(countries[code])

    session.flush()

    existing_rates = {
        rate.currency: rate
        for rate in session.scalars(select(CurrencyRate).where(CurrencyRate.currency.in_(["USD", "CNY", "SGD", "THB"]))).all()
    }
    for currency, amount in [("USD", "121.50"), ("CNY", "16.80"), ("SGD", "89.20"), ("THB", "3.35")]:
        if currency not in existing_rates:
            session.add(CurrencyRate(currency=currency, rate_to_bdt=Decimal(amount)))

    existing_fee_modes = {rule.mode for rule in session.scalars(select(ServiceFeeRule)).all()}
    if "LOCAL" not in existing_fee_modes:
        session.add(ServiceFeeRule(mode="LOCAL", fee_bdt=Decimal("450.00"), percent=Decimal("5.00")))
    if "BULK" not in existing_fee_modes:
        session.add(ServiceFeeRule(mode="BULK", fee_bdt=Decimal("1200.00"), percent=Decimal("3.50")))

    # Keep launch estimates explicit and operator-manageable.  The quote engine
    # intentionally refuses to invent a tariff when no active rule exists.
    # These country-wide defaults are reference estimates and can be replaced
    # with category-specific rules from the admin control centre.
    countries_with_global_duty = set(
        session.scalars(
            select(DutyRule.country_id).where(DutyRule.category_id.is_(None))
        ).all()
    )
    for country in countries.values():
        if country.id not in countries_with_global_duty:
            session.add(
                DutyRule(
                    country=country,
                    category_id=None,
                    percent=Decimal("5.00"),
                    fixed_bdt=Decimal("0.00"),
                )
            )

    shipping_cards = [
        ("CN", "AIR", "0.000", "0.999", "580.00"),
        ("CN", "AIR", "1.000", "4.999", "1450.00"),
        ("CN", "SEA", "0.000", "9.999", "980.00"),
        ("CN", "SEA", "10.000", "49.999", "2800.00"),
        ("SG", "AIR", "0.000", "0.999", "720.00"),
        ("SG", "AIR", "1.000", "4.999", "1680.00"),
        ("SG", "SEA", "0.000", "9.999", "1240.00"),
        ("SG", "SEA", "10.000", "49.999", "3400.00"),
        ("TH", "AIR", "0.000", "0.999", "690.00"),
        ("TH", "AIR", "1.000", "4.999", "1620.00"),
        ("TH", "SEA", "0.000", "9.999", "1180.00"),
        ("TH", "SEA", "10.000", "49.999", "3250.00"),
        ("IN", "AIR", "0.000", "0.999", "650.00"),
        ("IN", "AIR", "1.000", "4.999", "1550.00"),
        ("IN", "SEA", "0.000", "9.999", "1080.00"),
        ("IN", "SEA", "10.000", "49.999", "3050.00"),
    ]
    for origin in new_origins or []:
        shipping_cards.extend(
            (
                str(origin["code"]).upper(),
                str(rate["method"]).upper(),
                str(rate["min_kg"]),
                str(rate["max_kg"]),
                str(rate["cost_bdt"]),
            )
            for rate in origin["shipping_rates"]
        )
    for country_code, method, min_kg, max_kg, cost in shipping_cards:
        existing_card = session.scalar(
            select(ShippingRateCard).where(
                ShippingRateCard.country_id == countries[country_code].id,
                ShippingRateCard.method == method,
                ShippingRateCard.min_kg == Decimal(min_kg),
                ShippingRateCard.max_kg == Decimal(max_kg),
            )
        )
        if not existing_card:
            session.add(
                ShippingRateCard(
                    country=countries[country_code],
                    method=method,
                    min_kg=Decimal(min_kg),
                    max_kg=Decimal(max_kg),
                    cost_bdt=Decimal(cost),
                )
            )
        else:
            existing_card.cost_bdt = Decimal(cost)

    eta_rules = [
        ("CN", "LOCAL", "DOOR", 7, 12),
        ("CN", "LOCAL", "PICKUP", 5, 9),
        ("CN", "BULK", "DOOR", 18, 28),
        ("CN", "BULK", "PICKUP", 15, 24),
        ("SG", "LOCAL", "DOOR", 5, 8),
        ("SG", "LOCAL", "PICKUP", 4, 6),
        ("SG", "BULK", "DOOR", 14, 21),
        ("SG", "BULK", "PICKUP", 12, 19),
        ("TH", "LOCAL", "DOOR", 6, 10),
        ("TH", "LOCAL", "PICKUP", 5, 8),
        ("TH", "BULK", "DOOR", 14, 22),
        ("TH", "BULK", "PICKUP", 12, 20),
        ("IN", "LOCAL", "DOOR", 5, 9),
        ("IN", "LOCAL", "PICKUP", 4, 7),
        ("IN", "BULK", "DOOR", 12, 20),
        ("IN", "BULK", "PICKUP", 10, 18),
    ]
    for origin in new_origins or []:
        eta_rules.extend(
            (
                str(origin["code"]).upper(),
                str(rule["mode"]).upper(),
                str(rule["delivery_type"]).upper(),
                int(rule["min_days"]),
                int(rule["max_days"]),
            )
            for rule in origin["eta_rules"]
        )
    for country_code, mode, delivery_type, min_days, max_days in eta_rules:
        existing_rule = session.scalar(
            select(ETARule).where(
                ETARule.country_id == countries[country_code].id,
                ETARule.mode == mode,
                ETARule.delivery_type == delivery_type,
            )
        )
        if not existing_rule:
            session.add(
                ETARule(
                    country=countries[country_code],
                    mode=mode,
                    delivery_type=delivery_type,
                    min_days=min_days,
                    max_days=max_days,
                )
            )
        else:
            existing_rule.min_days = min_days
            existing_rule.max_days = max_days

    session.flush()
    return countries


def _supplier_rating(row: dict[str, str]) -> Decimal:
    defect_rate = _decimal_from_row(row, "Defect rates", "0")
    inspection = (row.get("Inspection results") or "").strip().lower()
    inspection_adjustment = {
        "pass": Decimal("0.30"),
        "pending": Decimal("0.00"),
        "fail": Decimal("-0.45"),
    }.get(inspection, Decimal("0.00"))
    rating = Decimal("4.80") - (defect_rate * Decimal("0.20")) + inspection_adjustment
    return min(max(rating, Decimal("1.00")), Decimal("5.00")).quantize(Decimal("0.01"))


def _estimated_weight_kg(product_type: str) -> Decimal:
    weights = {
        "haircare": Decimal("0.35"),
        "skincare": Decimal("0.25"),
        "cosmetics": Decimal("0.18"),
    }
    return weights.get(product_type.lower(), Decimal("0.30"))


def _ensure_supply_chain_dataset(session: Session, csv_path: Path, countries: dict[str, Country]) -> None:
    if not csv_path.exists():
        return

    supply_category = {
        category.slug: category
        for category in session.scalars(
            select(Category).where(Category.slug.in_(["haircare", "skincare", "cosmetics"]))
        ).all()
    }
    sellers = {seller.name: seller for seller in session.scalars(select(Seller)).all()}
    variants_by_sku = {
        variant.sku: variant
        for variant in session.scalars(select(ProductVariant).where(ProductVariant.sku.is_not(None))).all()
    }
    existing_sources = {
        source
        for source in session.scalars(
            select(SellerOffer.source_url).where(SellerOffer.source_url.like("supply-chain:%"))
        ).all()
        if source
    }

    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sku = (row.get("SKU") or "").strip()
            product_type = (row.get("Product type") or "supply-chain").strip()
            if not sku:
                continue

            category_slug = _slugify(product_type)
            category = supply_category.get(category_slug)
            if not category:
                category = Category(name=product_type.title(), slug=category_slug)
                session.add(category)
                session.flush()
                supply_category[category_slug] = category

            variant = variants_by_sku.get(sku)
            if not variant:
                product = Product(
                    name=f"{product_type.title()} {sku}",
                    slug=f"{category_slug}-{sku.lower()}",
                    model=sku,
                    description=(
                        "Imported from the supply-chain AI dataset with sales, stock, supplier, "
                        "manufacturing, shipping, and quality metrics."
                    ),
                    image=None,
                    category=category,
                )
                session.add(product)
                session.flush()
                variant = ProductVariant(
                    product=product,
                    sku=sku,
                    variant_name=f"{product_type.title()} dataset row",
                    weight_kg=_estimated_weight_kg(product_type),
                    length_cm=Decimal("12.00"),
                    width_cm=Decimal("8.00"),
                    height_cm=Decimal("4.00"),
                )
                session.add(variant)
                session.flush()
                variants_by_sku[sku] = variant

            supplier_name = (row.get("Supplier name") or "Dataset Supplier").strip()
            seller = sellers.get(supplier_name)
            if not seller:
                seller = Seller(
                    country=countries["IN"],
                    name=supplier_name,
                    rating=_supplier_rating(row),
                    note=f"Imported from {csv_path.name}; location: {(row.get('Location') or 'Unknown').strip()}",
                )
                session.add(seller)
                session.flush()
                sellers[supplier_name] = seller
            else:
                seller.rating = max(Decimal(seller.rating or 0), _supplier_rating(row))

            price = _decimal_from_row(row, "Price", "0")
            stock = max(_int_from_row(row, "Stock levels"), _int_from_row(row, "Availability"))
            moq = max(_int_from_row(row, "Order quantities", 1), 1)

            for mode, price_multiplier, minimum_order in [
                ("LOCAL", Decimal("1.00"), 1),
                ("BULK", Decimal("0.92"), moq),
            ]:
                source_url = f"supply-chain:{sku}:{mode}"
                if source_url in existing_sources:
                    continue
                session.add(
                    SellerOffer(
                        variant=variant,
                        country=countries["IN"],
                        seller=seller,
                        mode=mode,
                        price_origin=(price * price_multiplier).quantize(Decimal("0.01")),
                        currency="USD",
                        stock=stock,
                        moq=minimum_order,
                        source_url=source_url,
                    )
                )
                existing_sources.add(source_url)

    session.flush()


def _ensure_sellers_and_offers(session: Session, countries: dict[str, Country]) -> None:
    variants = session.scalars(select(ProductVariant).order_by(ProductVariant.id.asc())).all()
    if not variants:
        return

    existing_offer = session.scalar(select(SellerOffer.id).limit(1))
    if existing_offer:
        return

    sellers = {
        seller.name: seller
        for seller in session.scalars(select(Seller)).all()
    }

    seller_specs = [
        ("Shenzhen Prime Hub", "CN", "4.80"),
        ("Guangzhou SourceLink", "CN", "4.55"),
        ("Lion City Retail Export", "SG", "4.72"),
        ("Bangkok Trade Bridge", "TH", "4.49"),
    ]
    for name, country_code, rating in seller_specs:
        if name not in sellers:
            sellers[name] = Seller(country=countries[country_code], name=name, rating=Decimal(rating))
            session.add(sellers[name])

    session.flush()

    offers: list[SellerOffer] = []
    for index, variant in enumerate(variants, start=1):
        weight = Decimal(variant.weight_kg or Decimal("0.20"))
        base = Decimal("18.00") + (weight * Decimal("14.0")) + Decimal(index)
        offers.extend(
            [
                SellerOffer(
                    variant=variant,
                    country=countries["CN"],
                    seller=sellers["Shenzhen Prime Hub"],
                    mode="LOCAL",
                    price_origin=base,
                    currency="USD",
                    stock=120 + index * 5,
                    moq=1,
                ),
                SellerOffer(
                    variant=variant,
                    country=countries["CN"],
                    seller=sellers["Guangzhou SourceLink"],
                    mode="BULK",
                    price_origin=max(base - Decimal("2.10"), Decimal("10.00")),
                    currency="USD",
                    stock=300 + index * 12,
                    moq=5,
                ),
                SellerOffer(
                    variant=variant,
                    country=countries["SG"],
                    seller=sellers["Lion City Retail Export"],
                    mode="LOCAL",
                    price_origin=base + Decimal("4.20"),
                    currency="USD",
                    stock=60 + index * 3,
                    moq=1,
                ),
            ]
        )

    session.add_all(offers)


def _ensure_medical_catalog(session: Session, countries: dict[str, Country]) -> None:
    category_slug = "medical-products-accessories"
    category = session.scalar(select(Category).where(Category.slug == category_slug))
    if not category:
        category = Category(name="Medical Products & Accessories", slug=category_slug)
        session.add(category)
        session.flush()

    product_names = [
        "Digital Clinical Thermometer",
        "Infrared Forehead Thermometer",
        "Fingertip Pulse Oximeter",
        "Automatic Blood Pressure Monitor",
        "Aneroid Blood Pressure Kit",
        "Dual-Head Stethoscope",
        "Blood Glucose Monitoring Kit",
        "Glucose Test Strip Pack",
        "Portable Compressor Nebulizer",
        "Personal Steam Inhaler",
        "Comprehensive First Aid Kit",
        "Cotton Bandage Roll",
        "Adhesive Bandage Assortment",
        "Sterile Gauze Pad Pack",
        "Medical Adhesive Tape",
        "Elastic Crepe Bandage",
        "Adjustable Knee Support",
        "Compression Ankle Support",
        "Wrist Support Brace",
        "Lumbar Support Belt",
        "Soft Cervical Collar",
        "Adjustable Arm Sling",
        "Aluminum Underarm Crutches",
        "Height-Adjustable Walking Cane",
        "Foldable Walking Frame",
        "Lightweight Manual Wheelchair",
        "Adjustable Shower Chair",
        "Portable Commode Chair",
        "Safety Bed Rail",
        "Anti-Decubitus Air Mattress",
        "Reusable Hot and Cold Pack",
        "Electric Heating Pad",
        "Reusable Ice Bag",
        "Disposable Adult Face Mask",
        "Disposable Child Face Mask",
        "Protective Face Shield",
        "Nitrile Examination Gloves",
        "Latex Examination Gloves",
        "Touchless Sanitizer Dispenser",
        "Weekly Pill Organizer",
        "Lockable Medicine Storage Box",
        "Tablet Cutter",
        "Tablet Crusher",
        "Hearing Aid Battery Pack",
        "Thermometer Probe Cover Pack",
        "Manual Nasal Aspirator",
        "Digital Baby Weighing Scale",
        "Digital Body Weight Scale",
        "Medical Measuring Tape",
        "Reusable Diagnostic Penlight",
        "Neurological Reflex Hammer",
        "Medical Tuning Fork Set",
        "Portable Otoscope Set",
        "Portable Ophthalmoscope Set",
        "LED Examination Light",
        "Portable Suction Machine",
        "Oxygen Mask Kit",
        "Oxygen Nasal Cannula",
        "Handheld Incentive Spirometer",
        "Peak Flow Meter",
    ]

    existing_products = {product.slug: product for product in session.scalars(select(Product)).all()}
    variants_by_sku = {
        variant.sku: variant
        for variant in session.scalars(select(ProductVariant).where(ProductVariant.sku.like("MED-%"))).all()
    }
    medical_variants: list[tuple[int, ProductVariant]] = []

    for index, name in enumerate(product_names, start=1):
        slug = _slugify(name)
        product = existing_products.get(slug)
        description = (
            f"{name} for healthcare, home-care, clinic, and institutional sourcing comparison. "
            "Buyer should verify applicable registration, certification, and local regulatory requirements before purchase."
        )
        if not product:
            product = Product(
                name=name,
                slug=slug,
                model=f"MED-{index:03d}",
                description=description,
                image=None,
                category=category,
            )
            session.add(product)
            session.flush()
            existing_products[slug] = product
        else:
            product.name = name
            product.model = f"MED-{index:03d}"
            product.description = description
            product.category = category

        sku = f"MED-{index:03d}-STD"
        variant = variants_by_sku.get(sku)
        weight = (Decimal("0.08") + Decimal(index % 12) * Decimal("0.12")).quantize(Decimal("0.001"))
        length = Decimal(8 + (index % 8) * 3)
        width = Decimal(6 + (index % 6) * 2)
        height = Decimal(3 + (index % 5) * 2)
        if not variant:
            variant = ProductVariant(
                product=product,
                sku=sku,
                variant_name="Standard",
                weight_kg=weight,
                length_cm=length,
                width_cm=width,
                height_cm=height,
            )
            session.add(variant)
            session.flush()
            variants_by_sku[sku] = variant
        else:
            variant.product = product
            variant.variant_name = "Standard"
            variant.weight_kg = weight
            variant.length_cm = length
            variant.width_cm = width
            variant.height_cm = height
        medical_variants.append((index, variant))

    seller_specs = [
        ("Shenzhen Medical Supply Hub", "CN", "4.78"),
        ("India Care Instruments", "IN", "4.66"),
        ("Singapore Clinical Supply", "SG", "4.84"),
    ]
    sellers_by_key = {
        (seller.name, seller.country.code): seller
        for seller in session.scalars(select(Seller)).all()
    }
    for seller_name, country_code, rating in seller_specs:
        key = (seller_name, country_code)
        if key not in sellers_by_key:
            sellers_by_key[key] = Seller(
                country=countries[country_code],
                name=seller_name,
                rating=Decimal(rating),
                note="Medical-accessory sourcing supplier; buyer verification required for regulated items.",
            )
            session.add(sellers_by_key[key])
    session.flush()

    existing_offers = {
        (offer.variant_id, offer.country_id, offer.seller_id, offer.mode): offer
        for offer in session.scalars(select(SellerOffer)).all()
    }
    offer_specs = [
        ("CN", "Shenzhen Medical Supply Hub", "LOCAL", Decimal("1.00"), 1),
        ("CN", "Shenzhen Medical Supply Hub", "BULK", Decimal("0.86"), 10),
        ("IN", "India Care Instruments", "LOCAL", Decimal("0.96"), 1),
        ("SG", "Singapore Clinical Supply", "LOCAL", Decimal("1.14"), 1),
    ]
    for index, variant in medical_variants:
        base_price = (
            Decimal("3.50")
            + Decimal(index) * Decimal("1.85")
            + Decimal(variant.weight_kg) * Decimal("8.00")
        ).quantize(Decimal("0.01"))
        for country_code, seller_name, mode, multiplier, moq in offer_specs:
            country = countries[country_code]
            seller = sellers_by_key[(seller_name, country_code)]
            key = (variant.id, country.id, seller.id, mode)
            offer = existing_offers.get(key)
            price = (base_price * multiplier).quantize(Decimal("0.01"))
            if not offer:
                offer = SellerOffer(
                    variant=variant,
                    country=country,
                    seller=seller,
                    mode=mode,
                    price_origin=price,
                    currency="USD",
                    stock=150 + index * 8,
                    moq=moq,
                )
                session.add(offer)
                existing_offers[key] = offer
            else:
                offer.price_origin = price
                offer.currency = "USD"
                offer.stock = 150 + index * 8
                offer.moq = moq


def _ensure_precious_catalog(session: Session, countries: dict[str, Country]) -> None:
    category_slug = "jewelry-gems-precious-metals"
    category = session.scalar(select(Category).where(Category.slug == category_slug))
    if not category:
        category = Category(name="Jewelry, Gems & Precious Metals", slug=category_slug)
        session.add(category)
        session.flush()

    product_names = [
        # Gold jewelry
        "Gold Cable Chain Necklace",
        "Gold Figaro Chain Necklace",
        "Gold Rope Chain Necklace",
        "Gold Pendant Necklace",
        "Gold Link Bracelet",
        "Gold Cuff Bracelet",
        "Gold Classic Bangle",
        "Gold Stackable Ring",
        "Gold Signet Ring",
        "Gold Wedding Band",
        "Gold Stud Earrings",
        "Gold Hoop Earrings",
        "Gold Bullion Bar",
        "Gold Bullion Coin",
        # Silver jewelry
        "Silver Cable Chain Necklace",
        "Silver Figaro Chain Necklace",
        "Silver Rope Chain Necklace",
        "Silver Pendant Necklace",
        "Silver Link Bracelet",
        "Silver Cuff Bracelet",
        "Silver Classic Bangle",
        "Silver Stackable Ring",
        "Silver Signet Ring",
        "Silver Wedding Band",
        "Silver Stud Earrings",
        "Silver Hoop Earrings",
        "Silver Bullion Bar",
        "Silver Bullion Coin",
        # Other precious-metal jewelry and settings
        "Platinum Chain Necklace",
        "Platinum Link Bracelet",
        "Platinum Wedding Band",
        "Platinum Stud Earrings",
        "Palladium Wedding Band",
        "Rose Gold Bracelet",
        "White Gold Pendant Setting",
        "Two-Tone Gold Ring",
        # Diamond stones and jewelry
        "Round-Cut Diamond Stone",
        "Princess-Cut Diamond Stone",
        "Emerald-Cut Diamond Stone",
        "Oval-Cut Diamond Stone",
        "Pear-Cut Diamond Stone",
        "Marquise-Cut Diamond Stone",
        "Cushion-Cut Diamond Stone",
        "Radiant-Cut Diamond Stone",
        "Asscher-Cut Diamond Stone",
        "Heart-Cut Diamond Stone",
        "Diamond Solitaire Pendant",
        "Diamond Tennis Bracelet",
        "Diamond Stud Earrings",
        "Diamond Cluster Ring",
        # Colored gemstones
        "Ruby Gemstone",
        "Blue Sapphire Gemstone",
        "Emerald Gemstone",
        "Amethyst Gemstone",
        "Aquamarine Gemstone",
        "Citrine Gemstone",
        "Garnet Gemstone",
        "Opal Gemstone",
        "Peridot Gemstone",
        "Tanzanite Gemstone",
    ]

    existing_products = {product.slug: product for product in session.scalars(select(Product)).all()}
    variants_by_sku = {
        variant.sku: variant
        for variant in session.scalars(select(ProductVariant).where(ProductVariant.sku.like("JPM-%"))).all()
    }
    precious_variants: list[tuple[int, ProductVariant]] = []

    for index, name in enumerate(product_names, start=1):
        slug = _slugify(name)
        product = existing_products.get(slug)
        description = (
            f"{name} for cross-border supplier discovery and quote comparison. "
            "Displayed offer prices are indicative demo values, not live precious-material market quotations. "
            "Material composition, weight, dimensions, treatment, grade, origin, hallmark, certification, "
            "and import requirements are supplier-declared and must be independently verified before purchase."
        )
        if not product:
            product = Product(
                name=name,
                slug=slug,
                model=f"JPM-{index:03d}",
                description=description,
                image=None,
                category=category,
            )
            session.add(product)
            session.flush()
            existing_products[slug] = product
        else:
            product.name = name
            product.model = f"JPM-{index:03d}"
            product.description = description
            product.category = category

        sku = f"JPM-{index:03d}-STD"
        variant = variants_by_sku.get(sku)
        if index <= 14:
            variant_name = "Gold — purity and net weight to be specified"
        elif index <= 28:
            variant_name = "Silver — fineness and net weight to be specified"
        elif index <= 32:
            variant_name = "Platinum — fineness and net weight to be specified"
        elif index == 33:
            variant_name = "Palladium — fineness and net weight to be specified"
        elif index <= 36:
            variant_name = "Gold alloy — composition and net weight to be specified"
        elif index <= 50:
            variant_name = "Diamond — cut, carat, color, clarity and certificate to be specified"
        else:
            variant_name = "Gemstone — grade, weight and treatment disclosure to be specified"
        is_stone = 37 <= index <= 46 or index >= 51
        if is_stone:
            weight = (Decimal("0.010") + Decimal(index % 5) * Decimal("0.002")).quantize(Decimal("0.001"))
            length, width, height = Decimal("6.00"), Decimal("6.00"), Decimal("3.00")
        else:
            weight = (Decimal("0.040") + Decimal(index % 7) * Decimal("0.006")).quantize(Decimal("0.001"))
            length, width, height = Decimal("12.00"), Decimal("9.00"), Decimal("4.00")

        if not variant:
            variant = ProductVariant(
                product=product,
                sku=sku,
                variant_name=variant_name,
                weight_kg=weight,
                length_cm=length,
                width_cm=width,
                height_cm=height,
            )
            session.add(variant)
            session.flush()
            variants_by_sku[sku] = variant
        else:
            variant.product = product
            variant.variant_name = variant_name
            variant.weight_kg = weight
            variant.length_cm = length
            variant.width_cm = width
            variant.height_cm = height
        precious_variants.append((index, variant))

    seller_specs = [
        ("Jaipur Jewelry Sourcing Studio", "IN", "4.70"),
        ("Singapore Gem Trade Desk", "SG", "4.76"),
        ("Shenzhen Jewelry Components Hub", "CN", "4.58"),
    ]
    sellers_by_key = {
        (seller.name, seller.country.code): seller
        for seller in session.scalars(select(Seller)).all()
    }
    for seller_name, country_code, rating in seller_specs:
        key = (seller_name, country_code)
        if key not in sellers_by_key:
            sellers_by_key[key] = Seller(
                country=countries[country_code],
                name=seller_name,
                rating=Decimal(rating),
                note=(
                    "Demo jewelry and gemstone sourcing profile. Buyer due diligence, "
                    "material verification, and import-compliance review are required."
                ),
            )
            session.add(sellers_by_key[key])
    session.flush()

    existing_offers = {
        (offer.variant_id, offer.country_id, offer.seller_id, offer.mode): offer
        for offer in session.scalars(select(SellerOffer)).all()
    }
    offer_specs = [
        ("IN", "Jaipur Jewelry Sourcing Studio", "LOCAL", Decimal("1.00"), 1),
        ("IN", "Jaipur Jewelry Sourcing Studio", "BULK", Decimal("0.94"), 5),
        ("SG", "Singapore Gem Trade Desk", "LOCAL", Decimal("1.10"), 1),
        ("CN", "Shenzhen Jewelry Components Hub", "BULK", Decimal("0.91"), 10),
    ]
    for index, variant in precious_variants:
        if index <= 14:
            base_price = Decimal("150.00") + Decimal(index) * Decimal("18.50")
        elif index <= 28:
            base_price = Decimal("20.00") + Decimal(index - 14) * Decimal("3.25")
        elif index <= 36:
            base_price = Decimal("210.00") + Decimal(index - 28) * Decimal("24.00")
        elif index <= 50:
            base_price = Decimal("95.00") + Decimal(index - 36) * Decimal("28.00")
        else:
            base_price = Decimal("22.00") + Decimal(index - 50) * Decimal("8.00")

        for country_code, seller_name, mode, multiplier, moq in offer_specs:
            country = countries[country_code]
            seller = sellers_by_key[(seller_name, country_code)]
            key = (variant.id, country.id, seller.id, mode)
            offer = existing_offers.get(key)
            price = (base_price * multiplier).quantize(Decimal("0.01"))
            if not offer:
                offer = SellerOffer(
                    variant=variant,
                    country=country,
                    seller=seller,
                    mode=mode,
                    price_origin=price,
                    currency="USD",
                    stock=12 + index * 2,
                    moq=moq,
                )
                session.add(offer)
                existing_offers[key] = offer
            else:
                offer.price_origin = price
                offer.currency = "USD"
                offer.stock = 12 + index * 2
                offer.moq = moq


def _ensure_general_goods_catalog(
    session: Session,
    countries: dict[str, Country],
    manifest: dict[str, Any],
) -> None:
    category_specs = manifest["categories"]
    category_slugs = [str(item["slug"]) for item in category_specs]
    existing_categories = {
        item.slug: item
        for item in session.scalars(
            select(Category).where(Category.slug.in_(category_slugs))
        ).all()
    }
    categories: dict[str, Category] = {}
    for category_spec in category_specs:
        slug = str(category_spec["slug"])
        name = str(category_spec["name"])
        category = existing_categories.get(slug)
        if category and category.name != name:
            raise RuntimeError(
                f"Category slug collision for {slug}: expected {name!r}, found {category.name!r}"
            )
        if not category:
            category = Category(name=name, slug=slug)
            session.add(category)
        categories[slug] = category
    session.flush()

    product_specs: list[tuple[dict[str, Any], dict[str, Any]]] = [
        (category_spec, product_spec)
        for category_spec in category_specs
        for product_spec in category_spec["products"]
    ]
    expected_slugs = [str(product_spec["slug"]) for _category, product_spec in product_specs]
    expected_models = [str(product_spec["model"]) for _category, product_spec in product_specs]
    product_candidates = session.scalars(
        select(Product).where(
            or_(
                Product.slug.in_(expected_slugs),
                Product.model.in_(expected_models),
            )
        )
    ).all()
    products_by_slug: dict[str, Product] = {}
    products_by_model: dict[str, Product] = {}
    for product in product_candidates:
        slug_match = product.slug in expected_slugs
        model_match = bool(product.model and product.model in expected_models)
        if slug_match:
            if product.slug in products_by_slug:
                raise RuntimeError(f"Duplicate product slug already exists: {product.slug}")
            products_by_slug[product.slug] = product
        if model_match and product.model:
            if product.model in products_by_model:
                raise RuntimeError(f"Duplicate product model already exists: {product.model}")
            products_by_model[product.model] = product

    seeded_products: list[tuple[dict[str, Any], Product]] = []
    for category_spec, product_spec in product_specs:
        slug = str(product_spec["slug"])
        model = str(product_spec["model"])
        product_by_slug = products_by_slug.get(slug)
        product_by_model = products_by_model.get(model)
        if product_by_slug and product_by_slug.model != model:
            raise RuntimeError(
                f"Product slug collision for {slug}: expected model {model}, "
                f"found {product_by_slug.model or 'none'}"
            )
        if product_by_model and product_by_model.slug != slug:
            raise RuntimeError(
                f"Product model collision for {model}: expected slug {slug}, "
                f"found {product_by_model.slug}"
            )
        if product_by_slug and product_by_model and product_by_slug.id != product_by_model.id:
            raise RuntimeError(f"Product natural keys disagree for {slug} / {model}")

        category = categories[str(category_spec["slug"])]
        description = (
            f"{product_spec['name']} for cross-border supplier discovery and quote comparison. "
            "Displayed prices and availability are indicative demo values, not live supplier quotations. "
            f"{str(product_spec['spec_caveat']).strip()}"
        )
        seed_image = _owned_product_image_path(product_spec.get("image"), f"{model} image")
        product = product_by_slug or product_by_model
        if not product:
            product = Product(
                name=str(product_spec["name"]),
                slug=slug,
                model=model,
                description=description,
                image=seed_image,
                category=category,
            )
            session.add(product)
            products_by_slug[slug] = product
            products_by_model[model] = product
        else:
            product.name = str(product_spec["name"])
            product.description = description
            product.category = category
            product.image = _merge_seed_image(product.image, seed_image)
        seeded_products.append((product_spec, product))
    session.flush()

    expected_skus = [str(product_spec["sku"]) for product_spec, _product in seeded_products]
    variants_by_sku: dict[str, ProductVariant] = {}
    for variant in session.scalars(
        select(ProductVariant).where(ProductVariant.sku.in_(expected_skus))
    ).all():
        if variant.sku in variants_by_sku:
            raise RuntimeError(f"Duplicate product SKU already exists: {variant.sku}")
        if variant.sku:
            variants_by_sku[variant.sku] = variant

    seeded_variants: list[tuple[dict[str, Any], ProductVariant]] = []
    for product_spec, product in seeded_products:
        sku = str(product_spec["sku"])
        variant = variants_by_sku.get(sku)
        if variant and variant.product_id != product.id:
            raise RuntimeError(
                f"Product SKU collision for {sku}: expected product {product.slug}, "
                f"found product id {variant.product_id}"
            )
        dimensions = product_spec["dimensions_cm"]
        if not variant:
            variant = ProductVariant(product=product, sku=sku)
            session.add(variant)
            variants_by_sku[sku] = variant
        variant.variant_name = "Standard supplier-declared specification"
        variant.weight_kg = Decimal(str(product_spec["weight_kg"]))
        variant.length_cm = Decimal(str(dimensions[0]))
        variant.width_cm = Decimal(str(dimensions[1]))
        variant.height_cm = Decimal(str(dimensions[2]))
        seeded_variants.append((product_spec, variant))
    session.flush()

    supplier_specs = manifest["supplier_profiles"]
    supplier_names = [str(item["name"]) for item in supplier_specs]
    supplier_candidates = session.scalars(
        select(Seller).where(Seller.name.in_(supplier_names))
    ).all()
    sellers_by_key: dict[tuple[str, str], Seller] = {}
    for seller in supplier_candidates:
        key = (seller.country.code, seller.name)
        if key in sellers_by_key:
            raise RuntimeError(
                f"Duplicate supplier already exists for {seller.country.code} / {seller.name}"
            )
        sellers_by_key[key] = seller

    for supplier_spec in supplier_specs:
        country_code = str(supplier_spec["country_code"]).upper()
        seller_name = str(supplier_spec["name"])
        key = (country_code, seller_name)
        seller = sellers_by_key.get(key)
        if not seller:
            seller = Seller(country=countries[country_code], name=seller_name)
            session.add(seller)
            sellers_by_key[key] = seller
        seller.rating = Decimal(str(supplier_spec["rating"]))
        seller.note = str(supplier_spec["note"])
    session.flush()

    supplier_by_country = {
        str(item["country_code"]).upper(): sellers_by_key[
            (str(item["country_code"]).upper(), str(item["name"]))
        ]
        for item in supplier_specs
    }
    seeded_variant_ids = [variant.id for _product_spec, variant in seeded_variants]
    offers_by_key: dict[tuple[int, int, int, str], SellerOffer] = {}
    for offer in session.scalars(
        select(SellerOffer).where(SellerOffer.variant_id.in_(seeded_variant_ids))
    ).all():
        key = (offer.variant_id, offer.country_id, offer.seller_id, offer.mode)
        if key in offers_by_key:
            raise RuntimeError(
                f"Duplicate seller offer already exists for variant {offer.variant_id}"
            )
        offers_by_key[key] = offer

    for product_spec, variant in seeded_variants:
        origins = [str(code).upper() for code in product_spec["origins"]]
        base_price = Decimal(str(product_spec["base_price_usd"]))
        for strategy in manifest["offer_strategy"]:
            country_code = origins[int(strategy["origin_index"])]
            country = countries[country_code]
            seller = supplier_by_country[country_code]
            mode = str(strategy["mode"]).upper()
            key = (variant.id, country.id, seller.id, mode)
            offer = offers_by_key.get(key)
            if not offer:
                offer = SellerOffer(
                    variant=variant,
                    country=country,
                    seller=seller,
                    mode=mode,
                    price_origin=Decimal("0.01"),
                    currency="USD",
                )
                session.add(offer)
                offers_by_key[key] = offer
            offer.price_origin = (
                base_price * Decimal(str(strategy["price_multiplier"]))
            ).quantize(Decimal("0.01"))
            offer.currency = "USD"
            offer.stock = int(strategy["stock"])
            offer.moq = int(strategy["moq"])


def _import_legacy_catalog(session: Session, sqlite_path: Path) -> bool:
    """Idempotently sync the legacy catalog without unstable placeholder images."""
    if not sqlite_path.exists():
        return False

    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    try:
        categories = cursor.execute("select id, name, slug from catalog_category order by id").fetchall()
        products = cursor.execute(
            "select id, name, slug, model, description, category_id, image, image_url from catalog_product order by id"
        ).fetchall()
        variants = cursor.execute(
            "select id, sku, variant_name, weight_kg, length_cm, width_cm, height_cm, product_id "
            "from catalog_productvariant order by id"
        ).fetchall()
    except sqlite3.DatabaseError:
        connection.close()
        return False

    if not products:
        connection.close()
        return False

    existing_categories = {item.slug: item for item in session.scalars(select(Category)).all()}
    category_map: dict[int, Category] = {}
    for row in categories:
        category = existing_categories.get(row["slug"])
        if not category:
            category = Category(name=row["name"], slug=row["slug"])
            session.add(category)
            session.flush()
            existing_categories[row["slug"]] = category
        else:
            category.name = row["name"]
        category_map[row["id"]] = category

    existing_products = {item.slug: item for item in session.scalars(select(Product)).all()}
    product_map: dict[int, Product] = {}
    for row in products:
        product = existing_products.get(row["slug"])
        # Prefer uploaded media over third-party placeholders; local files are stable and owned by the project.
        image = (row["image"] or "").strip() or (row["image_url"] or "").strip() or None
        if image and "loremflickr.com" in image.lower():
            image = None
        if not product:
            product = Product(name=row["name"], slug=row["slug"], model=row["model"],
                              description=row["description"], image=image,
                              category=category_map[row["category_id"]])
            session.add(product)
            session.flush()
            existing_products[row["slug"]] = product
        else:
            product.name = row["name"]
            product.model = row["model"]
            product.description = row["description"]
            product.image = _merge_seed_image(product.image, image)
            product.category = category_map[row["category_id"]]
        product_map[row["id"]] = product

    def variant_key(product_id: int, sku: str | None, name: str | None, weight: object,
                    length: object, width: object, height: object) -> tuple[object, ...]:
        return (product_id, (sku or "").strip(), (name or "").strip(), Decimal(str(weight or 0)),
                Decimal(str(length or 0)), Decimal(str(width or 0)), Decimal(str(height or 0)))

    existing_variants: dict[tuple[object, ...], ProductVariant] = {}
    duplicate_variants: list[tuple[ProductVariant, ProductVariant]] = []
    for item in session.scalars(select(ProductVariant).order_by(ProductVariant.id.asc())).all():
        key = variant_key(item.product_id, item.sku, item.variant_name, item.weight_kg,
                          item.length_cm, item.width_cm, item.height_cm)
        keeper = existing_variants.get(key)
        if keeper:
            duplicate_variants.append((item, keeper))
        else:
            existing_variants[key] = item

    # Preserve offer references while removing variants created by older non-idempotent imports.
    for duplicate, keeper in duplicate_variants:
        for offer in session.scalars(select(SellerOffer).where(SellerOffer.variant_id == duplicate.id)).all():
            offer.variant = keeper
        session.delete(duplicate)
    session.flush()

    for row in variants:
        product = product_map[row["product_id"]]
        key = variant_key(product.id, row["sku"], row["variant_name"], row["weight_kg"],
                          row["length_cm"], row["width_cm"], row["height_cm"])
        variant = existing_variants.get(key)
        if not variant:
            variant = ProductVariant(
                product=product,
                sku=row["sku"],
                variant_name=row["variant_name"],
                weight_kg=Decimal(str(row["weight_kg"] or 0)),
                length_cm=Decimal(str(row["length_cm"] or 0)),
                width_cm=Decimal(str(row["width_cm"] or 0)),
                height_cm=Decimal(str(row["height_cm"] or 0)),
            )
            session.add(variant)
            session.flush()
            existing_variants[key] = variant
        else:
            variant.product = product_map[row["product_id"]]
            variant.variant_name = row["variant_name"]
            variant.weight_kg = Decimal(str(row["weight_kg"] or 0))
            variant.length_cm = Decimal(str(row["length_cm"] or 0))
            variant.width_cm = Decimal(str(row["width_cm"] or 0))
            variant.height_cm = Decimal(str(row["height_cm"] or 0))

    connection.close()
    session.flush()
    return True


def _remove_unstable_placeholder_images(session: Session) -> None:
    for product in session.scalars(
        select(Product).where(Product.image.ilike("%loremflickr.com/%"))
    ).all():
        product.image = None


def _deterministic_snapshot_sku(product_slug: str, variant_index: int) -> str:
    digest = hashlib.sha256(
        f"public-catalog-v2:{product_slug.casefold()}:{variant_index}".encode("utf-8")
    ).hexdigest()[:16]
    return f"SNAP-{digest.upper()}"


def _ensure_public_catalog_snapshot(
    session: Session,
    snapshot: dict[str, Any],
    countries: dict[str, Country],
) -> dict[str, int]:
    """Create missing public snapshot rows without overwriting managed catalog data."""

    existing_categories: dict[str, Category] = {}
    for category in session.scalars(select(Category).order_by(Category.id.asc())).all():
        key = category.slug.casefold()
        if key in existing_categories:
            raise RuntimeError(
                f"Existing category slugs collide case-insensitively: {category.slug}"
            )
        existing_categories[key] = category

    created_categories = 0
    for category_spec in snapshot["categories"]:
        slug = str(category_spec["slug"])
        key = slug.casefold()
        if key in existing_categories:
            continue
        category = Category(name=str(category_spec["name"]), slug=slug)
        session.add(category)
        existing_categories[key] = category
        created_categories += 1
    session.flush()

    existing_products: dict[str, Product] = {}
    for product in session.scalars(select(Product).order_by(Product.id.asc())).all():
        key = product.slug.casefold()
        if key in existing_products:
            raise RuntimeError(
                f"Existing product slugs collide case-insensitively: {product.slug}"
            )
        existing_products[key] = product

    created_product_keys: set[str] = set()
    product_specs_by_key: dict[str, dict[str, Any]] = {}
    filled_images = 0
    for product_spec in snapshot["products"]:
        slug = str(product_spec["slug"])
        key = slug.casefold()
        product_specs_by_key[key] = product_spec
        image = _snapshot_owned_image_path(
            product_spec.get("image"), f"product {slug} image"
        )
        product = existing_products.get(key)
        if product is not None:
            if not (product.image or "").strip() and image:
                product.image = image
                filled_images += 1
            continue

        category_slug = str(product_spec["category"]["slug"])
        product = Product(
            name=str(product_spec["name"]),
            slug=slug,
            model=(str(product_spec["model"]) if product_spec.get("model") else None),
            description=(
                str(product_spec["description"])
                if product_spec.get("description")
                else None
            ),
            image=image,
            category=existing_categories[category_slug.casefold()],
        )
        session.add(product)
        existing_products[key] = product
        created_product_keys.add(key)
    session.flush()

    variants_by_sku: dict[str, ProductVariant] = {}
    variants_by_product_and_name: dict[tuple[int, str], list[ProductVariant]] = {}
    for variant in session.scalars(
        select(ProductVariant).order_by(ProductVariant.id.asc())
    ).all():
        if variant.sku:
            sku_key = variant.sku.casefold()
            if sku_key in variants_by_sku:
                raise RuntimeError(
                    f"Existing variant SKUs collide case-insensitively: {variant.sku}"
                )
            variants_by_sku[sku_key] = variant
        name_key = (variant.variant_name or "").strip().casefold()
        variants_by_product_and_name.setdefault(
            (variant.product_id, name_key), []
        ).append(variant)

    created_variants_by_product: dict[str, list[ProductVariant]] = {
        key: [] for key in created_product_keys
    }
    created_variants = 0
    for product_spec in snapshot["products"]:
        product_key = str(product_spec["slug"]).casefold()
        product = existing_products[product_key]
        for variant_index, variant_spec in enumerate(product_spec["variants"]):
            source_sku = (str(variant_spec.get("sku") or "").strip() or None)
            variant: ProductVariant | None = None
            if source_sku:
                variant = variants_by_sku.get(source_sku.casefold())
                if variant is not None and variant.product_id != product.id:
                    raise RuntimeError(
                        f"Snapshot SKU {source_sku} already belongs to another product"
                    )
            if variant is None:
                name_key = str(variant_spec.get("variant_name") or "").strip().casefold()
                name_matches = variants_by_product_and_name.get(
                    (product.id, name_key), []
                )
                if len(name_matches) > 1:
                    raise RuntimeError(
                        f"Product {product.slug} has ambiguous variants named "
                        f"{variant_spec.get('variant_name') or ''}"
                    )
                if name_matches:
                    variant = name_matches[0]
            if variant is not None:
                continue

            sku = source_sku or _deterministic_snapshot_sku(product.slug, variant_index)
            sku_key = sku.casefold()
            conflicting_variant = variants_by_sku.get(sku_key)
            if conflicting_variant is not None:
                raise RuntimeError(
                    f"Generated snapshot SKU {sku} already belongs to another product"
                )
            variant = ProductVariant(
                product=product,
                sku=sku,
                variant_name=(
                    str(variant_spec["variant_name"])
                    if variant_spec.get("variant_name")
                    else None
                ),
                weight_kg=Decimal(str(variant_spec["weight_kg"])),
                length_cm=Decimal(str(variant_spec["length_cm"])),
                width_cm=Decimal(str(variant_spec["width_cm"])),
                height_cm=Decimal(str(variant_spec["height_cm"])),
            )
            session.add(variant)
            variants_by_sku[sku_key] = variant
            variants_by_product_and_name.setdefault(
                (product.id, (variant.variant_name or "").strip().casefold()), []
            ).append(variant)
            if product_key in created_variants_by_product:
                created_variants_by_product[product_key].append(variant)
            created_variants += 1
    session.flush()

    reference_sellers: dict[str, Seller] = {}
    for seller in session.scalars(
        select(Seller)
        .where(Seller.is_active.is_(True))
        .order_by(Seller.country_id.asc(), Seller.name.asc(), Seller.id.asc())
    ).all():
        reference_sellers.setdefault(seller.country.code, seller)

    created_offers = 0
    for product_key in sorted(created_product_keys):
        product_spec = product_specs_by_key[product_key]
        eligible_country: Country | None = None
        reference_seller: Seller | None = None
        for raw_code in product_spec["market"]["countries"]:
            code = str(raw_code).upper()
            if code in countries and code in reference_sellers:
                eligible_country = countries[code]
                reference_seller = reference_sellers[code]
                break
        if eligible_country is None or reference_seller is None:
            raise RuntimeError(
                f"No active reference supplier is available for snapshot product "
                f"{product_spec['slug']}"
            )

        local_price = Decimal(str(product_spec["market"]["min_price"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        bulk_price = max(local_price * Decimal("0.90"), Decimal("0.01")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        stock_seed = int(
            hashlib.sha256(product_key.encode("utf-8")).hexdigest()[:8], 16
        )
        for variant in created_variants_by_product[product_key]:
            for mode, price, stock, moq in (
                ("LOCAL", local_price, 100 + stock_seed % 400, 1),
                ("BULK", bulk_price, 500 + stock_seed % 1500, 10),
            ):
                session.add(
                    SellerOffer(
                        variant=variant,
                        country=eligible_country,
                        seller=reference_seller,
                        mode=mode,
                        price_origin=price,
                        currency="USD",
                        stock=stock,
                        moq=moq,
                        source_url=(
                            "development-reference:public-catalog-snapshot-v2:"
                            f"{product_spec['slug']}:{mode.lower()}"
                        ),
                    )
                )
                created_offers += 1

    session.flush()
    return {
        "categories": created_categories,
        "products": len(created_product_keys),
        "variants": created_variants,
        "offers": created_offers,
        "images": filled_images,
    }


_LEGACY_DEMO_FINGERPRINTS: dict[str, dict[str, Any]] = {
    "anker-ganprime-735-charger": {
        "name": "Anker GaNPrime 735 Charger",
        "model": "A2668",
        "description": "65W GaN charger suited for local and bulk sourcing flows.",
        "image": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=80",
        "category": ("consumer-electronics", "Consumer Electronics"),
        "variants": {
            "ANKER-A2668-US": ("US Plug", "0.220", "10.00", "6.00", "4.50", 1),
            "ANKER-A2668-EU": ("EU Plug", "0.230", "10.00", "6.50", "4.50", 2),
        },
    },
    "xiaomi-smart-air-purifier-4-compact": {
        "name": "Xiaomi Smart Air Purifier 4 Compact",
        "model": "AC-M18-SC",
        "description": "Compact appliance for cross-border home delivery sourcing.",
        "image": "https://images.unsplash.com/photo-1585771724684-38269d6639fd?auto=format&fit=crop&w=900&q=80",
        "category": ("home-appliances", "Home Appliances"),
        "variants": {
            "XI-AIR-4C-WHITE": ("White", "2.200", "22.00", "22.00", "35.50", 3),
        },
    },
    "baseus-bowie-h1i-headphones": {
        "name": "Baseus Bowie H1i Headphones",
        "model": "H1i",
        "description": "Wireless ANC headset with strong marketplace availability.",
        "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80",
        "category": ("smart-devices", "Smart Devices"),
        "variants": {
            "BASEUS-H1I-BLK": ("Black", "0.480", "19.00", "17.00", "8.00", 4),
        },
    },
}


def _legacy_demo_offer_is_untouched(offer: SellerOffer, *, seed_index: int, weight: Decimal) -> bool:
    base = Decimal("18.00") + (weight * Decimal("14.0")) + Decimal(seed_index)
    expected = {
        ("CN", "Shenzhen Prime Hub", "LOCAL"): (
            base,
            120 + seed_index * 5,
            1,
        ),
        ("CN", "Guangzhou SourceLink", "BULK"): (
            max(base - Decimal("2.10"), Decimal("10.00")),
            300 + seed_index * 12,
            5,
        ),
        ("SG", "Lion City Retail Export", "LOCAL"): (
            base + Decimal("4.20"),
            60 + seed_index * 3,
            1,
        ),
    }
    expected_row = expected.get(
        (offer.country.code, offer.seller.name, offer.mode)
    )
    return bool(
        expected_row
        and offer.is_active
        and offer.currency == "USD"
        and offer.source_url in (None, "")
        and Decimal(offer.price_origin) == expected_row[0]
        and offer.stock == expected_row[1]
        and offer.moq == expected_row[2]
    )


def _remove_untouched_legacy_demo_catalog(session: Session) -> int:
    """Retire only exact, unmodified rows from the superseded three-item demo."""

    removed = 0
    retired_category_slugs: set[str] = set()
    for slug, fingerprint in _LEGACY_DEMO_FINGERPRINTS.items():
        product = session.scalar(select(Product).where(Product.slug == slug))
        if product is None:
            continue
        expected_category_slug, expected_category_name = fingerprint["category"]
        if not (
            product.is_active
            and product.name == fingerprint["name"]
            and product.model == fingerprint["model"]
            and product.description == fingerprint["description"]
            and product.image == fingerprint["image"]
            and product.category.slug == expected_category_slug
            and product.category.name == expected_category_name
            and product.category.is_active
        ):
            continue

        expected_variants = fingerprint["variants"]
        actual_variants = {variant.sku: variant for variant in product.variants}
        if set(actual_variants) != set(expected_variants):
            continue
        untouched = True
        for sku, expected_variant in expected_variants.items():
            variant = actual_variants[sku]
            name, weight, length, width, height, seed_index = expected_variant
            if not (
                variant.is_active
                and variant.variant_name == name
                and Decimal(variant.weight_kg) == Decimal(weight)
                and Decimal(variant.length_cm) == Decimal(length)
                and Decimal(variant.width_cm) == Decimal(width)
                and Decimal(variant.height_cm) == Decimal(height)
            ):
                untouched = False
                break
            if variant.offers and (
                len(variant.offers) != 3
                or not all(
                    _legacy_demo_offer_is_untouched(
                        offer,
                        seed_index=seed_index,
                        weight=Decimal(weight),
                    )
                    for offer in variant.offers
                )
            ):
                untouched = False
                break
        if not untouched:
            continue

        retired_category_slugs.add(expected_category_slug)
        session.delete(product)
        removed += 1

    if not removed:
        return 0
    session.flush()
    for category_slug in retired_category_slugs:
        category = session.scalar(select(Category).where(Category.slug == category_slug))
        if category is None:
            continue
        has_products = session.scalar(
            select(Product.id).where(Product.category_id == category.id).limit(1)
        )
        expected_name = next(
            fingerprint["category"][1]
            for fingerprint in _LEGACY_DEMO_FINGERPRINTS.values()
            if fingerprint["category"][0] == category_slug
        )
        if not has_products and category.is_active and category.name == expected_name:
            session.delete(category)
    session.flush()
    return removed


def _seed_demo_catalog(session: Session) -> None:
    categories = {
        "consumer-electronics": Category(name="Consumer Electronics", slug="consumer-electronics"),
        "smart-devices": Category(name="Smart Devices", slug="smart-devices"),
        "home-appliances": Category(name="Home Appliances", slug="home-appliances"),
    }
    session.add_all(categories.values())

    session.add_all(
        [
            Product(
                name="Anker GaNPrime 735 Charger",
                slug="anker-ganprime-735-charger",
                model="A2668",
                description="65W GaN charger suited for local and bulk sourcing flows.",
                image="https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=80",
                category=categories["consumer-electronics"],
                variants=[
                    ProductVariant(
                        sku="ANKER-A2668-US",
                        variant_name="US Plug",
                        weight_kg=Decimal("0.220"),
                        length_cm=Decimal("10.00"),
                        width_cm=Decimal("6.00"),
                        height_cm=Decimal("4.50"),
                    ),
                    ProductVariant(
                        sku="ANKER-A2668-EU",
                        variant_name="EU Plug",
                        weight_kg=Decimal("0.230"),
                        length_cm=Decimal("10.00"),
                        width_cm=Decimal("6.50"),
                        height_cm=Decimal("4.50"),
                    ),
                ],
            ),
            Product(
                name="Xiaomi Smart Air Purifier 4 Compact",
                slug="xiaomi-smart-air-purifier-4-compact",
                model="AC-M18-SC",
                description="Compact appliance for cross-border home delivery sourcing.",
                image="https://images.unsplash.com/photo-1585771724684-38269d6639fd?auto=format&fit=crop&w=900&q=80",
                category=categories["home-appliances"],
                variants=[
                    ProductVariant(
                        sku="XI-AIR-4C-WHITE",
                        variant_name="White",
                        weight_kg=Decimal("2.200"),
                        length_cm=Decimal("22.00"),
                        width_cm=Decimal("22.00"),
                        height_cm=Decimal("35.50"),
                    )
                ],
            ),
            Product(
                name="Baseus Bowie H1i Headphones",
                slug="baseus-bowie-h1i-headphones",
                model="H1i",
                description="Wireless ANC headset with strong marketplace availability.",
                image="https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=80",
                category=categories["smart-devices"],
                variants=[
                    ProductVariant(
                        sku="BASEUS-H1I-BLK",
                        variant_name="Black",
                        weight_kg=Decimal("0.480"),
                        length_cm=Decimal("19.00"),
                        width_cm=Decimal("17.00"),
                        height_cm=Decimal("8.00"),
                    )
                ],
            ),
        ]
    )


def _sync_legacy_offers(session: Session, sqlite_path: Path) -> int:
    """Upsert legacy sellers/offers using stable business keys, not database IDs."""
    if not sqlite_path.exists():
        return 0
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    try:
        countries = {row["id"]: row for row in connection.execute("select id, code, name from sourcing_country")}
        sellers = connection.execute("select id, name, rating, note, country_id from sourcing_seller").fetchall()
        products = {row["id"]: row for row in connection.execute("select id, slug from catalog_product")}
        variants = {row["id"]: row for row in connection.execute(
            "select id, sku, variant_name, weight_kg, length_cm, width_cm, height_cm, product_id from catalog_productvariant"
        )}
        offers = connection.execute(
            "select mode, price_origin, currency, stock, moq, source_url, country_id, seller_id, variant_id "
            "from sourcing_selleroffer"
        ).fetchall()
    except sqlite3.DatabaseError:
        connection.close()
        return 0

    country_by_code = {item.code: item for item in session.scalars(select(Country)).all()}
    product_by_slug = {item.slug: item for item in session.scalars(select(Product)).all()}
    new_variants = session.scalars(select(ProductVariant)).all()
    variant_by_key = {
        (item.product_id, (item.sku or "").strip(), (item.variant_name or "").strip(),
         Decimal(item.weight_kg), Decimal(item.length_cm), Decimal(item.width_cm), Decimal(item.height_cm)): item
        for item in new_variants
    }
    seller_by_key = {(item.country.code, item.name): item for item in session.scalars(select(Seller)).all()}
    seller_map: dict[int, Seller] = {}
    for row in sellers:
        legacy_country = countries[row["country_id"]]
        country = country_by_code.get(legacy_country["code"])
        if not country:
            country = Country(code=legacy_country["code"], name=legacy_country["name"])
            session.add(country); session.flush(); country_by_code[country.code] = country
        key = (country.code, row["name"])
        seller = seller_by_key.get(key)
        if not seller:
            seller = Seller(country=country, name=row["name"])
            session.add(seller); session.flush(); seller_by_key[key] = seller
        seller.rating = Decimal(str(row["rating"] or 0)); seller.note = row["note"]
        seller_map[row["id"]] = seller

    legacy_variant_map: dict[int, ProductVariant] = {}
    for legacy_id, row in variants.items():
        product = product_by_slug.get(products[row["product_id"]]["slug"])
        if not product:
            continue
        key = (product.id, (row["sku"] or "").strip(), (row["variant_name"] or "").strip(),
               Decimal(str(row["weight_kg"] or 0)), Decimal(str(row["length_cm"] or 0)),
               Decimal(str(row["width_cm"] or 0)), Decimal(str(row["height_cm"] or 0)))
        if key in variant_by_key:
            legacy_variant_map[legacy_id] = variant_by_key[key]

    existing = {
        (item.variant_id, item.country_id, item.seller_id, item.mode): item
        for item in session.scalars(select(SellerOffer)).all()
    }
    synced = 0
    for row in offers:
        variant = legacy_variant_map.get(row["variant_id"])
        seller = seller_map.get(row["seller_id"])
        country = country_by_code.get(countries[row["country_id"]]["code"])
        if not variant or not seller or not country:
            continue
        key = (variant.id, country.id, seller.id, row["mode"])
        offer = existing.get(key)
        if not offer:
            offer = SellerOffer(variant=variant, country=country, seller=seller, mode=row["mode"],
                                price_origin=Decimal(str(row["price_origin"])), currency=row["currency"])
            session.add(offer); existing[key] = offer
        offer.price_origin = Decimal(str(row["price_origin"])); offer.currency = row["currency"]
        offer.stock = row["stock"]; offer.moq = row["moq"]; offer.source_url = row["source_url"]
        synced += 1
    connection.close()
    session.flush()
    return synced


def seed_database(
    session: Session,
    legacy_sqlite_path: Path | None = None,
    supply_chain_csv_path: Path | None = None,
    public_catalog_snapshot_path: Path | None = None,
) -> None:
    general_goods_manifest = _load_general_goods_manifest()
    public_catalog_snapshot = _load_public_catalog_snapshot(
        public_catalog_snapshot_path
    )
    _remove_untouched_legacy_demo_catalog(session)
    has_products = session.scalar(select(Product.id).limit(1))

    if not has_products:
        # The committed public snapshot is now the canonical development
        # catalog. Legacy import remains optional, but the three-product demo
        # is intentionally not added because it is outside that 610-product
        # launch catalog.
        if legacy_sqlite_path:
            _import_legacy_catalog(session, legacy_sqlite_path)

    # Legacy data can grow after the rebuild DB is first created, so keep it synchronized.
    if legacy_sqlite_path and has_products:
        _import_legacy_catalog(session, legacy_sqlite_path)

    session.flush()
    countries = _ensure_reference_data(
        session,
        general_goods_manifest["new_origins"],
    )
    _ensure_sellers_and_offers(session, countries)
    _ensure_medical_catalog(session, countries)
    _ensure_precious_catalog(session, countries)
    _ensure_general_goods_catalog(session, countries, general_goods_manifest)
    if legacy_sqlite_path:
        _sync_legacy_offers(session, legacy_sqlite_path)
    if supply_chain_csv_path:
        _ensure_supply_chain_dataset(session, supply_chain_csv_path, countries)
    _ensure_public_catalog_snapshot(session, public_catalog_snapshot, countries)
    _remove_unstable_placeholder_images(session)
    session.commit()
