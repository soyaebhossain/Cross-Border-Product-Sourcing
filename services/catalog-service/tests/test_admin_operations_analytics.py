from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.admin_schemas import (
    ArchiveIn,
    PaymentReversalIn,
    RefundCreateIn,
    RefundReverseIn,
)
from app.api.routes.admin_analytics import (
    analytics_overview,
    profitability_analytics,
    supplier_analytics,
)
from app.api.routes.admin_operations import archive_product
from app.db import Base
from app.models import (
    AccountUser,
    AdminAuditEvent,
    Category,
    Country,
    CurrencyRate,
    ETARule,
    ManualPaymentProof,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ProductVariant,
    Seller,
    SellerOffer,
    ServiceFeeRule,
    ShippingRateCard,
)
from app.schemas import CreateOrderIn, SaveQuoteIn, UpdateOrderStatusIn
from app.security import request_id_context
from app.services.catalog import list_products
from app.services.financial_operations import (
    create_refund,
    financial_snapshot,
    reverse_payment,
    reverse_refund,
)
from app.services.orders import (
    create_manual_order_record,
    save_quote_record,
    update_order_status_record,
)
from app.services.sourcing import get_variant_or_404


ADMIN = {"sub": 1, "role": "admin"}
CUSTOMER = {"sub": 2, "role": "customer"}


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as database_session:
        admin = AccountUser(
            id=1,
            username="operations-admin",
            email="admin@example.test",
            password_hash="not-used",
            role="admin",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        customer = AccountUser(
            id=2,
            username="buyer",
            email="buyer@example.test",
            password_hash="not-used",
            role="customer",
            is_active=True,
        )
        category = Category(name="Medical", slug="medical")
        product = Product(name="Monitor", slug="monitor", category=category)
        variant = ProductVariant(
            product=product,
            sku="MON-1",
            variant_name="Standard",
            weight_kg=Decimal("1.000"),
        )
        country = Country(code="CN", name="China")
        supplier = Seller(
            country=country,
            name="Clinical Supply",
            rating=Decimal("4.70"),
        )
        offer = SellerOffer(
            variant=variant,
            country=country,
            seller=supplier,
            mode="LOCAL",
            price_origin=Decimal("10.00"),
            currency="USD",
            stock=100,
            moq=1,
        )
        database_session.add_all(
            [
                admin,
                customer,
                category,
                product,
                variant,
                country,
                supplier,
                offer,
                CurrencyRate(currency="USD", rate_to_bdt=Decimal("100.0000")),
                ServiceFeeRule(
                    mode="LOCAL",
                    fee_bdt=Decimal("0.00"),
                    percent=Decimal("0.00"),
                ),
                ShippingRateCard(
                    country=country,
                    method="AIR",
                    min_kg=Decimal("0.000"),
                    max_kg=Decimal("10.000"),
                    cost_bdt=Decimal("100.00"),
                ),
                ETARule(
                    country=country,
                    mode="LOCAL",
                    delivery_type="DOOR",
                    min_days=5,
                    max_days=7,
                ),
            ]
        )
        database_session.commit()
        yield database_session
    engine.dispose()


def _raw_order(session: Session, *, delivered: bool = False) -> Order:
    variant = session.scalar(select(ProductVariant))
    offer = session.scalar(select(SellerOffer))
    now = datetime.now(timezone.utc)
    order = Order(
        user_id=2,
        country_code="CN",
        mode="LOCAL",
        delivery_type="DOOR",
        status="DELIVERED" if delivered else "CONFIRMED",
        total_bdt=Decimal("1000.00"),
        shipping_bdt=Decimal("100.00"),
        advance_bdt=Decimal("600.00"),
        remaining_bdt=Decimal("400.00"),
        quote_snapshot={"test": True},
        actual_cost_bdt=Decimal("700.00") if delivered else None,
        promised_delivery_at=now - timedelta(days=1),
        delivered_at=now if delivered else None,
        quality_defect_reported=delivered,
    )
    order.items.append(
        OrderItem(
            variant_id=variant.id,
            offer_id=offer.id,
            product_name="Monitor",
            variant_name="Standard",
            qty=1,
        )
    )
    order.manual_payment = ManualPaymentProof(
        channel="bKash",
        trx_id=f"TX-{id(order)}",
        trx_normalized=f"tx{id(order)}",
        decision="APPROVED",
        verified=True,
        verified_at=now,
        decided_at=now,
        decided_by_user_id=1,
    )
    order.history.append(
        OrderStatusHistory(
            previous_status="PENDING",
            status=order.status,
            note="Approved for test",
            actor_user_id=1,
            actor_role="admin",
            request_id="req-fixture",
        )
    )
    session.add(order)
    session.commit()
    return order


def test_refund_reversal_and_payment_reversal_recompute_financials(session: Session) -> None:
    order = _raw_order(session)
    token = request_id_context.set("req-refund-flow")
    try:
        refund = create_refund(
            session,
            order.id,
            RefundCreateIn(amount_bdt=Decimal("100.00"), reason="Customer cancellation"),
            ADMIN,
        )
        assert refund.transaction_id.startswith("RFN-")
        assert financial_snapshot(session, order) == {
            "gross_collected_bdt": "600.00",
            "refunds_bdt": "100.00",
            "net_verified_cash_bdt": "500.00",
            "outstanding_bdt": "500.00",
        }
        with pytest.raises(HTTPException, match="exceeds refundable"):
            create_refund(
                session,
                order.id,
                RefundCreateIn(amount_bdt=Decimal("501.00"), reason="Too much"),
                ADMIN,
            )

        reverse_refund(
            session,
            refund.id,
            RefundReverseIn(note="Refund transfer failed"),
            ADMIN,
        )
        assert financial_snapshot(session, order)["net_verified_cash_bdt"] == "600.00"

        refreshed_order, reversal = reverse_payment(
            session,
            order.manual_payment.id,
            PaymentReversalIn(note="Bank verification was incorrect"),
            ADMIN,
        )
        assert reversal.transaction_id.startswith("REV-")
        assert refreshed_order.status == "PENDING"
        assert refreshed_order.manual_payment.decision == "REVERSED"
        assert financial_snapshot(session, refreshed_order)["outstanding_bdt"] == "1000.00"
    finally:
        request_id_context.reset(token)

    events = session.scalars(
        select(AdminAuditEvent).order_by(AdminAuditEvent.id.asc())
    ).all()
    assert [event.action for event in events] == [
        "refund.posted",
        "refund.reversed",
        "payment.reversed",
    ]
    assert {event.request_id for event in events} == {"req-refund-flow"}


def test_saved_quote_price_is_server_owned_and_quote_orders_are_unique(session: Session) -> None:
    variant = session.scalar(select(ProductVariant))
    quote = save_quote_record(
        session,
        SaveQuoteIn(
            variant_id=variant.id,
            country="CN",
            mode="LOCAL",
            qty=1,
            delivery_type="DOOR",
            response={"breakdown": {"total_bdt": "1.00"}},
        ),
        CUSTOMER,
    )
    assert quote.response["breakdown"]["total_bdt"] != "1.00"
    payload = CreateOrderIn(
        variant_id=variant.id,
        country="CN",
        mode="LOCAL",
        qty=1,
        delivery_type="DOOR",
        saved_quote_id=quote.id,
        idempotency_key="quote-order-100",
        trx_id="UNIQUE-QUOTE-100",
        channel="bKash",
    )
    order, replayed = create_manual_order_record(session, payload, CUSTOMER)
    assert replayed is False
    same, replayed = create_manual_order_record(session, payload, CUSTOMER)
    assert replayed is True
    assert same.id == order.id

    duplicate = payload.model_copy(
        update={
            "idempotency_key": "quote-order-200",
            "trx_id": "UNIQUE-QUOTE-200",
        }
    )
    with pytest.raises(HTTPException, match="already linked"):
        create_manual_order_record(session, duplicate, CUSTOMER)


def test_soft_archive_hides_product_and_variant_from_public_sourcing(session: Session) -> None:
    product = session.scalar(select(Product))
    variant = session.scalar(select(ProductVariant))
    assert [item.id for item in list_products(session)] == [product.id]

    archive_product(
        product.id,
        ArchiveIn(archived=True, note="Seasonal catalog retirement"),
        session,
        ADMIN,
    )
    assert list_products(session) == []
    with pytest.raises(HTTPException) as raised:
        get_variant_or_404(session, variant.id)
    assert raised.value.status_code == 404


def test_state_transition_requires_note_and_records_actor_request_id(session: Session) -> None:
    order = _raw_order(session)
    with pytest.raises(ValueError, match="operational note"):
        UpdateOrderStatusIn(status="PURCHASED")
    updated = update_order_status_record(
        session,
        order.id,
        UpdateOrderStatusIn(
            status="PURCHASED",
            note="Supplier purchase completed",
            request_id="req-transition",
        ),
        ADMIN,
    )
    history = updated.history[-1]
    assert history.previous_status == "CONFIRMED"
    assert history.status == "PURCHASED"
    assert history.actor_user_id == 1
    assert history.actor_role == "admin"
    assert history.request_id == "req-transition"


def test_sql_analytics_refunds_delivery_supplier_sla_and_profitability(session: Session) -> None:
    order = _raw_order(session, delivered=True)
    create_refund(
        session,
        order.id,
        RefundCreateIn(amount_bdt=Decimal("50.00"), reason="Partial goodwill refund"),
        ADMIN,
    )
    today = date.today()
    dashboard = analytics_overview(
        date_from=today - timedelta(days=1),
        date_to=today,
        days=None,
        timezone_name="UTC",
        status=None,
        country=None,
        mode=None,
        compare=True,
        session=session,
        user=ADMIN,
    )
    assert dashboard["cards"]["gross_order_value_bdt"] == "1000.00"
    assert dashboard["cards"]["verified_cash_bdt"] == "550.00"
    assert dashboard["cards"]["refunds_bdt"] == "50.00"
    assert dashboard["cards"]["realized_margin_bdt"] == "300.00"
    assert dashboard["delivery"]["delivered_late"] == 1
    assert dashboard["supplier_performance"][0]["defect_rate_pct"] == 100.0
    assert dashboard["supplier_performance"][0]["sla_pct"] == 0.0
    assert dashboard["data_last_updated_at"] is not None
    assert dashboard["metric_definitions"]["realized_margin_bdt"]

    suppliers = supplier_analytics(
        date_from=today - timedelta(days=1),
        date_to=today,
        days=None,
        timezone_name="UTC",
        country=None,
        mode=None,
        page=1,
        page_size=25,
        session=session,
        user=ADMIN,
    )
    assert suppliers["total"] == 1
    profitability = profitability_analytics(
        dimension="product",
        date_from=today - timedelta(days=1),
        date_to=today,
        days=None,
        timezone_name="UTC",
        country=None,
        mode=None,
        page=1,
        page_size=25,
        session=session,
        user=ADMIN,
    )
    assert profitability["items"][0]["margin_bdt"] == "300.00"
