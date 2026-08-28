from __future__ import annotations

import re
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.quotes import router as quotes_router
from app.db import get_session
from app.models import (
    AccountUser,
    Base,
    Category,
    Country,
    CustomerAddress,
    CurrencyRate,
    DutyRule,
    Order,
    Product,
    ProductVariant,
    SavedQuote,
    Seller,
    SellerOffer,
    ShippingRateCard,
)
from app.schemas import (
    MAX_DATABASE_INTEGER,
    MAX_QUOTE_QUANTITY,
    CreateOrderIn,
    QuoteRecommendIn,
    QuoteRequestIn,
)
from app.services.orders import create_manual_order_record
from app.services.sourcing import build_quote, recommend_routes


CUSTOMER = {"sub": 1001, "role": "customer"}


class QuoteIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)

        category = Category(name="Office", slug="office")
        product = Product(
            name="Precision Desk Tool",
            slug="precision-desk-tool",
            category=category,
        )
        self.variant = ProductVariant(
            product=product,
            sku="PDT-1",
            variant_name="Standard",
            weight_kg=Decimal("1.000"),
        )
        self.country = Country(code="CN", name="China")
        self.seller = Seller(
            country=self.country,
            name="Integrity Supplier",
            rating=Decimal("4.50"),
        )
        self.offer = SellerOffer(
            id=77,
            variant=self.variant,
            country=self.country,
            seller=self.seller,
            mode="LOCAL",
            price_origin=Decimal("10.01"),
            currency="USD",
            stock=500,
            moq=1,
        )
        self.currency_rate = CurrencyRate(
            currency="USD",
            rate_to_bdt=Decimal("110.1234"),
        )
        shipping_rate = ShippingRateCard(
            country=self.country,
            method="AIR",
            min_kg=Decimal("0.001"),
            max_kg=Decimal("1000.000"),
            cost_bdt=Decimal("123.45"),
        )
        self.duty_rule = DutyRule(
            country=self.country,
            percent=Decimal("5.00"),
            fixed_bdt=Decimal("0.00"),
        )
        user = AccountUser(
            id=CUSTOMER["sub"],
            username="quote-customer",
            email="quote-customer@example.com",
            password_hash="not-used",
            role="customer",
        )
        address = CustomerAddress(
            user_id=CUSTOMER["sub"],
            label="Primary",
            recipient_name="Quote Customer",
            line1="1 Test Road",
            city="Dhaka",
            country_code="BD",
            phone="+8801700000000",
            is_default_shipping=True,
            is_default_billing=True,
        )
        self.session.add_all(
            [
                product,
                self.country,
                self.seller,
                self.offer,
                self.currency_rate,
                shipping_rate,
                self.duty_rule,
                user,
                address,
            ]
        )
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _quote_payload(self, *, qty: int = 1) -> QuoteRequestIn:
        return QuoteRequestIn(
            variant_id=self.variant.id,
            country="CN",
            mode="LOCAL",
            qty=qty,
            delivery_type="DOOR",
        )

    def _order_payload(
        self,
        *,
        offer_id: int | None = None,
        saved_quote_id: int | None = None,
    ) -> CreateOrderIn:
        return CreateOrderIn(
            saved_quote_id=saved_quote_id,
            variant_id=self.variant.id,
            country="CN",
            mode="LOCAL",
            qty=1,
            delivery_type="DOOR",
            offer_id=offer_id,
            trx_id="QUOTE-INTEGRITY-100",
            channel="bKash",
        )

    def test_quote_fails_closed_without_an_eligible_offer(self) -> None:
        self.offer.stock = 0
        self.session.commit()

        with self.assertRaises(HTTPException) as raised:
            build_quote(self.session, self._quote_payload())

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("No eligible active supplier offer", raised.exception.detail)

    def test_quote_fails_closed_when_currency_rate_is_missing(self) -> None:
        self.session.delete(self.currency_rate)
        self.session.commit()

        with self.assertRaises(HTTPException) as raised:
            build_quote(self.session, self._quote_payload())

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("No active BDT exchange rate", raised.exception.detail)

    def test_quote_fails_closed_when_currency_rate_is_inactive(self) -> None:
        self.currency_rate.is_active = False
        self.session.commit()

        with self.assertRaises(HTTPException) as raised:
            build_quote(self.session, self._quote_payload())

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("No active BDT exchange rate", raised.exception.detail)

    def test_quote_fails_closed_when_duty_rule_is_missing(self) -> None:
        self.session.delete(self.duty_rule)
        self.session.commit()

        with self.assertRaises(HTTPException) as raised:
            build_quote(self.session, self._quote_payload())

        self.assertEqual(raised.exception.status_code, 422)
        self.assertIn("No active customs duty rule", raised.exception.detail)

    def test_route_recommendations_use_all_eligible_offer_countries(self) -> None:
        india = Country(code="IN", name="India")
        india_supplier = Seller(
            country=india,
            name="India Eligible Supplier",
            rating=Decimal("4.40"),
        )
        india_offer = SellerOffer(
            variant=self.variant,
            country=india,
            seller=india_supplier,
            mode="LOCAL",
            price_origin=Decimal("9.50"),
            currency="USD",
            stock=100,
            moq=1,
        )
        japan = Country(code="JP", name="Japan")
        self.session.add_all(
            [
                india,
                india_supplier,
                india_offer,
                japan,
                ShippingRateCard(
                    country=india,
                    method="AIR",
                    min_kg=Decimal("0.001"),
                    max_kg=Decimal("1000.000"),
                    cost_bdt=Decimal("100.00"),
                ),
                DutyRule(
                    country=india,
                    percent=Decimal("5.00"),
                    fixed_bdt=Decimal("0.00"),
                ),
            ]
        )
        self.session.commit()

        routes = recommend_routes(
            self.session,
            QuoteRecommendIn(
                variant_id=self.variant.id,
                qty=1,
                delivery_type="DOOR",
                priority="balanced",
            ),
        )

        countries = {route["country"] for route in routes}
        self.assertIn("CN", countries)
        self.assertIn("IN", countries)
        self.assertNotIn("JP", countries)

    def test_all_bdt_fields_are_quantized_and_payment_split_balances(self) -> None:
        result = build_quote(self.session, self._quote_payload())
        breakdown = result["breakdown"]

        self.assertEqual(result["pricing_basis"]["duty_rule_id"], self.duty_rule.id)
        self.assertEqual(result["pricing_basis"]["duty_scope"], "country")

        bdt_values = {
            key: value for key, value in breakdown.items() if key.endswith("_bdt")
        }
        self.assertTrue(bdt_values)
        for key, value in bdt_values.items():
            with self.subTest(key=key):
                self.assertRegex(value, re.compile(r"^\d+\.\d{2}$"))

        total = Decimal(breakdown["total_bdt"])
        advance = Decimal(breakdown["advance_bdt"])
        remaining = Decimal(breakdown["remaining_bdt"])
        self.assertEqual(advance + remaining, total)

    def test_quote_and_recommendation_boundaries_return_422(self) -> None:
        app = FastAPI()
        app.include_router(quotes_router)
        app.dependency_overrides[get_session] = lambda: self.session

        cases = [
            (
                "/api/quote/",
                {
                    "variant_id": self.variant.id,
                    "country": "CN",
                    "mode": "LOCAL",
                    "qty": 1,
                    "delivery_type": "DOOR",
                },
            ),
            (
                "/api/quote/recommend/",
                {
                    "variant_id": self.variant.id,
                    "qty": 1,
                    "delivery_type": "DOOR",
                    "priority": "balanced",
                },
            ),
            (
                "/api/recommendations/cheapest-country/",
                {
                    "variant_id": self.variant.id,
                    "qty": 1,
                    "delivery_type": "DOOR",
                    "priority": "balanced",
                },
            ),
        ]

        with TestClient(app) as client:
            for endpoint, valid_payload in cases:
                invalid_payloads = [
                    {**valid_payload, "variant_id": MAX_DATABASE_INTEGER + 1},
                    {**valid_payload, "qty": MAX_QUOTE_QUANTITY + 1},
                    {**valid_payload, "delivery_type": "DRONE"},
                ]
                for invalid_payload in invalid_payloads:
                    with self.subTest(endpoint=endpoint, payload=invalid_payload):
                        response = client.post(endpoint, json=invalid_payload)
                        self.assertEqual(response.status_code, 422)

    def test_manual_order_requires_the_server_locked_offer(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            create_manual_order_record(
                self.session,
                self._order_payload(offer_id=999),
                CUSTOMER,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("server-generated quote", raised.exception.detail)
        self.assertEqual(self.session.scalar(select(func.count(Order.id))), 0)

    def test_manual_order_requires_default_shipping_and_billing_addresses(self) -> None:
        address = self.session.scalar(select(CustomerAddress))
        address.is_default_billing = False
        self.session.commit()

        with self.assertRaises(HTTPException) as raised:
            create_manual_order_record(
                self.session,
                self._order_payload(),
                CUSTOMER,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("default billing address", raised.exception.detail)
        self.assertEqual(self.session.scalar(select(func.count(Order.id))), 0)

    def test_manual_order_cannot_bypass_missing_offer(self) -> None:
        self.offer.is_active = False
        self.session.commit()

        with self.assertRaises(HTTPException) as raised:
            create_manual_order_record(
                self.session,
                self._order_payload(),
                CUSTOMER,
            )

        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(self.session.scalar(select(func.count(Order.id))), 0)

    def test_saved_quote_order_revalidates_the_locked_offer_route(self) -> None:
        quote_result = build_quote(self.session, self._quote_payload())
        saved_quote = SavedQuote(
            user_id=CUSTOMER["sub"],
            variant_id=self.variant.id,
            product_name=self.variant.product.name,
            variant_name=self.variant.variant_name or "Variant",
            country_code="CN",
            mode="LOCAL",
            delivery_type="DOOR",
            qty=1,
            status="requested",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            response=quote_result,
        )
        self.session.add(saved_quote)
        self.session.commit()

        # A route change makes the originally locked offer ineligible even
        # though its ID, stock and supplier are still otherwise valid.
        self.offer.mode = "BULK"
        self.session.commit()

        with self.assertRaises(HTTPException) as raised:
            create_manual_order_record(
                self.session,
                self._order_payload(
                    offer_id=self.offer.id,
                    saved_quote_id=saved_quote.id,
                ),
                CUSTOMER,
            )

        self.assertEqual(raised.exception.status_code, 409)
        self.assertIn("no longer eligible", raised.exception.detail)
        self.assertEqual(self.session.scalar(select(func.count(Order.id))), 0)


if __name__ == "__main__":
    unittest.main()
