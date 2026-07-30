from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.export_public_catalog_snapshot import (
    BANNED_PUBLIC_KEYS,
    build_public_catalog_snapshot,
    serialize_public_catalog_snapshot,
    validate_public_catalog_snapshot,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
COMMITTED_SNAPSHOT = (
    REPOSITORY_ROOT
    / "apps"
    / "web-next"
    / "data"
    / "public-catalog.snapshot.json"
)


def _fixture_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE alembic_version (version_num TEXT NOT NULL);
        INSERT INTO alembic_version VALUES ('test_revision');

        CREATE TABLE catalog_categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            is_active INTEGER NOT NULL
        );
        CREATE TABLE catalog_products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            model TEXT,
            description TEXT,
            image TEXT,
            category_id INTEGER NOT NULL,
            is_active INTEGER NOT NULL
        );
        CREATE TABLE catalog_product_variants (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            sku TEXT,
            variant_name TEXT,
            weight_kg NUMERIC,
            length_cm NUMERIC,
            width_cm NUMERIC,
            height_cm NUMERIC,
            is_active INTEGER NOT NULL
        );
        CREATE TABLE sourcing_countries (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        );
        CREATE TABLE sourcing_sellers (
            id INTEGER PRIMARY KEY,
            rating NUMERIC,
            name TEXT,
            is_active INTEGER NOT NULL
        );
        CREATE TABLE sourcing_seller_offers (
            id INTEGER PRIMARY KEY,
            variant_id INTEGER NOT NULL,
            country_id INTEGER NOT NULL,
            seller_id INTEGER NOT NULL,
            price_origin NUMERIC NOT NULL,
            currency TEXT NOT NULL,
            mode TEXT NOT NULL,
            source_url TEXT,
            is_active INTEGER NOT NULL
        );

        -- This table and its values must never be read into the public export.
        CREATE TABLE accounts_users (
            id INTEGER PRIMARY KEY,
            email TEXT,
            phone TEXT,
            password_hash TEXT
        );
        INSERT INTO accounts_users
            VALUES (1, 'private@example.test', '+8801700000000', 'secret-hash');

        INSERT INTO catalog_categories VALUES (1, 'Medical', 'medical', 1);
        INSERT INTO catalog_products VALUES (
            1,
            'Pulse Oximeter',
            'pulse-oximeter',
            'PO-1',
            'Contact private@example.test for a confidential order',
            'https://images.example.test/private-token.jpg',
            1,
            1
        );
        INSERT INTO catalog_product_variants
            VALUES (11, 1, 'PO-1-BLUE', 'Blue', 0.2, 10, 5, 3, 1);
        INSERT INTO sourcing_countries VALUES (1, 'IN', 'India');
        INSERT INTO sourcing_sellers
            VALUES (21, 4.8, 'Confidential Seller Name', 1);
        INSERT INTO sourcing_seller_offers
            VALUES (
                31,
                11,
                1,
                21,
                12.5,
                'USD',
                'LOCAL',
                'https://supplier.example.test/private',
                1
            );
        """
    )
    return connection


def _walk_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(str(key).lower())
            keys.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_walk_keys(child))
    return keys


def test_exporter_whitelists_public_fields_and_is_reproducible() -> None:
    connection = _fixture_connection()
    try:
        snapshot = build_public_catalog_snapshot(connection, minimum_products=1)
    finally:
        connection.close()

    product = snapshot["products"][0]
    assert product["description"] is None
    assert product["image"] is None
    assert product["market"] == {
        "countries": ["IN"],
        "supplier_count": 1,
        "max_rating": 4.8,
        "risk_level": "Low",
        "recommended_score": 109.39,
        "min_price": 12.5,
        "currency": "USD",
        "min_delivery_days": 14,
    }
    second_connection = _fixture_connection()
    try:
        second_snapshot = build_public_catalog_snapshot(
            second_connection,
            minimum_products=1,
        )
    finally:
        second_connection.close()
    serialized = serialize_public_catalog_snapshot(snapshot)
    assert serialized == serialize_public_catalog_snapshot(second_snapshot)
    assert b"private@example.test" not in serialized
    assert b"+8801700000000" not in serialized
    assert b"secret-hash" not in serialized
    assert b"Confidential Seller Name" not in serialized
    assert b"supplier.example.test" not in serialized


def test_snapshot_rejects_case_insensitive_duplicate_slugs() -> None:
    connection = _fixture_connection()
    try:
        snapshot = build_public_catalog_snapshot(connection, minimum_products=1)
    finally:
        connection.close()
    duplicate = dict(snapshot["products"][0])
    duplicate["id"] = 2
    duplicate["slug"] = duplicate["slug"].upper()
    duplicate["variants"] = []
    duplicate["default_variant_id"] = None
    snapshot["products"].append(duplicate)

    with pytest.raises(RuntimeError, match="case-insensitively unique"):
        validate_public_catalog_snapshot(snapshot, minimum_products=1)


def test_committed_snapshot_is_complete_and_contains_no_private_scope() -> None:
    snapshot = json.loads(COMMITTED_SNAPSHOT.read_text(encoding="utf-8"))
    validate_public_catalog_snapshot(snapshot, minimum_products=610)

    assert snapshot["counts"] == {
        "categories": 27,
        "countries": 7,
        "products": 610,
        "variants": 610,
    }
    assert len(snapshot["products"]) == 610
    assert len(
        {product["slug"].casefold() for product in snapshot["products"]}
    ) == 610
    precious_products = [
        product
        for product in snapshot["products"]
        if product["category"]["slug"] == "jewelry-gems-precious-metals"
    ]
    assert len(precious_products) == 60
    assert all(product["variants"] for product in precious_products)
    assert all(product["market"].get("supplier_count", 0) >= 1 for product in precious_products)
    expected_priority_counts = {
        "beauty-tools-accessories": 12,
        "creator-content-tools": 12,
        "ecommerce-packaging-supplies": 12,
        "educational-academic-tools": 12,
        "fashion-accessories": 12,
        "home-organization-storage": 12,
        "kitchen-utility-tools": 12,
        "laptop-pc-accessories": 12,
        "mobile-accessories": 12,
        "office-desk-accessories": 12,
        "pet-care-accessories": 10,
        "travel-luggage-accessories": 10,
    }
    priority_counts = {
        slug: sum(
            product["category"]["slug"] == slug
            for product in snapshot["products"]
        )
        for slug in expected_priority_counts
    }
    assert priority_counts == expected_priority_counts
    priority_products = [
        product
        for product in snapshot["products"]
        if product["category"]["slug"] in expected_priority_counts
    ]
    assert all(product["variants"] for product in priority_products)
    assert all(product["market"].get("supplier_count", 0) >= 1 for product in priority_products)
    assert all(
        product["image"] is None
        or product["image"].startswith("/media/products/")
        for product in snapshot["products"]
    )
    assert all(product["description"] is None for product in snapshot["products"])
    assert not (_walk_keys(snapshot) & BANNED_PUBLIC_KEYS)

    serialized = COMMITTED_SNAPSHOT.read_bytes()
    assert b"http://" not in serialized
    assert b"https://" not in serialized
    assert b"@" not in serialized
