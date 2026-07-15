from __future__ import annotations

import csv
import re
import sqlite3
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Category,
    Country,
    CurrencyRate,
    ETARule,
    Product,
    ProductVariant,
    Seller,
    SellerOffer,
    ServiceFeeRule,
    ShippingRateCard,
)


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


def _ensure_reference_data(session: Session) -> dict[str, Country]:
    countries = {
        country.code: country
        for country in session.scalars(select(Country).where(Country.code.in_(["CN", "SG", "TH", "IN"]))).all()
    }

    for code, name in [("CN", "China"), ("SG", "Singapore"), ("TH", "Thailand"), ("IN", "India")]:
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

    shipping_cards = [
        ("CN", "AIR", "0.000", "0.999", "580.00"),
        ("CN", "AIR", "1.000", "4.999", "1450.00"),
        ("CN", "SEA", "0.000", "9.999", "980.00"),
        ("CN", "SEA", "10.000", "49.999", "2800.00"),
        ("SG", "AIR", "0.000", "0.999", "720.00"),
        ("SG", "AIR", "1.000", "4.999", "1680.00"),
        ("TH", "AIR", "0.000", "0.999", "690.00"),
        ("TH", "SEA", "0.000", "9.999", "1180.00"),
        ("IN", "AIR", "0.000", "0.999", "650.00"),
        ("IN", "AIR", "1.000", "4.999", "1550.00"),
        ("IN", "SEA", "0.000", "9.999", "1080.00"),
        ("IN", "SEA", "10.000", "49.999", "3050.00"),
    ]
    for country_code, method, min_kg, max_kg, cost in shipping_cards:
        exists = session.scalar(
            select(ShippingRateCard.id).where(
                ShippingRateCard.country_id == countries[country_code].id,
                ShippingRateCard.method == method,
                ShippingRateCard.min_kg == Decimal(min_kg),
                ShippingRateCard.max_kg == Decimal(max_kg),
            )
        )
        if not exists:
            session.add(
                ShippingRateCard(
                    country=countries[country_code],
                    method=method,
                    min_kg=Decimal(min_kg),
                    max_kg=Decimal(max_kg),
                    cost_bdt=Decimal(cost),
                )
            )

    eta_rules = [
        ("CN", "LOCAL", "DOOR", 7, 12),
        ("CN", "LOCAL", "PICKUP", 5, 9),
        ("CN", "BULK", "DOOR", 18, 28),
        ("CN", "BULK", "PICKUP", 15, 24),
        ("SG", "LOCAL", "DOOR", 5, 8),
        ("SG", "LOCAL", "PICKUP", 4, 6),
        ("TH", "LOCAL", "DOOR", 6, 10),
        ("TH", "BULK", "DOOR", 14, 22),
        ("IN", "LOCAL", "DOOR", 5, 9),
        ("IN", "LOCAL", "PICKUP", 4, 7),
        ("IN", "BULK", "DOOR", 12, 20),
        ("IN", "BULK", "PICKUP", 10, 18),
    ]
    for country_code, mode, delivery_type, min_days, max_days in eta_rules:
        exists = session.scalar(
            select(ETARule.id).where(
                ETARule.country_id == countries[country_code].id,
                ETARule.mode == mode,
                ETARule.delivery_type == delivery_type,
            )
        )
        if not exists:
            session.add(
                ETARule(
                    country=countries[country_code],
                    mode=mode,
                    delivery_type=delivery_type,
                    min_days=min_days,
                    max_days=max_days,
                )
            )

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


def _import_legacy_catalog(session: Session, sqlite_path: Path) -> bool:
    """Idempotently sync the legacy catalog, preferring its populated image_url field."""
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
            product.image = image
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
) -> None:
    has_products = session.scalar(select(Product.id).limit(1))

    if not has_products:
        imported = _import_legacy_catalog(session, legacy_sqlite_path) if legacy_sqlite_path else False
        if not imported:
            _seed_demo_catalog(session)

    # Legacy data can grow after the rebuild DB is first created, so keep it synchronized.
    if legacy_sqlite_path and has_products:
        _import_legacy_catalog(session, legacy_sqlite_path)

    session.flush()
    countries = _ensure_reference_data(session)
    _ensure_sellers_and_offers(session, countries)
    if legacy_sqlite_path:
        _sync_legacy_offers(session, legacy_sqlite_path)
    if supply_chain_csv_path:
        _ensure_supply_chain_dataset(session, supply_chain_csv_path, countries)
    session.commit()
