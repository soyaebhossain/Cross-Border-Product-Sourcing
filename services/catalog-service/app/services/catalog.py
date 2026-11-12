from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..models import Category, Country, CurrencyRate, ETARule, Product, ProductVariant, Seller, SellerOffer
from ..supplier_risk import supplier_risk_label


def _literal_contains_pattern(value: str) -> str:
    """Build an escaped SQL LIKE pattern so %, _ and \\ remain literal search text."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_categories(session: Session) -> list[Category]:
    return session.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.name.asc())
    ).all()


def list_countries(session: Session) -> list[Country]:
    return session.scalars(select(Country).order_by(Country.name.asc())).all()


def list_products(session: Session, q: str = "") -> list[Product]:
    query = (
        select(Product)
        .options(
            joinedload(Product.category),
            selectinload(
                Product.variants.and_(ProductVariant.is_active.is_(True))
            ),
        )
        .where(
            Product.is_active.is_(True),
            Product.category.has(Category.is_active.is_(True)),
        )
        .order_by(Product.name.asc())
    )
    if q.strip():
        like = _literal_contains_pattern(q.strip())
        query = query.join(Product.category).where(
            or_(
                Product.name.ilike(like, escape="\\"),
                Product.model.ilike(like, escape="\\"),
                Product.slug.ilike(like, escape="\\"),
                Category.slug.ilike(like, escape="\\"),
                Category.name.ilike(like, escape="\\"),
            )
        )
    return session.scalars(query).unique().all()


def build_market_summaries(
    session: Session,
    products: list[Product],
) -> dict[int, dict[str, object]]:
    ids = [item.id for item in products]
    summaries: dict[int, dict[str, object]] = {
        item.id: {"countries": set(), "supplier_count": 0} for item in products
    }
    if not ids:
        return summaries

    rates = {
        currency.upper(): float(rate)
        for currency, rate in session.execute(
            select(CurrencyRate.currency, CurrencyRate.rate_to_bdt).where(
                CurrencyRate.is_active.is_(True)
            )
        ).all()
    }
    rates["BDT"] = 1.0
    eta_by_lane = {
        (country_id, mode): (int(min_days), int(max_days))
        for country_id, mode, min_days, max_days in session.execute(
            select(ETARule.country_id, ETARule.mode, ETARule.min_days, ETARule.max_days).where(
                ETARule.delivery_type == "DOOR",
                ETARule.is_active.is_(True),
            )
        ).all()
    }
    rows = session.execute(
        select(
            ProductVariant.product_id,
            SellerOffer.price_origin,
            SellerOffer.currency,
            SellerOffer.mode,
            Country.id,
            Country.code,
            Seller.rating,
            SellerOffer.seller_id,
            SellerOffer.moq,
        )
        .join(SellerOffer, SellerOffer.variant_id == ProductVariant.id)
        .join(Country, Country.id == SellerOffer.country_id)
        .join(Seller, Seller.id == SellerOffer.seller_id)
        .where(ProductVariant.product_id.in_(ids))
        .where(
            ProductVariant.is_active.is_(True),
            SellerOffer.is_active.is_(True),
            Seller.is_active.is_(True),
        )
    ).all()
    seller_sets: dict[int, set[int]] = {item_id: set() for item_id in ids}
    for product_id, price, currency, mode, country_id, code, rating, seller_id, moq in rows:
        item = summaries[product_id]
        item["countries"].add(code)
        seller_sets[product_id].add(seller_id)
        amount = float(price)
        score = float(rating or 0)
        # Same defaults as sourcing.eta_range when no ETA rule is configured.
        delivery, delivery_max = eta_by_lane.get(
            (country_id, mode),
            (7, 14) if mode == "LOCAL" else (15, 30),
        )
        normalized_price = amount * rates.get(str(currency).upper(), float("inf"))
        if normalized_price < float(item.get("_min_price_bdt", float("inf"))):
            item["_min_price_bdt"] = normalized_price
            item["min_price"] = amount
            item["currency"] = currency
            if normalized_price != float("inf"):
                item["min_price_bdt"] = round(normalized_price, 2)
        item["max_rating"] = max(float(item.get("max_rating", score)), score)
        # Delivery is the configured range of the fastest lane, never a derived guess.
        if delivery < int(item.get("min_delivery_days", 10**6)):
            item["min_delivery_days"] = delivery
            item["max_delivery_days"] = delivery_max
        item["min_moq"] = min(int(item.get("min_moq", moq)), int(moq))

    for product_id, item in summaries.items():
        item.pop("_min_price_bdt", None)
        item["countries"] = sorted(item["countries"])
        item["supplier_count"] = len(seller_sets[product_id])
        rating = float(item.get("max_rating", 0))
        item["risk_level"] = supplier_risk_label(rating)
        price = float(item.get("min_price", 0))
        delivery = int(item.get("min_delivery_days", 99))
        item["recommended_score"] = round(
            rating * 18
            + max(0, 20 - delivery / 2)
            + (10 if item["risk_level"] == "Low" else 5)
            - min(price / 1000, 10),
            2,
        )
    return summaries


def browse_products(session: Session, q: str = "", category: str = "", page: int = 1,
                    page_size: int = 24, sort: str = "name", country: str = "",
                    min_price: float | None = None, max_price: float | None = None,
                    max_delivery: int | None = None, min_rating: float | None = None,
                    risk: str = "") -> tuple[list[Product], int, dict[int, dict[str, object]]]:
    products = list_products(session, q)
    if category:
        products = [item for item in products if item.category.slug == category]
    summaries = build_market_summaries(session, products)

    def include(product: Product) -> bool:
        item = summaries[product.id]; price = item.get("min_price"); rating = float(item.get("max_rating", 0)); delivery = int(item.get("min_delivery_days", 999))
        return not ((country and country.upper() not in item["countries"]) or (min_price is not None and (price is None or float(price) < min_price)) or
                    (max_price is not None and (price is None or float(price) > max_price)) or (max_delivery is not None and delivery > max_delivery) or
                    (min_rating is not None and rating < min_rating) or (risk and item.get("risk_level", "").lower() != risk.lower()))
    products = [item for item in products if include(item)]
    if sort == "name_desc": products.sort(key=lambda item: item.name.lower(), reverse=True)
    elif sort == "cheapest": products.sort(key=lambda item: float(summaries[item.id].get("min_price", float("inf"))))
    elif sort == "fastest": products.sort(key=lambda item: int(summaries[item.id].get("min_delivery_days", 999)))
    elif sort == "highest_rated": products.sort(key=lambda item: float(summaries[item.id].get("max_rating", 0)), reverse=True)
    elif sort == "recommended": products.sort(key=lambda item: float(summaries[item.id].get("recommended_score", 0)), reverse=True)
    else: products.sort(key=lambda item: item.name.lower())
    total = len(products); start = (page - 1) * page_size
    return products[start:start + page_size], total, summaries


def get_product_by_slug_or_404(session: Session, slug: str) -> Product:
    product = session.scalar(
        select(Product)
        .options(
            joinedload(Product.category),
            selectinload(
                Product.variants.and_(ProductVariant.is_active.is_(True))
            ),
        )
        .where(
            Product.slug == slug,
            Product.is_active.is_(True),
            Product.category.has(Category.is_active.is_(True)),
        )
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def list_sourcing_lanes(session: Session) -> list[dict[str, object]]:
    """Origin countries that have active offers, with their configured door-delivery ETA."""

    counts = session.execute(
        select(
            Country.id,
            Country.code,
            Country.name,
            func.count(SellerOffer.id),
            func.count(func.distinct(ProductVariant.product_id)),
        )
        .join(SellerOffer, SellerOffer.country_id == Country.id)
        .join(ProductVariant, ProductVariant.id == SellerOffer.variant_id)
        .join(Seller, Seller.id == SellerOffer.seller_id)
        .where(SellerOffer.is_active.is_(True), Seller.is_active.is_(True), ProductVariant.is_active.is_(True))
        .group_by(Country.id, Country.code, Country.name)
    ).all()
    eta = {
        country_id: (int(min_days), int(max_days))
        for country_id, min_days, max_days in session.execute(
            select(ETARule.country_id, ETARule.min_days, ETARule.max_days).where(
                ETARule.mode == "LOCAL",
                ETARule.delivery_type == "DOOR",
                ETARule.is_active.is_(True),
            )
        ).all()
    }
    lanes = [
        {
            "code": code,
            "name": name,
            "offers": int(offers),
            "products": int(products),
            "eta_min_days": eta.get(country_id, (None, None))[0],
            "eta_max_days": eta.get(country_id, (None, None))[1],
        }
        for country_id, code, name, offers, products in counts
    ]
    return sorted(lanes, key=lambda lane: (-int(lane["products"]), str(lane["code"])))
