from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..customer_schemas import PaymentRetryIn
from ..config import get_settings
from ..models import (
    ManualPaymentProof,
    Order,
    PaymentProofAttempt,
    PaymentProofDecision,
)
from ..security import request_id_context, validate_payment_proof_host
from .customer_account import require_customer
from .notifications import queue_customer_notification
from .orders import get_order_or_404, normalize_transaction_id, utc_now


CurrentUser = dict[str, Any]


def latest_payment_attempt(
    session: Session,
    payment_id: int,
) -> PaymentProofAttempt | None:
    return session.scalar(
        select(PaymentProofAttempt)
        .where(PaymentProofAttempt.payment_id == payment_id)
        .order_by(PaymentProofAttempt.attempt_number.desc())
        .limit(1)
    )


def ensure_payment_attempt(
    session: Session,
    payment: ManualPaymentProof,
    *,
    submitted_by_user_id: int,
) -> PaymentProofAttempt:
    current = latest_payment_attempt(session, payment.id)
    if current is not None:
        return current
    attempt = PaymentProofAttempt(
        payment_id=payment.id,
        order_id=payment.order_id,
        attempt_number=1,
        channel=payment.channel,
        trx_id=payment.trx_id,
        trx_normalized=payment.trx_normalized,
        screenshot_url=payment.screenshot_url,
        submitted_by_user_id=submitted_by_user_id,
        request_id=request_id_context.get(),
        created_at=payment.created_at or utc_now(),
    )
    session.add(attempt)
    session.flush()
    return attempt


def append_payment_decision(
    session: Session,
    payment: ManualPaymentProof,
    *,
    decision: str,
    reason: str | None,
    actor_user_id: int | None,
    actor_role: str,
    request_id: str | None,
    submitted_by_user_id: int,
) -> PaymentProofDecision:
    attempt = ensure_payment_attempt(
        session,
        payment,
        submitted_by_user_id=submitted_by_user_id,
    )
    event = PaymentProofDecision(
        decision=decision,
        reason=(reason or "").strip() or None,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        request_id=request_id or request_id_context.get(),
    )
    attempt.decisions.append(event)
    return event


def serialize_payment_attempt(attempt: PaymentProofAttempt) -> dict[str, Any]:
    return {
        "id": attempt.id,
        "payment_id": attempt.payment_id,
        "order_id": attempt.order_id,
        "attempt_number": attempt.attempt_number,
        "channel": attempt.channel,
        "trx_id": attempt.trx_id,
        "screenshot_url": attempt.screenshot_url,
        "submitted_by_user_id": attempt.submitted_by_user_id,
        "request_id": attempt.request_id,
        "created_at": attempt.created_at,
        "decisions": [
            {
                "id": decision.id,
                "decision": decision.decision,
                "reason": decision.reason,
                "actor_user_id": decision.actor_user_id,
                "actor_role": decision.actor_role,
                "request_id": decision.request_id,
                "created_at": decision.created_at,
            }
            for decision in sorted(
                attempt.decisions,
                key=lambda item: (item.created_at, item.id),
            )
        ],
    }


def list_payment_attempts(
    session: Session,
    order_id: int,
    current_user: CurrentUser,
) -> list[dict[str, Any]]:
    require_customer(current_user)
    order = get_order_or_404(session, order_id, current_user)
    payment = order.manual_payment
    if payment is None:
        return []
    attempt = ensure_payment_attempt(
        session,
        payment,
        submitted_by_user_id=order.user_id,
    )
    if attempt.id is None:
        session.flush()
    session.commit()
    attempts = session.scalars(
        select(PaymentProofAttempt)
        .where(PaymentProofAttempt.payment_id == payment.id)
        .order_by(PaymentProofAttempt.attempt_number)
    ).all()
    # SQLAlchemy populates the decision relationship on access; the return type
    # is deliberately append-only and ordered for an audit-friendly timeline.
    return [serialize_payment_attempt(item) for item in attempts]


def retry_manual_payment(
    session: Session,
    order_id: int,
    payload: PaymentRetryIn,
    current_user: CurrentUser,
) -> tuple[Order, PaymentProofAttempt]:
    require_customer(current_user)
    validate_payment_proof_host(payload.screenshot_url, get_settings())
    order = get_order_or_404(session, order_id, current_user)
    payment = order.manual_payment
    if payment is None:
        raise HTTPException(status_code=409, detail="No manual payment exists for this order")
    if order.status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Payment retry is only available while the order is pending",
        )
    if payment.decision not in {"REJECTED", "REVERSED"}:
        raise HTTPException(
            status_code=409,
            detail="Only a rejected or reversed payment proof can be retried",
        )
    normalized = normalize_transaction_id(payload.trx_id)
    duplicate_attempt = session.scalar(
        select(PaymentProofAttempt.id).where(
            func.lower(PaymentProofAttempt.channel) == payload.channel.casefold(),
            PaymentProofAttempt.trx_normalized == normalized,
        )
    )
    duplicate_current = session.scalar(
        select(ManualPaymentProof.id).where(
            ManualPaymentProof.id != payment.id,
            func.lower(ManualPaymentProof.channel) == payload.channel.casefold(),
            ManualPaymentProof.trx_normalized == normalized,
        )
    )
    if duplicate_attempt or duplicate_current:
        raise HTTPException(
            status_code=409,
            detail="This payment transaction ID has already been submitted",
        )

    previous = ensure_payment_attempt(
        session,
        payment,
        submitted_by_user_id=order.user_id,
    )
    attempt_number = previous.attempt_number + 1
    attempt = PaymentProofAttempt(
        payment_id=payment.id,
        order_id=order.id,
        attempt_number=attempt_number,
        channel=payload.channel,
        trx_id=payload.trx_id.strip(),
        trx_normalized=normalized,
        screenshot_url=payload.screenshot_url,
        submitted_by_user_id=int(current_user["sub"]),
        request_id=request_id_context.get(),
    )
    session.add(attempt)
    payment.channel = payload.channel
    payment.trx_id = payload.trx_id.strip()
    payment.trx_normalized = normalized
    payment.screenshot_url = payload.screenshot_url
    payment.decision = "PENDING"
    payment.decision_reason = None
    payment.decided_at = None
    payment.decided_by_user_id = None
    payment.verified = False
    payment.verified_at = None
    order.updated_at = utc_now()
    queue_customer_notification(
        session,
        user_id=order.user_id,
        category="order",
        title=f"Payment retry submitted for order #{order.id}",
        body="Your new payment proof is queued for verification.",
        order_id=order.id,
        data={"payment_attempt": attempt_number, "payment_status": "PENDING"},
        template_key="payment_retry_submitted",
    )
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="This payment transaction ID has already been submitted",
        ) from exc
    session.refresh(order)
    session.refresh(attempt)
    return order, attempt
