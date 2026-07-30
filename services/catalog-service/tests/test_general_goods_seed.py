from __future__ import annotations

from collections import Counter
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import (
    Category,
    Country,
    ETARule,
    Product,
    ProductVariant,
    SellerOffer,
    ShippingRateCard,
)
from app.seed import (
    _ensure_general_goods_catalog,
    _ensure_reference_data,
    _load_general_goods_manifest,
    seed_database,
)
from app.services.sourcing import shipping_cost_bdt


EXPECTED_CATEGORIES = {
    "mobile-accessories": ("Mobile Accessories", 12),
    "laptop-pc-accessories": ("Laptop & PC Accessories", 12),
    "educational-academic-tools": ("Educational & Academic Tools", 12),
    "creator-content-tools": ("Creator & Content Tools", 12),
    "ecommerce-packaging-supplies": ("E-commerce Packaging Supplies", 12),
    "home-organization-storage": ("Home Organization & Storage", 12),
    "fashion-accessories": ("Fashion Accessories", 12),
    "beauty-tools-accessories": ("Beauty Tools & Accessories", 12),
    "kitchen-utility-tools": ("Kitchen Utility Tools", 12),
    "office-desk-accessories": ("Office & Desk Accessories", 12),
    "travel-luggage-accessories": ("Travel & Luggage Accessories", 10),
    "pet-care-accessories": ("Pet Care Accessories", 10),
}
NEW_ORIGINS = {"MY", "TR", "VN"}
ALL_ORIGINS = {"CN", "IN", "MY", "SG", "TH", "TR", "VN"}


def _general_goods_rows(session: Session):
    category_slugs = set(EXPECTED_CATEGORIES)
    products = session.scalars(
        select(Product)
        .join(Product.category)
        .where(Category.slug.in_(category_slugs))
        .order_by(Product.model.asc())
    ).all()
    variants = session.scalars(
        select(ProductVariant)
        .join(ProductVariant.product)
        .join(Product.category)
        .where(Category.slug.in_(category_slugs))
        .order_by(ProductVariant.sku.asc())
    ).all()
    variant_ids = [variant.id for variant in variants]
    offers = session.scalars(
        select(SellerOffer)
        .where(SellerOffer.variant_id.in_(variant_ids))
        .order_by(SellerOffer.id.asc())
    ).all()
    return products, variants, offers


def test_general_goods_seed_is_complete_and_idempotent() -> None:
    manifest = _load_general_goods_manifest()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_database(session)

        categories = session.scalars(
            select(Category).where(Category.slug.in_(EXPECTED_CATEGORIES))
        ).all()
        assert {
            category.slug: (
                category.name,
                sum(product.category_id == category.id for product in session.scalars(select(Product)).all()),
            )
            for category in categories
        } == EXPECTED_CATEGORIES

        products, variants, offers = _general_goods_rows(session)
        assert len(products) == 140
        assert len(variants) == 140
        assert len(offers) == 560
        assert len({product.slug for product in products}) == 140
        assert len({product.model for product in products}) == 140
        assert len({variant.sku for variant in variants}) == 140
        assert all(
            product.slug.startswith(f"{product.category.slug}-")
            and "indicative demo values" in (product.description or "")
            for product in products
        )
        assert all(
            Decimal(variant.weight_kg) > 0
            and Decimal(variant.length_cm) > 0
            and Decimal(variant.width_cm) > 0
            and Decimal(variant.height_cm) > 0
            for variant in variants
        )
        assert all(Decimal(offer.price_origin) > 0 and offer.currency == "USD" for offer in offers)
        assert Counter(offer.variant_id for offer in offers) == Counter(
            {variant.id: 4 for variant in variants}
        )
        variants_by_id = {variant.id: variant for variant in variants}
        assert all(
            shipping_cost_bdt(
                session,
                offer.country,
                offer.mode,
                Decimal(variants_by_id[offer.variant_id].weight_kg)
                * Decimal(offer.moq),
            )
            > 0
            and shipping_cost_bdt(
                session,
                offer.country,
                offer.mode,
                Decimal(variants_by_id[offer.variant_id].weight_kg)
                * Decimal(offer.stock),
            )
            > 0
            for offer in offers
        )

        product_spec_by_sku = {
            product["sku"]: product
            for category in manifest["categories"]
            for product in category["products"]
        }
        offers_by_variant: dict[int, list[SellerOffer]] = {}
        for offer in offers:
            offers_by_variant.setdefault(offer.variant_id, []).append(offer)
        for variant in variants:
            origins = product_spec_by_sku[variant.sku]["origins"]
            expected_routes = {
                (origins[0], "LOCAL"),
                (origins[0], "BULK"),
                (origins[1], "LOCAL"),
                (origins[2], "BULK"),
            }
            assert {
                (offer.country.code, offer.mode)
                for offer in offers_by_variant[variant.id]
            } == expected_routes

        for country_code in ALL_ORIGINS:
            country = session.scalar(select(Country).where(Country.code == country_code))
            assert country is not None
            cards = session.scalars(
                select(ShippingRateCard).where(ShippingRateCard.country_id == country.id)
            ).all()
            assert {
                (
                    card.method,
                    Decimal(card.min_kg),
                    Decimal(card.max_kg),
                )
                for card in cards
            } == {
                ("AIR", Decimal("0.000"), Decimal("0.999")),
                ("AIR", Decimal("1.000"), Decimal("4.999")),
                ("SEA", Decimal("0.000"), Decimal("9.999")),
                ("SEA", Decimal("10.000"), Decimal("49.999")),
            }
            assert all(Decimal(card.cost_bdt) > 0 for card in cards)

            eta_rules = session.scalars(
                select(ETARule).where(ETARule.country_id == country.id)
            ).all()
            assert {
                (rule.mode, rule.delivery_type)
                for rule in eta_rules
            } == {
                ("LOCAL", "DOOR"),
                ("LOCAL", "PICKUP"),
                ("BULK", "DOOR"),
                ("BULK", "PICKUP"),
            }
            assert all(rule.min_days > 0 and rule.max_days >= rule.min_days for rule in eta_rules)

        first_counts = (len(products), len(variants), len(offers))
        seed_database(session)
        second_counts = tuple(len(items) for items in _general_goods_rows(session))
        assert first_counts == second_counts == (140, 140, 560)


def test_general_goods_seed_rejects_an_existing_slug_collision() -> None:
    manifest = _load_general_goods_manifest()
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    first_product = manifest["categories"][0]["products"][0]
    with Session(engine) as session:
        countries = _ensure_reference_data(session, manifest["new_origins"])
        manual_category = Category(name="Manual Catalog", slug="manual-catalog")
        session.add(
            Product(
                name="Manual collision",
                slug=first_product["slug"],
                model="MANUAL-001",
                category=manual_category,
            )
        )
        session.flush()

        with pytest.raises(RuntimeError, match="Product slug collision"):
            _ensure_general_goods_catalog(session, countries, manifest)


def test_shipping_cost_scales_large_quantities_and_rejects_missing_method() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        country = Country(code="ZZ", name="Shipping test origin")
        session.add(country)
        session.flush()
        session.add(
            ShippingRateCard(
                country=country,
                method="AIR",
                min_kg=Decimal("0.000"),
                max_kg=Decimal("10.000"),
                cost_bdt=Decimal("100.00"),
            )
        )
        session.flush()

        assert shipping_cost_bdt(session, country, "LOCAL", Decimal("10.000")) == Decimal(
            "100.00"
        )
        assert shipping_cost_bdt(session, country, "LOCAL", Decimal("10.001")) == Decimal(
            "200.00"
        )
        assert shipping_cost_bdt(session, country, "LOCAL", Decimal("25.000")) == Decimal(
            "300.00"
        )
        with pytest.raises(HTTPException, match="No SEA shipping rate"):
            shipping_cost_bdt(session, country, "BULK", Decimal("1.000"))
