from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import (
    AccountUser,
    AdminAuditEvent,
    Base,
    Category,
    Country,
    CurrencyRate,
    ManualPaymentProof,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    PurchaseOrder,
    Seller,
    SellerOffer,
)
from app.services import procurement
from app.services.orders import utc_now

ADMIN = {"sub": 9001, "role": "admin"}
OPERATOR = {"sub": 9002, "role": "operator"}


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        category = Category(name="Office", slug="office")
        product = Product(name="Desk Lamp", slug="desk-lamp", category=category)
        variant = ProductVariant(product=product, sku="LAMP-1", variant_name="Standard", weight_kg=Decimal("1.000"))
        country = Country(code="CN", name="China")
        seller = Seller(country=country, name="Lamp Works", rating=Decimal("4.40"))
        offer = SellerOffer(
            id=77, variant=variant, country=country, seller=seller, mode="LOCAL",
            price_origin=Decimal("10.00"), currency="USD", stock=500, moq=1,
        )
        customer = AccountUser(id=1001, username="buyer", email="buyer@example.com", password_hash="x", role="customer")
        db.add_all([product, variant, country, seller, offer, customer, CurrencyRate(currency="USD", rate_to_bdt=Decimal("120"))])
        db.commit()
        yield db
    engine.dispose()


def _order(db: Session, status: str = "CONFIRMED", qty: int = 10) -> Order:
    order = Order(
        user_id=1001, country_code="CN", mode="LOCAL", delivery_type="DOOR", status=status,
        total_bdt=Decimal("20000.00"), shipping_bdt=Decimal("1500.00"), advance_bdt=Decimal("12000.00"),
        remaining_bdt=Decimal("8000.00"),
        quote_snapshot={"response": {"breakdown": {"product_cost_bdt": "12000.00", "duty_vat_bdt": "2000.00"}}},
    )
    order.items.append(OrderItem(variant_id=1, product_name="Desk Lamp", variant_name="Standard", qty=qty, offer_id=77))
    order.manual_payment = ManualPaymentProof(
        channel="bKash", trx_id="TX-1", trx_normalized=f"tx{status}{qty}", verified=True, decision="APPROVED",
    )
    db.add(order)
    db.commit()
    return order


def _po(db: Session, order: Order, **kwargs) -> PurchaseOrder:
    return procurement.create_purchase_order(
        db, order.id, unit_cost_origin=kwargs.get("unit_cost"), expected_at=None, note="Raise PO", current_user=OPERATOR
    )


def _status(db: Session, po: PurchaseOrder, status: str) -> PurchaseOrder:
    return procurement.change_purchase_order_status(db, po.id, status=status, note=f"Move to {status}", current_user=OPERATOR)


def test_purchase_order_is_prefilled_from_the_locked_supplier_offer(session: Session) -> None:
    po = _po(session, _order(session))

    assert po.status == "DRAFT"
    assert po.po_number == f"PO-{utc_now().year}-{po.id:05d}"
    assert po.seller.name == "Lamp Works"
    assert (po.currency, po.total_origin, po.total_bdt) == ("USD", Decimal("100.00"), Decimal("12000.00"))
    assert [(item.qty, item.unit_cost_origin) for item in po.items] == [(10, Decimal("10.00"))]
    assert session.scalar(select(AdminAuditEvent.action)) == "purchase_order.created"


def test_negotiated_unit_cost_replaces_the_offer_price(session: Session) -> None:
    po = _po(session, _order(session), unit_cost=Decimal("9.25"))
    assert po.total_origin == Decimal("92.50")


@pytest.mark.parametrize("order_status", ["PENDING", "CANCELLED", "DELIVERED"])
def test_purchase_order_needs_a_confirmed_order(session: Session, order_status: str) -> None:
    with pytest.raises(HTTPException) as raised:
        _po(session, _order(session, status=order_status))
    assert raised.value.status_code == 409


def test_an_order_cannot_have_two_active_purchase_orders(session: Session) -> None:
    order = _order(session)
    first = _po(session, order)
    with pytest.raises(HTTPException) as raised:
        _po(session, order)
    assert first.po_number in raised.value.detail

    _status(session, first, "CANCELLED")
    assert _po(session, order).status == "DRAFT"


def test_supplier_confirmation_moves_the_customer_order_to_purchased(session: Session) -> None:
    order = _order(session)
    po = _status(session, _po(session, order), "SENT")
    assert session.get(Order, order.id).status == "CONFIRMED"

    po = _status(session, po, "CONFIRMED")

    assert po.status == "CONFIRMED"
    assert session.get(Order, order.id).status == "PURCHASED"


def test_invalid_transitions_are_rejected(session: Session) -> None:
    po = _po(session, _order(session))
    for target in ("CONFIRMED", "CLOSED", "RECEIVED"):
        with pytest.raises(HTTPException) as raised:
            _status(session, po, target)
        assert raised.value.status_code == 409


def test_goods_receipts_track_quality_and_complete_the_purchase_order(session: Session) -> None:
    order = _order(session)
    po = _status(session, _status(session, _po(session, order), "SENT"), "CONFIRMED")

    po = procurement.record_goods_receipt(session, po.id, received=6, accepted=6, rejected=0, qc_note=None, current_user=OPERATOR)
    assert po.status == "CONFIRMED"
    with pytest.raises(HTTPException) as raised:
        procurement.record_goods_receipt(session, po.id, received=5, accepted=5, rejected=0, qc_note=None, current_user=OPERATOR)
    assert "Only 4 units" in raised.value.detail
    with pytest.raises(HTTPException):
        procurement.record_goods_receipt(session, po.id, received=4, accepted=3, rejected=1, qc_note=None, current_user=OPERATOR)

    po = procurement.record_goods_receipt(
        session, po.id, received=4, accepted=3, rejected=1, qc_note="One lamp arrived cracked", current_user=OPERATOR
    )

    assert po.status == "RECEIVED"
    assert procurement.received_qty(po) == 10
    assert session.get(Order, order.id).quality_defect_reported is True


def test_supplier_payments_reduce_the_payable_and_gate_closing(session: Session) -> None:
    po = _status(session, _status(session, _po(session, _order(session)), "SENT"), "CONFIRMED")
    po = procurement.record_goods_receipt(session, po.id, received=10, accepted=10, rejected=0, qc_note=None, current_user=OPERATOR)

    with pytest.raises(HTTPException) as raised:
        _status(session, po, "CLOSED")
    assert "still payable" in raised.value.detail
    with pytest.raises(HTTPException):
        procurement.record_supplier_payment(
            session, po.id, amount_origin=Decimal("150"), method="TT", reference=None, note="Too much", current_user=OPERATOR
        )

    po = procurement.record_supplier_payment(
        session, po.id, amount_origin=Decimal("40"), method="TT", reference="SWIFT-1", note="Deposit", current_user=OPERATOR
    )
    assert procurement.outstanding_origin(po) == Decimal("60.00")
    # The balance is paid after the rate moved; each payment keeps its own rate.
    session.scalar(select(CurrencyRate)).rate_to_bdt = Decimal("125")
    session.commit()
    po = procurement.record_supplier_payment(
        session, po.id, amount_origin=Decimal("60"), method="TT", reference="SWIFT-2", note="Balance", current_user=OPERATOR
    )

    assert procurement.outstanding_origin(po) == Decimal("0.00")
    assert procurement.paid_bdt(po) == Decimal("12300.00")  # 40 x 120 + 60 x 125
    assert _status(session, po, "CLOSED").status == "CLOSED"


def test_payment_reversal_reopens_the_payable_and_is_audited(session: Session) -> None:
    po = _status(session, _po(session, _order(session)), "SENT")
    po = procurement.record_supplier_payment(
        session, po.id, amount_origin=Decimal("100"), method="TT", reference="SWIFT-9", note="Paid in full", current_user=OPERATOR
    )
    with pytest.raises(HTTPException) as raised:
        _status(session, po, "CANCELLED")
    assert "Reverse the supplier payments" in raised.value.detail

    po = procurement.reverse_supplier_payment(session, po.payments[0].id, reason="Sent to the wrong account", current_user=ADMIN)

    assert procurement.outstanding_origin(po) == Decimal("100.00")
    assert po.payments[0].reversal_reason == "Sent to the wrong account"
    actions = session.scalars(select(AdminAuditEvent.action).order_by(AdminAuditEvent.id)).all()
    assert actions[-1] == "supplier_payment.reversed"
    with pytest.raises(HTTPException):
        procurement.reverse_supplier_payment(session, po.payments[0].id, reason="Again", current_user=ADMIN)


def test_payables_report_ages_open_balances(session: Session) -> None:
    recent = _status(session, _po(session, _order(session, qty=10)), "SENT")
    old = _status(session, _po(session, _order(session, qty=5)), "SENT")
    old.created_at = utc_now() - timedelta(days=75)
    draft = _po(session, _order(session, qty=2))
    session.commit()
    procurement.record_supplier_payment(
        session, recent.id, amount_origin=Decimal("25"), method="TT", reference=None, note="Part payment", current_user=OPERATOR
    )

    report = procurement.supplier_payables(session)

    assert [row["po_number"] for row in report["items"]] == [old.po_number, recent.po_number]
    assert draft.po_number not in [row["po_number"] for row in report["items"]]
    assert report["aging_bdt"] == {"0_30": "9000.00", "31_60": "0.00", "over_60": "6000.00"}
    assert report["total_outstanding_bdt"] == "15000.00"


def test_order_profit_and_loss_separates_actual_and_quoted_costs(session: Session) -> None:
    order = _order(session)
    before = procurement.order_profit_and_loss(session, order)
    assert before["supplier_cost_basis"] == "quote"
    assert before["estimated_margin_bdt"] == "4500.00"  # 20000 - 12000 - 1500 - 2000

    _po(session, order, unit_cost=Decimal("9.00"))
    after = procurement.order_profit_and_loss(session, order)

    assert after["supplier_cost_basis"] == "purchase_order"
    assert after["supplier_cost_bdt"] == "10800.00"
    assert after["estimated_margin_bdt"] == "5700.00"
    assert after["realized_margin_bdt"] is None
    assert after["net_verified_cash_bdt"] == "12000.00"

    order.actual_cost_bdt = Decimal("15100.00")
    session.commit()
    assert procurement.order_profit_and_loss(session, order)["realized_margin_bdt"] == "4900.00"


def test_erp_summary_counts_work_waiting_in_each_module(session: Session) -> None:
    _order(session, qty=3)
    _status(session, _po(session, _order(session, qty=4)), "SENT")

    summary = procurement.erp_summary(session)

    assert summary["orders_awaiting_purchase"] == 1
    assert summary["open_purchase_orders"] == 1
    assert summary["purchase_orders"]["SENT"] == 1
    assert summary["payables_outstanding_bdt"] == "4800.00"
