from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..admin_schemas import PaymentReversalIn, RefundCreateIn, RefundReverseIn
from ..analytics_cache import invalidate_admin_analytics
from ..models import ManualPaymentProof, Order, OrderStatusHistory, PaymentAdjustment
from .orders import get_order_or_404, record_admin_audit, require_operator, utc_now


CurrentUser = dict[str, Any]


def _money(value: Decimal | int | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _new_reference(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:24].upper()}"


def posted_refunds_for_order(session: Session, order_id: int) -> Decimal:
    value = session.scalar(
        select(func.coalesce(func.sum(PaymentAdjustment.amount_bdt), 0)).where(
            PaymentAdjustment.order_id == order_id,
            PaymentAdjustment.adjustment_type == "REFUND",
            PaymentAdjustment.status == "POSTED",
        )
    )
    return _money(value)


def financial_snapshot(session: Session, order: Order) -> dict[str, Any]:
    approved = bool(
        order.manual_payment
        and order.manual_payment.decision == "APPROVED"
        and order.manual_payment.verified
    )
    gross_collected = _money(order.advance_bdt if approved else 0)
    refunds = posted_refunds_for_order(session, order.id)
    net_collected = max(Decimal("0.00"), gross_collected - refunds)
    outstanding = (
        Decimal("0.00")
        if order.status == "CANCELLED"
        else max(Decimal("0.00"), _money(order.total_bdt) - net_collected)
    )
    return {
        "gross_collected_bdt": format(gross_collected, ".2f"),
        "refunds_bdt": format(refunds, ".2f"),
        "net_verified_cash_bdt": format(net_collected, ".2f"),
        "outstanding_bdt": format(outstanding, ".2f"),
    }


def serialize_adjustment(adjustment: PaymentAdjustment) -> dict[str, Any]:
    return {
        "id": adjustment.id,
        "order_id": adjustment.order_id,
        "payment_id": adjustment.payment_id,
        "type": adjustment.adjustment_type,
        "status": adjustment.status,
        "amount_bdt": format(_money(adjustment.amount_bdt), ".2f"),
        "transaction_id": adjustment.transaction_id,
        "reason": adjustment.reason,
        "created_by_user_id": adjustment.created_by_user_id,
        "created_at": adjustment.created_at,
        "reversed_by_user_id": adjustment.reversed_by_user_id,
        "reversed_at": adjustment.reversed_at,
        "reversal_reason": adjustment.reversal_reason,
    }


def reverse_payment(
    session: Session,
    payment_id: int,
    payload: PaymentReversalIn,
    current_user: CurrentUser,
) -> tuple[Order, PaymentAdjustment]:
    require_operator(current_user)
    payment = session.scalar(
        select(ManualPaymentProof).where(ManualPaymentProof.id == payment_id)
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Payment proof not found")
    order = get_order_or_404(session, payment.order_id, current_user)
    if payment.decision != "APPROVED" or not payment.verified:
        raise HTTPException(status_code=409, detail="Only an approved payment can be reversed")
    if order.status not in {"PENDING", "CONFIRMED", "CANCELLED"}:
        raise HTTPException(
            status_code=409,
            detail="Purchased or fulfilled orders require a refund, not payment-verification reversal",
        )
    refunds = posted_refunds_for_order(session, order.id)
    if refunds:
        raise HTTPException(
            status_code=409,
            detail="Reverse posted refunds before reversing this payment verification",
        )

    before = {
        "payment_decision": payment.decision,
        "payment_verified": payment.verified,
        "order_status": order.status,
    }
    now = utc_now()
    adjustment = PaymentAdjustment(
        order_id=order.id,
        payment_id=payment.id,
        adjustment_type="PAYMENT_REVERSAL",
        status="POSTED",
        amount_bdt=_money(order.advance_bdt),
        transaction_id=_new_reference("REV"),
        reason=payload.note.strip(),
        created_by_user_id=int(current_user["sub"]),
        created_at=now,
    )
    payment.decision = "REVERSED"
    payment.verified = False
    payment.verified_at = None
    payment.decided_at = now
    payment.decided_by_user_id = int(current_user["sub"])
    payment.decision_reason = payload.note.strip()
    from .customer_payments import append_payment_decision
    from .notifications import queue_customer_notification

    append_payment_decision(
        session,
        payment,
        decision="REVERSED",
        reason=payload.note,
        actor_user_id=int(current_user["sub"]),
        actor_role=str(current_user.get("role") or "operator"),
        request_id=payload.request_id,
        submitted_by_user_id=order.user_id,
    )
    if order.status == "CONFIRMED":
        order.status = "PENDING"
        order.history.append(
            OrderStatusHistory(
                status="PENDING",
                previous_status="CONFIRMED",
                note=f"Payment verification reversed: {payload.note.strip()}",
                actor_user_id=int(current_user["sub"]),
                actor_role=str(current_user.get("role") or "operator"),
                request_id=payload.request_id,
            )
        )
    order.updated_at = now
    session.add(adjustment)
    record_admin_audit(
        session,
        current_user,
        action="payment.reversed",
        entity_type="manual_payment",
        entity_id=payment.id,
        before=before,
        after={
            "payment_decision": payment.decision,
            "payment_verified": payment.verified,
            "order_status": order.status,
            "reversal_transaction_id": adjustment.transaction_id,
        },
        note=payload.note,
        request_id=payload.request_id,
    )
    queue_customer_notification(
        session,
        user_id=order.user_id,
        category="order",
        title=f"Payment reversed for order #{order.id}",
        body=payload.note.strip(),
        order_id=order.id,
        data={"order_status": order.status, "payment_status": "REVERSED"},
        template_key="payment_reversed",
    )
    session.commit()
    session.refresh(order)
    session.refresh(adjustment)
    invalidate_admin_analytics()
    return order, adjustment


def create_refund(
    session: Session,
    order_id: int,
    payload: RefundCreateIn,
    current_user: CurrentUser,
) -> PaymentAdjustment:
    require_operator(current_user)
    order = get_order_or_404(session, order_id, current_user)
    payment = order.manual_payment
    if not payment or payment.decision != "APPROVED" or not payment.verified:
        raise HTTPException(status_code=409, detail="A verified payment is required before refunding")
    refundable = _money(order.advance_bdt) - posted_refunds_for_order(session, order.id)
    amount = _money(payload.amount_bdt)
    if amount > refundable:
        raise HTTPException(
            status_code=409,
            detail=f"Refund exceeds refundable verified cash ({format(refundable, '.2f')} BDT)",
        )
    transaction_id = (payload.transaction_id or _new_reference("RFN")).strip().upper()
    duplicate = session.scalar(
        select(PaymentAdjustment.id).where(
            func.lower(PaymentAdjustment.transaction_id) == transaction_id.casefold()
        )
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="Refund transaction ID already exists")

    adjustment = PaymentAdjustment(
        order_id=order.id,
        payment_id=payment.id,
        adjustment_type="REFUND",
        status="POSTED",
        amount_bdt=amount,
        transaction_id=transaction_id,
        reason=payload.reason.strip(),
        created_by_user_id=int(current_user["sub"]),
    )
    session.add(adjustment)
    session.flush()
    from .notifications import queue_customer_notification

    record_admin_audit(
        session,
        current_user,
        action="refund.posted",
        entity_type="payment_adjustment",
        entity_id=adjustment.id,
        before=None,
        after=serialize_adjustment(adjustment),
        note=payload.reason,
        request_id=payload.request_id,
    )
    queue_customer_notification(
        session,
        user_id=order.user_id,
        category="order",
        title=f"Refund posted for order #{order.id}",
        body=f"Refund BDT {format(amount, '.2f')} was posted. {payload.reason.strip()}",
        order_id=order.id,
        data={
            "refund_id": adjustment.id,
            "amount_bdt": format(amount, ".2f"),
            "refund_status": adjustment.status,
        },
        template_key="refund_posted",
    )
    session.commit()
    session.refresh(adjustment)
    invalidate_admin_analytics()
    return adjustment


def reverse_refund(
    session: Session,
    adjustment_id: int,
    payload: RefundReverseIn,
    current_user: CurrentUser,
) -> PaymentAdjustment:
    require_operator(current_user)
    adjustment = session.get(PaymentAdjustment, adjustment_id)
    if not adjustment or adjustment.adjustment_type != "REFUND":
        raise HTTPException(status_code=404, detail="Refund not found")
    if adjustment.status != "POSTED":
        raise HTTPException(status_code=409, detail="Refund has already been reversed")

    before = serialize_adjustment(adjustment)
    adjustment.status = "REVERSED"
    adjustment.reversed_at = utc_now()
    adjustment.reversed_by_user_id = int(current_user["sub"])
    adjustment.reversal_reason = payload.note.strip()
    order = get_order_or_404(session, adjustment.order_id, current_user)
    from .notifications import queue_customer_notification

    record_admin_audit(
        session,
        current_user,
        action="refund.reversed",
        entity_type="payment_adjustment",
        entity_id=adjustment.id,
        before=before,
        after=serialize_adjustment(adjustment),
        note=payload.note,
        request_id=payload.request_id,
    )
    queue_customer_notification(
        session,
        user_id=order.user_id,
        category="order",
        title=f"Refund reversed for order #{order.id}",
        body=payload.note.strip(),
        order_id=order.id,
        data={"refund_id": adjustment.id, "refund_status": adjustment.status},
        template_key="refund_reversed",
    )
    session.commit()
    session.refresh(adjustment)
    invalidate_admin_analytics()
    return adjustment
