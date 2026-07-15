from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..models import Category, Country, Product, ProductVariant, Seller, SellerOffer


def list_categories(session: Session) -> list[Category]:
    return session.scalars(select(Category).order_by(Category.name.asc())).all()


def list_countries(session: Session) -> list[Country]:
    return session.scalars(select(Country).order_by(Country.name.asc())).all()


def list_products(session: Session, q: str = "") -> list[Product]:
    query = (
        select(Product)
        .options(joinedload(Product.category), selectinload(Product.variants))
        .order_by(Product.name.asc())
    )
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.join(Product.category).where(
            or_(
                Product.name.ilike(like),
                Product.model.ilike(like),
                Product.slug.ilike(like),
                Category.slug.ilike(like),
                Category.name.ilike(like),
            )
        )
    return session.scalars(query).unique().all()


def browse_products(session: Session, q: str = "", category: str = "", page: int = 1,
                    page_size: int = 24, sort: str = "name", country: str = "",
                    min_price: float | None = None, max_price: float | None = None,
                    max_delivery: int | None = None, min_rating: float | None = None,
                    risk: str = "") -> tuple[list[Product], int, dict[int, dict[str, object]]]:
    products = list_products(session, q)
    if category:
        products = [item for item in products if item.category.slug == category]
    ids = [item.id for item in products]
    summaries: dict[int, dict[str, object]] = {item.id: {"countries": set(), "supplier_count": 0} for item in products}
    if ids:
        rows = session.execute(
            select(ProductVariant.product_id, SellerOffer.price_origin, SellerOffer.currency, SellerOffer.mode,
                   Country.code, Seller.rating, SellerOffer.seller_id)
            .join(SellerOffer, SellerOffer.variant_id == ProductVariant.id)
            .join(Country, Country.id == SellerOffer.country_id)
            .join(Seller, Seller.id == SellerOffer.seller_id)
            .where(ProductVariant.product_id.in_(ids))
        ).all()
        seller_sets: dict[int, set[int]] = {item_id: set() for item_id in ids}
        for product_id, price, currency, mode, code, rating, seller_id in rows:
            item = summaries[product_id]; item["countries"].add(code); seller_sets[product_id].add(seller_id)
            amount = float(price); score = float(rating or 0); delivery = 14 if mode == "LOCAL" else 30
            item["min_price"] = min(float(item.get("min_price", amount)), amount)
            item["currency"] = currency; item["max_rating"] = max(float(item.get("max_rating", score)), score)
            item["min_delivery_days"] = min(int(item.get("min_delivery_days", delivery)), delivery)
        for product_id, item in summaries.items():
            item["countries"] = sorted(item["countries"]); item["supplier_count"] = len(seller_sets[product_id])
            rating = float(item.get("max_rating", 0)); item["risk_level"] = "Low" if rating >= 4.5 else "Medium" if rating >= 3.5 else "High"
            price = float(item.get("min_price", 0)); delivery = int(item.get("min_delivery_days", 99))
            item["recommended_score"] = round(rating * 18 + max(0, 20 - delivery / 2) + (10 if item["risk_level"] == "Low" else 5) - min(price / 1000, 10), 2)

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
        .options(joinedload(Product.category), selectinload(Product.variants))
        .where(Product.slug == slug)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
