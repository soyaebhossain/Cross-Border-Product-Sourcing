"""Procurement and supplier-side finance for customer orders.

Flow: a confirmed customer order gets a purchase order (PO) for its supplier.
DRAFT -> SENT -> CONFIRMED -> RECEIVED -> CLOSED, or CANCELLED before goods
arrive. Confirming a PO moves the customer order to PURCHASED. Goods receipts
record quality-check results, supplier payments reduce the payable, and a PO
closes only when everything is received and fully paid. Every change is
written to the admin audit log; payments are reversed, never deleted.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..models import (
    GoodsReceipt,
    Order,
    PurchaseOrder,
    PurchaseOrderItem,
    SellerOffer,
    SupplierPayment,
)
from ..schemas import UpdateOrderStatusIn
from .financial_operations import financial_snapshot
from .orders import record_admin_audit, update_order_status_record, utc_now
from .sourcing import currency_rate_row

CurrentUser = dict[str, Any]
CENT = Decimal("0.01")

PO_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"SENT", "CANCELLED"},
    "SENT": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"CANCELLED"},  # RECEIVED is reached by recording goods receipts
    "RECEIVED": {"CLOSED"},
    "CLOSED": set(),
    "CANCELLED": set(),
}
OPEN_STATUSES = ("DRAFT", "SENT", "CONFIRMED", "RECEIVED")
PAYABLE_STATUSES = ("SENT", "CONFIRMED", "RECEIVED")
ORDER_STATUSES_NEEDING_PURCHASE = ("CONFIRMED", "PURCHASED")


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT)


def po_loader_options() -> tuple[Any, ...]:
    return (
        selectinload(PurchaseOrder.items),
        selectinload(PurchaseOrder.receipts),
        selectinload(PurchaseOrder.payments),
        selectinload(PurchaseOrder.seller),
        selectinload(PurchaseOrder.order),
    )


def get_purchase_order_or_404(session: Session, po_id: int) -> PurchaseOrder:
    purchase_order = session.scalar(
        select(PurchaseOrder).options(*po_loader_options()).where(PurchaseOrder.id == po_id)
    )
    if not purchase_order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return purchase_order


def ordered_qty(purchase_order: PurchaseOrder) -> int:
    return sum(item.qty for item in purchase_order.items)


def received_qty(purchase_order: PurchaseOrder) -> int:
    return sum(receipt.received_qty for receipt in purchase_order.receipts)


def paid_origin(purchase_order: PurchaseOrder) -> Decimal:
    return _money(sum((p.amount_origin for p in purchase_order.payments if p.reversed_at is None), Decimal("0")))


def paid_bdt(purchase_order: PurchaseOrder) -> Decimal:
    return _money(sum((p.amount_bdt for p in purchase_order.payments if p.reversed_at is None), Decimal("0")))


def outstanding_origin(purchase_order: PurchaseOrder) -> Decimal:
    if purchase_order.status == "CANCELLED":
        return Decimal("0.00")
    return max(Decimal("0.00"), _money(purchase_order.total_origin) - paid_origin(purchase_order))


def serialize_purchase_order(purchase_order: PurchaseOrder, *, detail: bool = False) -> dict[str, Any]:
    outstanding = outstanding_origin(purchase_order)
    data: dict[str, Any] = {
        "id": purchase_order.id,
        "po_number": purchase_order.po_number,
        "order_id": purchase_order.order_id,
        "order_status": purchase_order.order.status if purchase_order.order else None,
        "supplier": {"id": purchase_order.seller_id, "name": purchase_order.seller.name},
        "status": purchase_order.status,
        "currency": purchase_order.currency,
        "fx_rate_to_bdt": format(Decimal(purchase_order.fx_rate_to_bdt).normalize(), "f"),
        "total_origin": format(_money(purchase_order.total_origin), ".2f"),
        "total_bdt": format(_money(purchase_order.total_bdt), ".2f"),
        "paid_origin": format(paid_origin(purchase_order), ".2f"),
        "paid_bdt": format(paid_bdt(purchase_order), ".2f"),
        "outstanding_origin": format(outstanding, ".2f"),
        "outstanding_bdt": format(_money(outstanding * Decimal(purchase_order.fx_rate_to_bdt)), ".2f"),
        "ordered_qty": ordered_qty(purchase_order),
        "received_qty": received_qty(purchase_order),
        "rejected_qty": sum(receipt.rejected_qty for receipt in purchase_order.receipts),
        "expected_at": purchase_order.expected_at,
        "note": purchase_order.note,
        "created_at": purchase_order.created_at,
        "updated_at": purchase_order.updated_at,
        "allowed_statuses": sorted(PO_TRANSITIONS.get(purchase_order.status, set())),
    }
    if detail:
        data["items"] = [
            {
                "id": item.id,
                "variant_id": item.variant_id,
                "product_name": item.product_name,
                "variant_name": item.variant_name,
                "qty": item.qty,
                "unit_cost_origin": format(_money(item.unit_cost_origin), ".2f"),
                "line_total_origin": format(_money(Decimal(item.unit_cost_origin) * item.qty), ".2f"),
            }
            for item in purchase_order.items
        ]
        data["receipts"] = [
            {
                "id": receipt.id,
                "received_qty": receipt.received_qty,
                "accepted_qty": receipt.accepted_qty,
                "rejected_qty": receipt.rejected_qty,
                "qc_note": receipt.qc_note,
                "received_at": receipt.received_at,
                "received_by_user_id": receipt.received_by_user_id,
            }
            for receipt in sorted(purchase_order.receipts, key=lambda row: row.id)
        ]
        data["payments"] = [serialize_supplier_payment(payment) for payment in sorted(purchase_order.payments, key=lambda row: row.id)]
    return data


def serialize_supplier_payment(payment: SupplierPayment) -> dict[str, Any]:
    return {
        "id": payment.id,
        "purchase_order_id": payment.purchase_order_id,
        "amount_origin": format(_money(payment.amount_origin), ".2f"),
        "currency": payment.currency,
        "fx_rate_to_bdt": format(Decimal(payment.fx_rate_to_bdt).normalize(), "f"),
        "amount_bdt": format(_money(payment.amount_bdt), ".2f"),
        "method": payment.method,
        "reference": payment.reference,
        "paid_at": payment.paid_at,
        "status": "REVERSED" if payment.reversed_at else "POSTED",
        "reversed_at": payment.reversed_at,
        "reversal_reason": payment.reversal_reason,
    }


def _rate_to_bdt(session: Session, currency: str) -> Decimal:
    rate = currency_rate_row(session, currency)
    return Decimal("1") if rate is None else Decimal(rate.rate_to_bdt)


def create_purchase_order(
    session: Session,
    order_id: int,
    *,
    unit_cost_origin: Decimal | None,
    expected_at: datetime | None,
    note: str | None,
    current_user: CurrentUser,
) -> PurchaseOrder:
    order = session.scalar(select(Order).options(selectinload(Order.items)).where(Order.id == order_id))
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ORDER_STATUSES_NEEDING_PURCHASE:
        raise HTTPException(
            status_code=409,
            detail=f"A purchase order needs a confirmed customer order; order {order.id} is {order.status}",
        )
    existing = session.scalar(
        select(PurchaseOrder.po_number).where(
            PurchaseOrder.order_id == order.id, PurchaseOrder.status != "CANCELLED"
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Order {order.id} already has purchase order {existing}")
    if not order.items:
        raise HTTPException(status_code=409, detail="Order has no items to purchase")

    offers: list[tuple[Any, SellerOffer]] = []
    for item in order.items:
        offer = session.get(SellerOffer, item.offer_id) if item.offer_id else None
        if offer is None:
            raise HTTPException(status_code=409, detail="Order item has no supplier offer to purchase from")
        offers.append((item, offer))
    seller_ids = {offer.seller_id for _, offer in offers}
    currencies = {offer.currency.strip().upper() for _, offer in offers}
    if len(seller_ids) != 1 or len(currencies) != 1:
        raise HTTPException(status_code=409, detail="Order items come from different suppliers or currencies")
    if unit_cost_origin is not None and len(offers) != 1:
        raise HTTPException(status_code=400, detail="A negotiated unit cost can only be set for a single-item order")

    currency = currencies.pop()
    fx_rate = _rate_to_bdt(session, currency)
    purchase_order = PurchaseOrder(
        order_id=order.id,
        seller_id=seller_ids.pop(),
        status="DRAFT",
        currency=currency,
        fx_rate_to_bdt=fx_rate,
        total_origin=Decimal("0"),
        total_bdt=Decimal("0"),
        expected_at=expected_at,
        note=(note or "").strip() or None,
        created_by_user_id=int(current_user["sub"]),
    )
    total = Decimal("0")
    for item, offer in offers:
        unit_cost = _money(unit_cost_origin if unit_cost_origin is not None else offer.price_origin)
        total += unit_cost * item.qty
        purchase_order.items.append(
            PurchaseOrderItem(
                variant_id=item.variant_id,
                product_name=item.product_name,
                variant_name=item.variant_name,
                qty=item.qty,
                unit_cost_origin=unit_cost,
            )
        )
    purchase_order.total_origin = _money(total)
    purchase_order.total_bdt = _money(total * fx_rate)
    session.add(purchase_order)
    session.flush()
    purchase_order.po_number = f"PO-{utc_now().year}-{purchase_order.id:05d}"
    record_admin_audit(
        session,
        current_user,
        action="purchase_order.created",
        entity_type="purchase_order",
        entity_id=purchase_order.id,
        after={
            "po_number": purchase_order.po_number,
            "order_id": order.id,
            "seller_id": purchase_order.seller_id,
            "total_origin": purchase_order.total_origin,
            "currency": currency,
        },
        note=note or "Purchase order raised from customer order",
    )
    session.commit()
    return get_purchase_order_or_404(session, purchase_order.id)


def change_purchase_order_status(
    session: Session,
    po_id: int,
    *,
    status: str,
    note: str,
    current_user: CurrentUser,
) -> PurchaseOrder:
    purchase_order = get_purchase_order_or_404(session, po_id)
    current = purchase_order.status
    if status == "RECEIVED":
        raise HTTPException(status_code=409, detail="Record a goods receipt to mark a purchase order received")
    if status not in PO_TRANSITIONS.get(current, set()):
        raise HTTPException(status_code=409, detail=f"Purchase order cannot move from {current} to {status}")
    if status == "CANCELLED" and paid_origin(purchase_order) > 0:
        raise HTTPException(status_code=409, detail="Reverse the supplier payments before cancelling this purchase order")
    if status == "CLOSED" and outstanding_origin(purchase_order) > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{purchase_order.currency} {outstanding_origin(purchase_order)} is still payable; "
                "record the supplier payment before closing"
            ),
        )
    purchase_order.status = status
    purchase_order.updated_at = utc_now()
    record_admin_audit(
        session,
        current_user,
        action=f"purchase_order.{status.lower()}",
        entity_type="purchase_order",
        entity_id=purchase_order.id,
        before={"status": current},
        after={"status": status},
        note=note,
    )
    session.commit()
    # A supplier confirmation is the moment the goods are actually bought.
    if status == "CONFIRMED" and purchase_order.order.status == "CONFIRMED":
        update_order_status_record(
            session,
            purchase_order.order_id,
            UpdateOrderStatusIn(status="PURCHASED", note=f"Supplier confirmed {purchase_order.po_number}"),
            current_user,
        )
    return get_purchase_order_or_404(session, po_id)


def record_goods_receipt(
    session: Session,
    po_id: int,
    *,
    received: int,
    accepted: int,
    rejected: int,
    qc_note: str | None,
    current_user: CurrentUser,
) -> PurchaseOrder:
    purchase_order = get_purchase_order_or_404(session, po_id)
    if purchase_order.status != "CONFIRMED":
        raise HTTPException(
            status_code=409,
            detail=f"Goods can be received only against a supplier-confirmed purchase order (now {purchase_order.status})",
        )
    if accepted + rejected != received:
        raise HTTPException(status_code=400, detail="Accepted plus rejected units must equal received units")
    remaining = ordered_qty(purchase_order) - received_qty(purchase_order)
    if received > remaining:
        raise HTTPException(status_code=409, detail=f"Only {remaining} units are still expected on this purchase order")
    if rejected and not (qc_note or "").strip():
        raise HTTPException(status_code=400, detail="A quality-check note is required when units are rejected")
    purchase_order.receipts.append(
        GoodsReceipt(
            received_qty=received,
            accepted_qty=accepted,
            rejected_qty=rejected,
            qc_note=(qc_note or "").strip() or None,
            received_by_user_id=int(current_user["sub"]),
        )
    )
    if rejected:
        purchase_order.order.quality_defect_reported = True
    fully_received = received == remaining
    if fully_received:
        purchase_order.status = "RECEIVED"
    purchase_order.updated_at = utc_now()
    record_admin_audit(
        session,
        current_user,
        action="purchase_order.goods_received",
        entity_type="purchase_order",
        entity_id=purchase_order.id,
        after={"received": received, "accepted": accepted, "rejected": rejected, "fully_received": fully_received},
        note=qc_note or "Goods receipt recorded",
    )
    session.commit()
    return get_purchase_order_or_404(session, po_id)


def record_supplier_payment(
    session: Session,
    po_id: int,
    *,
    amount_origin: Decimal,
    method: str,
    reference: str | None,
    note: str,
    current_user: CurrentUser,
) -> PurchaseOrder:
    purchase_order = get_purchase_order_or_404(session, po_id)
    if purchase_order.status not in PAYABLE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Supplier payments can be recorded only on a sent, confirmed or received purchase order (now {purchase_order.status})",
        )
    amount = _money(amount_origin)
    outstanding = outstanding_origin(purchase_order)
    if amount > outstanding:
        raise HTTPException(
            status_code=409,
            detail=f"Payment exceeds the outstanding payable of {purchase_order.currency} {outstanding}",
        )
    fx_rate = _rate_to_bdt(session, purchase_order.currency)
    purchase_order.payments.append(
        SupplierPayment(
            amount_origin=amount,
            currency=purchase_order.currency,
            fx_rate_to_bdt=fx_rate,
            amount_bdt=_money(amount * fx_rate),
            method=method.strip(),
            reference=(reference or "").strip() or None,
            created_by_user_id=int(current_user["sub"]),
        )
    )
    purchase_order.updated_at = utc_now()
    record_admin_audit(
        session,
        current_user,
        action="supplier_payment.posted",
        entity_type="purchase_order",
        entity_id=purchase_order.id,
        after={"amount_origin": amount, "currency": purchase_order.currency, "method": method, "reference": reference},
        note=note,
    )
    session.commit()
    return get_purchase_order_or_404(session, po_id)


def reverse_supplier_payment(
    session: Session,
    payment_id: int,
    *,
    reason: str,
    current_user: CurrentUser,
) -> PurchaseOrder:
    payment = session.get(SupplierPayment, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Supplier payment not found")
    if payment.reversed_at is not None:
        raise HTTPException(status_code=409, detail="This supplier payment is already reversed")
    purchase_order = get_purchase_order_or_404(session, payment.purchase_order_id)
    if purchase_order.status == "CLOSED":
        raise HTTPException(status_code=409, detail="A closed purchase order cannot have payments reversed")
    payment.reversed_at = utc_now()
    payment.reversed_by_user_id = int(current_user["sub"])
    payment.reversal_reason = reason.strip()
    record_admin_audit(
        session,
        current_user,
        action="supplier_payment.reversed",
        entity_type="purchase_order",
        entity_id=purchase_order.id,
        before={"payment_id": payment.id, "amount_origin": payment.amount_origin},
        note=reason,
    )
    session.commit()
    return get_purchase_order_or_404(session, purchase_order.id)


# ------------------------------------------------------------------ finance


def supplier_payables(session: Session) -> dict[str, Any]:
    """Open amounts owed to suppliers, aged from the day each PO was raised."""

    now = utc_now()
    rows: list[dict[str, Any]] = []
    buckets = {"0_30": Decimal("0"), "31_60": Decimal("0"), "over_60": Decimal("0")}
    purchase_orders = session.scalars(
        select(PurchaseOrder)
        .options(*po_loader_options())
        .where(PurchaseOrder.status.in_(PAYABLE_STATUSES))
        .order_by(PurchaseOrder.created_at.asc())
    ).all()
    for purchase_order in purchase_orders:
        outstanding = outstanding_origin(purchase_order)
        if outstanding <= 0:
            continue
        created = purchase_order.created_at
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=now.tzinfo)
        age_days = max(0, (now - created).days) if created else 0
        outstanding_bdt = _money(outstanding * Decimal(purchase_order.fx_rate_to_bdt))
        bucket = "0_30" if age_days <= 30 else "31_60" if age_days <= 60 else "over_60"
        buckets[bucket] += outstanding_bdt
        rows.append({**serialize_purchase_order(purchase_order), "age_days": age_days, "age_bucket": bucket})
    return {
        "generated_at": now,
        "items": rows,
        "total_outstanding_bdt": format(_money(sum(buckets.values(), Decimal("0"))), ".2f"),
        "aging_bdt": {key: format(_money(value), ".2f") for key, value in buckets.items()},
        "note": "Outstanding amounts are converted at each purchase order's exchange rate.",
    }


def order_profit_and_loss(session: Session, order: Order) -> dict[str, Any]:
    """Revenue against cost for one order, saying which figures are actual and which are quoted."""

    purchase_orders = session.scalars(
        select(PurchaseOrder)
        .options(*po_loader_options())
        .where(PurchaseOrder.order_id == order.id, PurchaseOrder.status != "CANCELLED")
    ).all()
    supplier_committed = _money(sum((po.total_bdt for po in purchase_orders), Decimal("0")))
    supplier_paid = _money(sum((paid_bdt(po) for po in purchase_orders), Decimal("0")))
    breakdown = ((order.quote_snapshot or {}).get("response") or {}).get("breakdown") or {}

    def quoted(key: str) -> Decimal:
        try:
            return _money(breakdown.get(key))
        except Exception:  # noqa: BLE001 - malformed legacy snapshots count as zero
            return Decimal("0.00")

    quoted_shipping = _money(order.shipping_bdt) if order.shipping_bdt is not None else quoted("shipping_bdt")
    quoted_duty_vat = quoted("duty_vat_bdt")
    revenue = _money(order.total_bdt)
    # Supplier cost is actual once a PO exists; freight and duty stay quoted
    # until an operator enters the settled cost on the order.
    supplier_cost = supplier_committed if purchase_orders else quoted("product_cost_bdt")
    estimated_cost = supplier_cost + quoted_shipping + quoted_duty_vat
    actual_cost = _money(order.actual_cost_bdt) if order.actual_cost_bdt is not None else None
    return {
        "order_id": order.id,
        "status": order.status,
        "created_at": order.created_at,
        "revenue_bdt": format(revenue, ".2f"),
        **financial_snapshot(session, order),
        "purchase_orders": [po.po_number for po in purchase_orders],
        "supplier_cost_bdt": format(supplier_cost, ".2f"),
        "supplier_cost_basis": "purchase_order" if purchase_orders else "quote",
        "supplier_paid_bdt": format(supplier_paid, ".2f"),
        "quoted_shipping_bdt": format(quoted_shipping, ".2f"),
        "quoted_duty_vat_bdt": format(quoted_duty_vat, ".2f"),
        "estimated_margin_bdt": format(revenue - estimated_cost, ".2f"),
        "actual_cost_bdt": format(actual_cost, ".2f") if actual_cost is not None else None,
        "realized_margin_bdt": format(revenue - actual_cost, ".2f") if actual_cost is not None else None,
    }


def erp_summary(session: Session) -> dict[str, Any]:
    """Counts for the module cards on the admin dashboard."""

    po_counts = dict(
        session.execute(select(PurchaseOrder.status, func.count(PurchaseOrder.id)).group_by(PurchaseOrder.status)).all()
    )
    awaiting_purchase = int(
        session.scalar(
            select(func.count(Order.id)).where(
                Order.status == "CONFIRMED",
                ~select(PurchaseOrder.id)
                .where(PurchaseOrder.order_id == Order.id, PurchaseOrder.status != "CANCELLED")
                .exists(),
            )
        )
        or 0
    )
    payables = supplier_payables(session)
    return {
        "orders_awaiting_purchase": awaiting_purchase,
        "purchase_orders": {status: int(po_counts.get(status, 0)) for status in PO_TRANSITIONS},
        "open_purchase_orders": sum(int(po_counts.get(status, 0)) for status in OPEN_STATUSES),
        "payables_outstanding_bdt": payables["total_outstanding_bdt"],
        "payables_count": len(payables["items"]),
        "payables_over_60_bdt": payables["aging_bdt"]["over_60"],
    }
