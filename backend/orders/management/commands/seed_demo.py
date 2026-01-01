from django.core.management.base import BaseCommand
from decimal import Decimal
from catalog.models import Category, Product, ProductVariant
from sourcing.models import Country, Seller, SellerOffer
from pricing.models import CurrencyRate, ServiceFeeRule
from shipping.models import ShippingRateCard, ETARule


class Command(BaseCommand):
    help = "Seed demo data for CN/SG/TH lanes, rates, and sample electronics products."

    def handle(self, *args, **options):
        self.stdout.write("Seeding demo data...")

        # Countries
        countries = {
            "CN": Country.objects.get_or_create(code="CN", defaults={"name": "China"})[0],
            "SG": Country.objects.get_or_create(code="SG", defaults={"name": "Singapore"})[0],
            "TH": Country.objects.get_or_create(code="TH", defaults={"name": "Thailand"})[0],
        }

        # FX rates (approx)
        CurrencyRate.objects.update_or_create(currency="USD", defaults={"rate_to_bdt": Decimal("120")})
        CurrencyRate.objects.update_or_create(currency="CNY", defaults={"rate_to_bdt": Decimal("16")})
        CurrencyRate.objects.update_or_create(currency="THB", defaults={"rate_to_bdt": Decimal("3.3")})
        CurrencyRate.objects.update_or_create(currency="SGD", defaults={"rate_to_bdt": Decimal("90")})

        # Service fees
        ServiceFeeRule.objects.update_or_create(mode="LOCAL", defaults={"fee_bdt": Decimal("2000"), "percent": Decimal("5")})
        ServiceFeeRule.objects.update_or_create(mode="BULK", defaults={"fee_bdt": Decimal("5000"), "percent": Decimal("3")})

        # Shipping rate cards (rough placeholders)
        for code, min_kg, max_kg, method, cost in [
            ("CN", 0, 5, "AIR", 1500),
            ("CN", 5, 100, "SEA", 9000),
            ("SG", 0, 5, "AIR", 1800),
            ("SG", 5, 100, "SEA", 9500),
            ("TH", 0, 5, "AIR", 1300),
            ("TH", 5, 100, "SEA", 8500),
        ]:
            ShippingRateCard.objects.update_or_create(
                country=countries[code],
                method=method,
                min_kg=Decimal(str(min_kg)),
                max_kg=Decimal(str(max_kg)),
                defaults={"cost_bdt": Decimal(str(cost))},
            )

        # ETA rules
        for code, mode, delivery, min_d, max_d in [
            ("CN", "LOCAL", "DOOR", 4, 8),
            ("CN", "BULK", "DOOR", 10, 18),
            ("SG", "LOCAL", "DOOR", 4, 6),
            ("SG", "BULK", "DOOR", 9, 15),
            ("TH", "LOCAL", "DOOR", 5, 7),
            ("TH", "BULK", "DOOR", 11, 16),
        ]:
            ETARule.objects.update_or_create(
                country=countries[code],
                mode=mode,
                delivery_type=delivery,
                defaults={"min_days": min_d, "max_days": max_d},
            )

        # Categories & products
        electronics = Category.objects.get_or_create(slug="electronics", defaults={"name": "Electronics"})[0]
        phones = Category.objects.get_or_create(slug="phones", defaults={"name": "Phones"})[0]
        pc_parts = Category.objects.get_or_create(slug="pc-components", defaults={"name": "PC Components"})[0]

        p1, _ = Product.objects.get_or_create(
            slug="iphone-14",
            defaults={"name": "iPhone 14", "model": "A2649", "category": phones},
        )
        v1, _ = ProductVariant.objects.get_or_create(
            product=p1,
            variant_name="128GB",
            defaults={"weight_kg": Decimal("0.20"), "length_cm": Decimal("14.7"), "width_cm": Decimal("7.1"), "height_cm": Decimal("0.8")},
        )

        p2, _ = Product.objects.get_or_create(
            slug="rtx-4070",
            defaults={"name": "NVIDIA RTX 4070", "model": "4070-12G", "category": pc_parts},
        )
        v2, _ = ProductVariant.objects.get_or_create(
            product=p2,
            variant_name="Founders Edition",
            defaults={"weight_kg": Decimal("1.1"), "length_cm": Decimal("24.2"), "width_cm": Decimal("11.2"), "height_cm": Decimal("4.2")},
        )

        p3, _ = Product.objects.get_or_create(
            slug="xiaomi-powerbank-20k",
            defaults={"name": "Xiaomi Power Bank 20,000mAh", "model": "PB200ZM", "category": electronics},
        )
        v3, _ = ProductVariant.objects.get_or_create(
            product=p3,
            variant_name="Type-C 22.5W",
            defaults={"weight_kg": Decimal("0.43"), "length_cm": Decimal("15.3"), "width_cm": Decimal("7.3"), "height_cm": Decimal("2.7")},
        )

        # Sellers
        sellers = {
            "cn_main": Seller.objects.get_or_create(country=countries["CN"], name="Shenzhen Hub", defaults={"rating": Decimal("4.8")})[0],
            "sg_dist": Seller.objects.get_or_create(country=countries["SG"], name="Singapore Dist", defaults={"rating": Decimal("4.7")})[0],
            "th_bkk": Seller.objects.get_or_create(country=countries["TH"], name="Bangkok Sourcing", defaults={"rating": Decimal("4.6")})[0],
        }

        # Offers
        for variant, seller, country_code, mode, price, currency, stock, moq in [
            (v1, sellers["cn_main"], "CN", "LOCAL", 500, "USD", 50, 1),
            (v1, sellers["sg_dist"], "SG", "LOCAL", 520, "USD", 30, 1),
            (v2, sellers["cn_main"], "CN", "BULK", 650, "USD", 80, 5),
            (v2, sellers["th_bkk"], "TH", "BULK", 670, "USD", 40, 5),
            (v3, sellers["cn_main"], "CN", "LOCAL", 22, "USD", 200, 5),
            (v3, sellers["th_bkk"], "TH", "LOCAL", 20, "USD", 120, 5),
        ]:
            SellerOffer.objects.update_or_create(
                variant=variant,
                country=countries[country_code],
                seller=seller,
                mode=mode,
                defaults={
                    "price_origin": Decimal(str(price)),
                    "currency": currency,
                    "stock": stock,
                    "moq": moq,
                },
            )

        self.stdout.write(self.style.SUCCESS("Demo data seeded."))
