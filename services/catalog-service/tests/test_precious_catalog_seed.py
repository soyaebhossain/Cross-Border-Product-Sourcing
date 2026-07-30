from __future__ import annotations

from collections import Counter
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Category, Product, ProductVariant, SellerOffer
from app.seed import _ensure_precious_catalog, _ensure_reference_data


PRECIOUS_CATEGORY_SLUG = "jewelry-gems-precious-metals"


def test_precious_catalog_seed_is_complete_and_idempotent() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        countries = _ensure_reference_data(session)
        _ensure_precious_catalog(session, countries)
        session.commit()

        category = session.scalar(
            select(Category).where(Category.slug == PRECIOUS_CATEGORY_SLUG)
        )
        assert category is not None
        assert category.name == "Jewelry, Gems & Precious Metals"

        products = session.scalars(
            select(Product)
            .where(Product.category_id == category.id)
            .order_by(Product.model)
        ).all()
        assert len(products) == 60
        assert len({product.slug.casefold() for product in products}) == 60
        assert {"Gold Bullion Bar", "Silver Bullion Coin", "Round-Cut Diamond Stone"} <= {
            product.name for product in products
        }
        assert all("indicative demo values" in (product.description or "") for product in products)

        product_ids = [product.id for product in products]
        variants = session.scalars(
            select(ProductVariant).where(ProductVariant.product_id.in_(product_ids))
        ).all()
        assert len(variants) == 60
        assert len({variant.sku for variant in variants}) == 60
        assert all((variant.sku or "").startswith("JPM-") for variant in variants)
        assert any("purity" in (variant.variant_name or "") for variant in variants)
        assert any("certificate" in (variant.variant_name or "") for variant in variants)

        variant_ids = [variant.id for variant in variants]
        offers = session.scalars(
            select(SellerOffer).where(SellerOffer.variant_id.in_(variant_ids))
        ).all()
        assert len(offers) == 240
        assert set(Counter(offer.variant_id for offer in offers).values()) == {4}
        assert len({offer.seller_id for offer in offers}) == 3
        assert len({offer.country_id for offer in offers}) == 3
        assert all(offer.price_origin > Decimal("0") for offer in offers)

        initial_counts = (
            session.scalar(select(func.count(Category.id))),
            session.scalar(select(func.count(Product.id))),
            session.scalar(select(func.count(ProductVariant.id))),
            session.scalar(select(func.count(SellerOffer.id))),
        )

        countries = _ensure_reference_data(session)
        _ensure_precious_catalog(session, countries)
        session.commit()

        repeated_counts = (
            session.scalar(select(func.count(Category.id))),
            session.scalar(select(func.count(Product.id))),
            session.scalar(select(func.count(ProductVariant.id))),
            session.scalar(select(func.count(SellerOffer.id))),
        )
        assert repeated_counts == initial_counts

    engine.dispose()
