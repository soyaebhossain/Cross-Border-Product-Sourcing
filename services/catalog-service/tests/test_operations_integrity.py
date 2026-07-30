from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.routes.admin import list_admin_audit_events, list_admin_payments, overview
from app.models import (
    AccountUser,
    AdminAuditEvent,
    Base,
    Category,
    Country,
    ManualPaymentProof,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductVariant,
    SavedQuote,
    Seller,
    SellerOffer,
    Shipment,
)
from app.schema_upgrade import upgrade_sqlite_schema
from app.schemas import AdminPaymentDecisionIn, CreateOrderIn, UpdateOrderStatusIn
from app.services.orders import (
    create_manual_order_record,
    decide_manual_payment_record,
    update_order_status_record,
)


ADMIN = {"sub": 9001, "role": "admin"}
CUSTOMER = {"sub": 1001, "role": "customer"}


class OperationsIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine, expire_on_commit=False)
        self.category = Category(name="Medical", slug="medical")
        self.product = Product(
            name="Portable Monitor",
            slug="portable-monitor",
            model="PM-1",
            category=self.category,
        )
        self.variant = ProductVariant(
            product=self.product,
            sku="PM-1-A",
            variant_name="Standard",
            weight_kg=Decimal("1.000"),
        )
        self.user = AccountUser(
            id=CUSTOMER["sub"],
            username="customer",
            email="customer@example.com",
            password_hash="not-used",
            role="customer",
        )
        self.country = Country(code="CN", name="China")
        self.seller = Seller(
            country=self.country,
            name="Test Supplier",
            rating=Decimal("4.50"),
        )
        self.offer = SellerOffer(
            id=77,
            variant=self.variant,
            country=self.country,
            seller=self.seller,
            mode="LOCAL",
            price_origin=Decimal("10.00"),
            currency="USD",
            stock=100,
            moq=1,
        )
        self.session.add_all([self.product, self.user, self.country, self.seller, self.offer])
        self.session.commit()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def _quote(self, *, expired: bool = False) -> SavedQuote:
        expires_at = datetime.now(timezone.utc) + (
            timedelta(days=-1) if expired else timedelta(days=7)
        )
        quote = SavedQuote(
            user_id=CUSTOMER["sub"],
            variant_id=self.variant.id,
            product_name=self.product.name,
            variant_name=self.variant.variant_name or "Variant",
            country_code="CN",
            mode="LOCAL",
            delivery_type="DOOR",
            qty=2,
            status="requested",
            expires_at=expires_at,
            response={
                "status": "requested",
                "expires_at": expires_at.isoformat(),
                "selected_offer_id": 77,
                "breakdown": {
                    "total_bdt": "1000.00",
                    "shipping_bdt": "100.00",
                    "advance_bdt": "600.00",
                    "remaining_bdt": "400.00",
                },
            },
        )
        self.session.add(quote)
        self.session.commit()
        return quote

    def _payload(
        self,
        quote: SavedQuote,
        *,
        trx_id: str = "TXN-100",
        idempotency_key: str = "checkout-attempt-100",
    ) -> CreateOrderIn:
        return CreateOrderIn(
            saved_quote_id=quote.id,
            variant_id=quote.variant_id,
            country=quote.country_code,
            mode=quote.mode,
            qty=quote.qty,
            delivery_type=quote.delivery_type,
            offer_id=77,
            idempotency_key=idempotency_key,
            trx_id=trx_id,
            channel="bKash",
        )

    def _raw_order(self, index: int = 1) -> Order:
        order = Order(
            user_id=CUSTOMER["sub"],
            country_code="CN",
            mode="LOCAL",
            delivery_type="DOOR",
            status="PENDING",
            total_bdt=Decimal("1000.00"),
            shipping_bdt=Decimal("100.00"),
            advance_bdt=Decimal("600.00"),
            remaining_bdt=Decimal("400.00"),
            quote_snapshot={"test": True},
        )
        order.items.append(
            OrderItem(
                variant_id=self.variant.id,
                product_name=self.product.name,
                variant_name="Standard",
                qty=1,
            )
        )
        order.manual_payment = ManualPaymentProof(
            channel="bKash",
            trx_id=f"TX-{index:04d}",
            trx_normalized=f"tx{index:04d}",
            decision="PENDING",
            verified=False,
        )
        order.history.append(OrderStatusHistory(status="PENDING", note="Created"))
        order.shipment = Shipment()
        self.session.add(order)
        self.session.commit()
        return order

    def test_saved_quote_checkout_is_immutable_and_idempotent(self) -> None:
        quote = self._quote()
        payload = self._payload(quote)
        order, replayed = create_manual_order_record(self.session, payload, CUSTOMER)
        self.assertFalse(replayed)
        self.assertEqual(order.saved_quote_id, quote.id)
        self.assertEqual(order.total_bdt, Decimal("1000.00"))
        self.assertEqual(order.quote_snapshot["response"]["breakdown"]["total_bdt"], "1000.00")

        same_order, replayed = create_manual_order_record(self.session, payload, CUSTOMER)
        self.assertTrue(replayed)
        self.assertEqual(same_order.id, order.id)

        duplicate_payload = self._payload(
            quote,
            trx_id="TXN 100",
            idempotency_key="checkout-attempt-200",
        )
        with self.assertRaises(HTTPException) as raised:
            create_manual_order_record(self.session, duplicate_payload, CUSTOMER)
        self.assertEqual(raised.exception.status_code, 409)

    def test_expired_saved_quote_cannot_create_order(self) -> None:
        quote = self._quote(expired=True)
        with self.assertRaises(HTTPException) as raised:
            create_manual_order_record(self.session, self._payload(quote), CUSTOMER)
        self.assertEqual(raised.exception.status_code, 409)
        self.session.refresh(quote)
        self.assertEqual(quote.status, "expired")

    def test_payment_decision_and_status_transitions_are_audited(self) -> None:
        order = self._raw_order()
        approved = decide_manual_payment_record(
            self.session,
            order.id,
            AdminPaymentDecisionIn(decision="APPROVED", note="Matched settlement"),
            ADMIN,
        )
        self.assertEqual(approved.status, "CONFIRMED")
        self.assertTrue(approved.manual_payment.verified)
        self.assertEqual(approved.manual_payment.decision, "APPROVED")

        with self.assertRaises(HTTPException):
            update_order_status_record(
                self.session,
                order.id,
                UpdateOrderStatusIn(status="DELIVERED", note="Invalid jump"),
                ADMIN,
            )

        purchased = update_order_status_record(
            self.session,
            order.id,
            UpdateOrderStatusIn(status="PURCHASED", note="Supplier purchase complete"),
            ADMIN,
        )
        self.assertEqual(purchased.status, "PURCHASED")
        with self.assertRaises(HTTPException):
            update_order_status_record(
                self.session,
                order.id,
                UpdateOrderStatusIn(status="IN_TRANSIT", note="Handed to carrier"),
                ADMIN,
            )
        in_transit = update_order_status_record(
            self.session,
            order.id,
            UpdateOrderStatusIn(
                status="IN_TRANSIT",
                note="Handed to carrier",
                tracking_number="TRACK-100",
            ),
            ADMIN,
        )
        self.assertEqual(in_transit.shipment.tracking_number, "TRACK-100")
        actions = self.session.scalars(
            select(AdminAuditEvent.action).order_by(AdminAuditEvent.id)
        ).all()
        self.assertEqual(
            actions,
            ["payment.approved", "order.status_changed", "order.status_changed"],
        )
        searched_audit = list_admin_audit_events(
            page=1,
            page_size=25,
            action=None,
            entity_type=None,
            actor_user_id=None,
            q="supplier purchase",
            session=self.session,
            user=ADMIN,
        )
        self.assertEqual(searched_audit["total"], 1)
        self.assertEqual(searched_audit["items"][0]["action"], "order.status_changed")

    def test_pending_payment_queue_is_paginated_without_recent_order_cap(self) -> None:
        for index in range(1, 16):
            self._raw_order(index)
        first = list_admin_payments(
            page=1,
            page_size=10,
            decision="PENDING",
            channel=None,
            q="",
            session=self.session,
            user=ADMIN,
        )
        second = list_admin_payments(
            page=2,
            page_size=10,
            decision="PENDING",
            channel=None,
            q="",
            session=self.session,
            user=ADMIN,
        )
        self.assertEqual(first["total"], 15)
        self.assertEqual(len(first["items"]), 10)
        self.assertEqual(len(second["items"]), 5)

        dashboard = overview(
            date_from=date.today() - timedelta(days=1),
            date_to=date.today(),
            timezone_name="UTC",
            status=None,
            country=None,
            mode=None,
            compare=True,
            session=self.session,
            user=ADMIN,
        )
        self.assertEqual(dashboard["payment_queue_total"], 15)
        self.assertEqual(len(dashboard["payment_queue"]), 12)
        self.assertIn("comparison", dashboard)
        self.assertIn("range", dashboard)


class SQLiteUpgradeTests(unittest.TestCase):
    def test_additive_upgrade_preserves_legacy_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.sqlite3"
            engine = create_engine(f"sqlite:///{path.as_posix()}")
            with engine.begin() as connection:
                connection.execute(
                    text(
                        """
                        CREATE TABLE orders_saved_quotes (
                            id INTEGER PRIMARY KEY,
                            response JSON NOT NULL,
                            created_at DATETIME
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE orders_orders (
                            id INTEGER PRIMARY KEY,
                            user_id INTEGER NOT NULL,
                            status VARCHAR(20),
                            created_at DATETIME
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        CREATE TABLE orders_manual_payments (
                            id INTEGER PRIMARY KEY,
                            order_id INTEGER NOT NULL,
                            channel VARCHAR(20),
                            trx_id VARCHAR(80),
                            verified BOOLEAN,
                            verified_at DATETIME,
                            created_at DATETIME
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO orders_orders (id, user_id, status, created_at)
                        VALUES (1, 5, 'PENDING', CURRENT_TIMESTAMP)
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO orders_manual_payments
                            (id, order_id, channel, trx_id, verified, created_at)
                        VALUES (1, 1, 'bKash', 'TX-001', 0, CURRENT_TIMESTAMP)
                        """
                    )
                )

            upgrade_sqlite_schema(engine)
            with engine.connect() as connection:
                order_count = connection.scalar(text("SELECT count(*) FROM orders_orders"))
                normalized = connection.scalar(
                    text("SELECT trx_normalized FROM orders_manual_payments WHERE id = 1")
                )
            self.assertEqual(order_count, 1)
            self.assertEqual(normalized, "tx001")
            self.assertIn("saved_quote_id", {item["name"] for item in inspect(engine).get_columns("orders_orders")})
            self.assertTrue(inspect(engine).has_table("admin_audit_events"))
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
