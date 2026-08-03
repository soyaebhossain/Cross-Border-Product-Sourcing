from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Category, Product
from app.seed import (
    _ensure_general_goods_catalog,
    _ensure_reference_data,
    _import_legacy_catalog,
    _load_general_goods_manifest,
)
from app.serializers import serialize_product


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _manifest_with_image(tmp_path, image: str):
    manifest = _load_general_goods_manifest()
    manifest["categories"][0]["products"][0]["image"] = image
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return _load_general_goods_manifest(path)


def test_manifest_owned_image_fills_empty_product_and_preserves_admin_media(
    tmp_path,
) -> None:
    manifest = _manifest_with_image(
        tmp_path,
        "products/priority/mobile-phone-case.webp",
    )
    first_spec = manifest["categories"][0]["products"][0]
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        countries = _ensure_reference_data(session, manifest["new_origins"])
        _ensure_general_goods_catalog(session, countries, manifest)
        product = session.scalar(
            select(Product).where(Product.slug == first_spec["slug"])
        )
        assert product is not None
        assert product.image == "products/priority/mobile-phone-case.webp"

        product.image = "products/admin-uploaded-phone-case.png"
        first_spec["image"] = "products/revised-seed-phone-case.webp"
        _ensure_general_goods_catalog(session, countries, manifest)
        assert product.image == "products/admin-uploaded-phone-case.png"

        product.image = None
        _ensure_general_goods_catalog(session, countries, manifest)
        assert product.image == "products/revised-seed-phone-case.webp"


def test_legacy_sync_does_not_replace_existing_admin_media(tmp_path) -> None:
    legacy_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(legacy_path)
    connection.executescript(
        """
        CREATE TABLE catalog_category (id INTEGER, name TEXT, slug TEXT);
        CREATE TABLE catalog_product (
            id INTEGER,
            name TEXT,
            slug TEXT,
            model TEXT,
            description TEXT,
            category_id INTEGER,
            image TEXT,
            image_url TEXT
        );
        CREATE TABLE catalog_productvariant (
            id INTEGER,
            sku TEXT,
            variant_name TEXT,
            weight_kg NUMERIC,
            length_cm NUMERIC,
            width_cm NUMERIC,
            height_cm NUMERIC,
            product_id INTEGER
        );
        INSERT INTO catalog_category VALUES (1, 'Mobile Accessories', 'mobile-accessories');
        INSERT INTO catalog_product VALUES (
            1,
            'Updated Phone Case',
            'protective-phone-case',
            'CASE-2',
            'Updated legacy description',
            1,
            '',
            'https://legacy.example.test/replace-me.webp'
        );
        """
    )
    connection.commit()
    connection.close()

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        category = Category(
            name="Mobile Accessories",
            slug="mobile-accessories",
        )
        product = Product(
            name="Protective Phone Case",
            slug="protective-phone-case",
            model="CASE-1",
            image="products/admin-uploaded-phone-case.webp",
            category=category,
        )
        session.add(product)
        session.flush()

        assert _import_legacy_catalog(session, legacy_path) is True
        assert product.name == "Updated Phone Case"
        assert product.image == "products/admin-uploaded-phone-case.webp"


@pytest.mark.parametrize(
    "image",
    (
        "https://images.example.test/product.webp",
        "../products/product.webp",
        "products/product.svg",
        "other/product.webp",
    ),
)
def test_manifest_rejects_non_owned_or_unsupported_product_images(
    tmp_path,
    image: str,
) -> None:
    manifest = _load_general_goods_manifest()
    manifest["categories"][0]["products"][0]["image"] = image
    path = tmp_path / "invalid-catalog.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError, match="owned relative product image path"):
        _load_general_goods_manifest(path)


@pytest.mark.parametrize(
    ("stored_image", "expected_url", "expected_kind"),
    (
        ("products/phone-case.webp", "/media/products/phone-case.webp", "owned"),
        (
            "products/illustrative/phone-case.webp",
            "/media/products/illustrative/phone-case.webp",
            "illustrative",
        ),
        (
            "https://cdn.example.test/phone-case.webp",
            "https://cdn.example.test/phone-case.webp",
            "external",
        ),
        (None, None, "fallback"),
    ),
)
def test_public_product_api_exposes_consistent_image_metadata(
    stored_image: str | None,
    expected_url: str | None,
    expected_kind: str,
) -> None:
    category = Category(id=1, name="Mobile Accessories", slug="mobile-accessories")
    product = Product(
        id=1,
        name="Protective Phone Case",
        slug="protective-phone-case",
        image=stored_image,
        category=category,
    )

    payload = serialize_product(product)

    assert payload["image"] == expected_url
    assert payload["image_metadata"] == {
        "url": expected_url,
        "alt": "Protective Phone Case",
        "kind": expected_kind,
        "credit": None,
    }


def test_priority_media_manifest_references_identical_runtime_assets() -> None:
    manifest = _load_general_goods_manifest()
    products = [
        product
        for category in manifest["categories"]
        for product in category["products"]
    ]

    assert len(products) == 140
    for product in products:
        relative_path = Path(str(product["image"]))
        api_asset = REPOSITORY_ROOT / "services" / "catalog-service" / "media" / relative_path
        web_asset = REPOSITORY_ROOT / "apps" / "web-next" / "public" / "media" / relative_path

        assert api_asset.is_file(), product["slug"]
        assert web_asset.is_file(), product["slug"]
        assert api_asset.read_bytes() == web_asset.read_bytes(), product["slug"]
