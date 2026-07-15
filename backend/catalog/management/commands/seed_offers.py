"""
Seeds SellerOffer + expands ShippingRateCard for all products without offers.
Prices derived from:
  1. bangladesh_import_demand.csv (best match)
  2. Category-based price table (fallback)
Safe to re-run (skips existing offers per variant+country+mode).
"""
import csv
from decimal import Decimal
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from sourcing.models import Country, Seller, SellerOffer
from shipping.models import ShippingRateCard, ETARule
from catalog.models import Product, ProductVariant

DATA_DIR = Path(settings.BASE_DIR).parent / "Data"

# ── Category baseline prices (USD) when CSV match fails ──────────────────────
CATEGORY_PRICE = {
    "industrial-automation": 280,
    "medical-equipment":     1200,
    "agricultural-tech":     350,
    "clean-energy-ev":       420,
    "scientific-instruments":280,
    "3d-printing-maker":     320,
    "phones":                180,
    "electronics":           120,
    "pc-components":         220,
    "electronic":            80,   # Fan category slug
    "haircare":              8,
    "skincare":              12,
    "cosmetics":             10,
    "default":               150,
}

# ── Country seller map ────────────────────────────────────────────────────────
SELLER_MAP = {
    "CN": "Shenzhen Hub",
    "SG": "Singapore Dist",
    "TH": "Bangkok Sourcing",
}

# CN = base price, SG = +12%, TH = +6%
COUNTRY_MULTIPLIER = {"CN": Decimal("1.00"), "SG": Decimal("1.12"), "TH": Decimal("1.06")}

# ── Additional shipping rate tiers to add ─────────────────────────────────────
EXTRA_SHIPPING = [
    # country_code, method, min_kg, max_kg, cost_bdt
    ("CN", "AIR",  5.0,   25.0,   3500),
    ("CN", "AIR",  25.0,  100.0,  8000),
    ("CN", "AIR",  100.0, 500.0,  22000),
    ("CN", "SEA",  0.0,   5.0,    4500),
    ("CN", "SEA",  100.0, 500.0,  18000),
    ("CN", "SEA",  500.0, 5000.0, 45000),
    ("SG", "AIR",  5.0,   25.0,   4000),
    ("SG", "AIR",  25.0,  100.0,  9000),
    ("SG", "AIR",  100.0, 500.0,  25000),
    ("SG", "SEA",  0.0,   5.0,    5000),
    ("SG", "SEA",  100.0, 500.0,  20000),
    ("SG", "SEA",  500.0, 5000.0, 50000),
    ("TH", "AIR",  5.0,   25.0,   3200),
    ("TH", "AIR",  25.0,  100.0,  7500),
    ("TH", "AIR",  100.0, 500.0,  20000),
    ("TH", "SEA",  0.0,   5.0,    4000),
    ("TH", "SEA",  100.0, 500.0,  17000),
    ("TH", "SEA",  500.0, 5000.0, 42000),
    ("IN", "AIR",  0.0,   5.0,    1200),
    ("IN", "AIR",  5.0,   25.0,   2800),
    ("IN", "AIR",  25.0,  100.0,  6500),
    ("IN", "SEA",  0.0,   5.0,    3500),
    ("IN", "SEA",  5.0,   500.0,  12000),
]

# ── Extra ETA rules for new countries/modes if missing ──────────────────────
EXTRA_ETA = [
    # country_code, mode, delivery_type, min_days, max_days
    ("CN", "LOCAL", "DOOR",   4, 8),
    ("CN", "LOCAL", "PICKUP", 3, 7),
    ("CN", "BULK",  "DOOR",  18, 30),
    ("CN", "BULK",  "PICKUP",16, 28),
    ("SG", "LOCAL", "DOOR",   3, 7),
    ("SG", "LOCAL", "PICKUP", 2, 6),
    ("SG", "BULK",  "DOOR",  16, 28),
    ("SG", "BULK",  "PICKUP",14, 25),
    ("TH", "LOCAL", "DOOR",   4, 8),
    ("TH", "LOCAL", "PICKUP", 3, 7),
    ("TH", "BULK",  "DOOR",  16, 28),
    ("TH", "BULK",  "PICKUP",14, 25),
    ("IN", "LOCAL", "DOOR",   5, 9),
    ("IN", "LOCAL", "PICKUP", 4, 8),
    ("IN", "BULK",  "DOOR",  20, 32),
    ("IN", "BULK",  "PICKUP",18, 30),
]


def _load_demand_csv() -> dict[str, float]:
    """Returns {product_type_lower: avg_price_usd}"""
    path = DATA_DIR / "bangladesh_import_demand.csv"
    result = {}
    if not path.exists():
        return result
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row.get("product_type", "") or "").lower().strip()
            try:
                price = float(row.get("avg_price_usd", 0) or 0)
                if key and price > 0:
                    result[key] = price
            except (ValueError, TypeError):
                pass
    return result


def _best_price(product_name: str, category_slug: str, demand_prices: dict) -> float:
    """Find best price match from demand CSV or category fallback."""
    name_lower = product_name.lower()

    # 1. Exact or substring match in demand CSV
    best_match_price = None
    best_match_len = 0
    for key, price in demand_prices.items():
        # partial match: if any word of key appears in product name
        if any(word in name_lower for word in key.split() if len(word) > 3):
            match_len = sum(1 for word in key.split() if word in name_lower)
            if match_len > best_match_len:
                best_match_len = match_len
                best_match_price = price

    if best_match_price:
        return best_match_price

    # 2. Category fallback
    slug = (category_slug or "").lower()
    for key, price in CATEGORY_PRICE.items():
        if key in slug:
            return float(price)

    return float(CATEGORY_PRICE["default"])


class Command(BaseCommand):
    help = "Seed SellerOffers for all products + expand ShippingRateCard tiers"

    def add_arguments(self, parser):
        parser.add_argument("--overwrite", action="store_true",
                            help="Delete and re-seed all offers (use to fix wrong prices)")

    def handle(self, *args, **options):
        # ── Step 1: Expand shipping rates ────────────────────────────────────
        self.stdout.write("Expanding shipping rate cards...")
        rate_added = 0
        for code, method, min_kg, max_kg, cost in EXTRA_SHIPPING:
            try:
                country = Country.objects.get(code=code)
            except Country.DoesNotExist:
                continue
            _, created = ShippingRateCard.objects.get_or_create(
                country=country,
                method=method,
                min_kg=Decimal(str(min_kg)),
                max_kg=Decimal(str(max_kg)),
                defaults={"cost_bdt": Decimal(str(cost))},
            )
            if created:
                rate_added += 1
        self.stdout.write(self.style.SUCCESS(f"  +{rate_added} shipping rate tiers added"))

        # ── Step 2: Expand ETA rules ─────────────────────────────────────────
        self.stdout.write("Expanding ETA rules...")
        eta_added = 0
        for code, mode, delivery, mn, mx in EXTRA_ETA:
            try:
                country = Country.objects.get(code=code)
            except Country.DoesNotExist:
                continue
            _, created = ETARule.objects.get_or_create(
                country=country,
                mode=mode,
                delivery_type=delivery,
                defaults={"min_days": mn, "max_days": mx},
            )
            if created:
                eta_added += 1
        self.stdout.write(self.style.SUCCESS(f"  +{eta_added} ETA rules added"))

        # ── Step 3: Seed SellerOffers ─────────────────────────────────────────
        self.stdout.write("Seeding seller offers...")
        demand_prices = _load_demand_csv()
        self.stdout.write(f"  CSV entries loaded: {len(demand_prices)}")
        overwrite = options.get("overwrite", False)

        if overwrite:
            # Delete auto-seeded offers for new categories so prices refresh
            new_cat_slugs = [
                "industrial-automation","medical-equipment","agricultural-tech",
                "clean-energy-ev","scientific-instruments","3d-printing-maker",
                "phones","electronics","pc-components","electronic",
                "haircare","skincare","cosmetics",
            ]
            auto_variant_ids = ProductVariant.objects.filter(
                product__category__slug__in=new_cat_slugs
            ).values_list("id", flat=True)
            deleted, _ = SellerOffer.objects.filter(variant_id__in=auto_variant_ids).delete()
            self.stdout.write(f"  Deleted {deleted} stale offers for re-seed")

        # products that have NO offers at all
        products_with_offers = set(
            SellerOffer.objects.values_list("variant__product_id", flat=True).distinct()
        )
        products_needing_offers = (
            Product.objects
            .exclude(id__in=products_with_offers)
            .select_related("category")
            .prefetch_related("variants")
        )

        offer_count = 0
        for product in products_needing_offers:
            variants = list(product.variants.all())
            if not variants:
                self.stdout.write(f"  SKIP {product.name} — no variants")
                continue

            cat_slug = product.category.slug if product.category else ""
            base_price = _best_price(product.name, cat_slug, demand_prices)

            for country_code, seller_name in SELLER_MAP.items():
                try:
                    country = Country.objects.get(code=country_code)
                    seller  = Seller.objects.get(name=seller_name, country=country)
                except (Country.DoesNotExist, Seller.DoesNotExist):
                    continue

                multiplier = COUNTRY_MULTIPLIER.get(country_code, Decimal("1.00"))
                price_usd  = Decimal(str(round(base_price, 2))) * multiplier

                for variant in variants:
                    for mode, moq, stock in [
                        ("LOCAL", 1,  50),
                        ("BULK",  3, 200),
                    ]:
                        # BULK price slightly cheaper per unit
                        bulk_disc = Decimal("1.00") if mode == "LOCAL" else Decimal("0.94")
                        final_price = (price_usd * bulk_disc).quantize(Decimal("0.01"))

                        SellerOffer.objects.get_or_create(
                            variant=variant,
                            country=country,
                            seller=seller,
                            mode=mode,
                            defaults={
                                "price_origin": final_price,
                                "currency": "USD",
                                "stock": stock,
                                "moq": moq,
                            },
                        )
                        offer_count += 1

            self.stdout.write(f"  OFFER {product.name[:50]:<50} base=${base_price:.0f}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone -- {offer_count} offers seeded across {products_needing_offers.count()} products."
        ))
