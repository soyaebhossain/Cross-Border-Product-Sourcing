from __future__ import annotations

from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Category, Product, ProductVariant, SellerOffer
from app.seed import (
    _ensure_reference_data,
    _ensure_sellers_and_offers,
    _seed_demo_catalog,
    seed_database,
)


def _counts(session: Session) -> tuple[int, int, int, int]:
    return (
        session.scalar(select(func.count(Category.id))) or 0,
        session.scalar(select(func.count(Product.id))) or 0,
        session.scalar(select(func.count(ProductVariant.id))) or 0,
        session.scalar(select(func.count(SellerOffer.id))) or 0,
    )


def test_public_snapshot_seed_converges_and_preserves_managed_rows() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        seed_database(session)
        first_counts = _counts(session)
        assert first_counts[:3] == (27, 610, 610)

        iphone = session.scalar(
            select(Product).where(Product.slug == "iphone-14")
        )
        assert iphone is not None
        assert iphone.image == "products/OIP.webp"
        assert len(iphone.variants) == 1
        reference_offers = session.scalars(
            select(SellerOffer).where(
                SellerOffer.variant_id == iphone.variants[0].id
            )
        ).all()
        assert {offer.mode for offer in reference_offers} == {"LOCAL", "BULK"}
        assert all(
            (offer.source_url or "").startswith(
                "development-reference:public-catalog-snapshot-v2:iphone-14:"
            )
            for offer in reference_offers
        )

        iphone.name = "Operator-managed iPhone listing"
        iphone.model = "MANAGED-MODEL"
        iphone.image = "products/operator-managed.webp"
        reference_offers[0].price_origin = Decimal("123.45")
        iphone.category.name = "Operator-managed phone category"
        session.commit()

        seed_database(session)
        assert _counts(session) == first_counts
        refreshed = session.scalar(
            select(Product).where(Product.slug == "iphone-14")
        )
        assert refreshed is not None
        assert refreshed.name == "Operator-managed iPhone listing"
        assert refreshed.model == "MANAGED-MODEL"
        assert refreshed.image == "products/operator-managed.webp"
        assert refreshed.category.name == "Operator-managed phone category"
        assert session.get(SellerOffer, reference_offers[0].id).price_origin == Decimal(
            "123.45"
        )

    engine.dispose()

def test_existing_untouched_three_product_demo_converges_to_canonical_catalog() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        _seed_demo_catalog(session)
        session.flush()
        countries = _ensure_reference_data(session)
        _ensure_sellers_and_offers(session, countries)
        session.commit()
        assert _counts(session)[:3] == (3, 3, 4)

        seed_database(session)

        assert _counts(session)[:3] == (27, 610, 610)
        assert session.scalar(
            select(Product.id).where(
                Product.slug == "anker-ganprime-735-charger"
            )
        ) is None
        assert session.scalar(
            select(Product.id).where(
                Product.slug == "xiaomi-smart-air-purifier-4-compact"
            )
        ) is None
        assert session.scalar(
            select(Product.id).where(
                Product.slug == "baseus-bowie-h1i-headphones"
            )
        ) is None

    engine.dispose()
