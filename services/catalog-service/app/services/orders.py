from __future__ import annotations

import copy
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from ..models import (
    AIDecisionExplanation,
    AdminAuditEvent,
    ManualPaymentProof,
    Order,
    OrderItem,
    OrderStatusHistory,
    PaymentProofAttempt,
    SavedQuote,
    SellerOffer,
    Shipment,
    ShipmentEvent,
)
from ..analytics_cache import invalidate_admin_analytics
from ..config import get_settings
from ..security import request_id_context, validate_payment_proof_host
from ..schemas import (
    AdminPaymentDecisionIn,
    CreateOrderIn,
    QuoteRequestIn,
    SaveQuoteIn,
    UpdateOrderStatusIn,
)
from .sourcing import build_quote, get_variant_or_404
from .automation import fallback_explanation, quote_automation_context, validated_explanation


CurrentUser = dict[str, Any]
ORDER_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"PURCHASED", "CANCELLED"},
    "PURCHASED": {"IN_TRANSIT", "CANCELLED"},
    "IN_TRANSIT": {"CUSTOMS", "CANCELLED"},
    "CUSTOMS": {"LOCAL_DISPATCH", "CANCELLED"},
    "LOCAL_DISPATCH": {"DELIVERED", "CANCELLED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}
ORDERED_QUOTE_STATUSES = {"requested", "received", "approved"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return value


def record_admin_audit(
    session: Session,
    current_user: CurrentUser,
    *,
    action: str,
    entity_type: str,
    entity_id: int | str,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    note: str | None = None,
    request_id: str | None = None,
) -> AdminAuditEvent:
    effective_request_id = request_id or request_id_context.get()
    event = AdminAuditEvent(
        actor_user_id=int(current_user["sub"]),
        actor_role=str(current_user.get("role") or "operator"),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        request_id=effective_request_id,
        before_data=_json_safe(before),
        after_data=_json_safe(after),
        note=(note or "").strip() or None,
    )
    session.add(event)
    return event


def normalize_transaction_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]", "", value or "").casefold()
    if len(normalized) < 3:
        raise HTTPException(status_code=422, detail="A valid payment transaction ID is required")
    return normalized


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _quote_expiry(quote: SavedQuote) -> datetime | None:
    if quote.expires_at:
        return _as_aware_utc(quote.expires_at)
    raw = (quote.response or {}).get("expires_at")
    if not raw:
        return None
    try:
        return _as_aware_utc(datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
    except ValueError:
        return None


def _set_quote_status(quote: SavedQuote, value: str) -> None:
    snapshot = dict(quote.response or {})
    snapshot["status"] = value
    quote.response = snapshot
    quote.status = value
    quote.updated_at = utc_now()


def save_quote_record(session: Session, payload: SaveQuoteIn, current_user: CurrentUser) -> SavedQuote:
    variant = get_variant_or_404(session, payload.variant_id)
    expires_at = utc_now() + timedelta(days=14)
    # Pricing is always produced by the server. A client-provided quote
    # response is display context only and must never become the checkout
    # authority.
    snapshot = copy.deepcopy(
        build_quote(
            session,
            QuoteRequestIn(
                variant_id=payload.variant_id,
                country=payload.country,
                mode=payload.mode,
                qty=payload.qty,
                delivery_type=payload.delivery_type,
            ),
        )
    )
    if not snapshot.get("selected_offer_id"):
        raise HTTPException(
            status_code=409,
            detail="No eligible active supplier offer is available for this quote",
        )
    snapshot["status"] = "requested"
    snapshot["expires_at"] = expires_at.isoformat()
    saved_quote = SavedQuote(
        user_id=current_user["sub"],
        variant_id=variant.id,
        product_name=variant.product.name,
        variant_name=variant.variant_name or variant.sku or "Variant",
        country_code=payload.country.upper(),
        mode=payload.mode,
        delivery_type=payload.delivery_type,
        qty=payload.qty,
        response=snapshot,
        status="requested",
        expires_at=expires_at,
    )
    session.add(saved_quote)
    client_explanation = payload.response.get("ai_explanation")
    if isinstance(client_explanation, dict):
        context = quote_automation_context(
            snapshot,
            country_code=payload.country,
            mode=payload.mode,
        )
        fallback = fallback_explanation(context)
        explanation = validated_explanation(client_explanation, fallback)
        metadata = payload.response.get("ai_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        provider = (
            "ollama-via-n8n"
            if metadata.get("source") == "ollama-via-n8n"
            else "deterministic-fallback"
        )
        review_required = bool(explanation.get("human_review_required"))
        saved_quote.ai_explanation = AIDecisionExplanation(
            provider=provider,
            model="qwen3:8b" if provider == "ollama-via-n8n" else None,
            prompt_version="quote-v1",
            deterministic_snapshot=context,
            explanation=explanation,
            confidence=explanation.get("confidence"),
            human_review_required=review_required,
            review_status="PENDING" if review_required else "NOT_REQUIRED",
        )
    session.commit()
    session.refresh(saved_quote)
    invalidate_admin_analytics()
    return saved_quote


def list_saved_quotes_for_user(session: Session, current_user: CurrentUser) -> list[SavedQuote]:
    return session.scalars(
        select(SavedQuote)
        .where(SavedQuote.user_id == current_user["sub"])
        .order_by(SavedQuote.created_at.desc())
    ).all()


def get_saved_quote_or_404(session: Session, quote_id: int, current_user: CurrentUser) -> SavedQuote:
    quote = session.get(SavedQuote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Saved quote not found")
    if current_user["role"] not in {"admin", "operator"} and quote.user_id != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return quote


def delete_saved_quote_record(session: Session, quote_id: int, current_user: CurrentUser) -> None:
    quote = get_saved_quote_or_404(session, quote_id, current_user)
    if quote.orders:
        raise HTTPException(status_code=409, detail="A quote linked to an order cannot be deleted")
    session.delete(quote)
    session.commit()
    invalidate_admin_analytics()


def update_saved_quote_status(
    session: Session,
    quote_id: int,
    value: str,
    current_user: CurrentUser,
) -> SavedQuote:
    quote = get_saved_quote_or_404(session, quote_id, current_user)
    if value in {"received", "expired"}:
        require_operator(current_user)
    _set_quote_status(quote, value)
    session.add(quote)
    session.commit()
    session.refresh(quote)
    invalidate_admin_analytics()
    return quote


def _decimal_breakdown(breakdown: dict[str, Any], key: str) -> Decimal:
    try:
        value = Decimal(str(breakdown[key]))
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=f"Quote snapshot is missing a valid {key}") from exc
    if value < 0:
        raise HTTPException(status_code=409, detail=f"Quote snapshot contains a negative {key}")
    return value


def _assert_quote_payload_matches(payload: CreateOrderIn, quote: SavedQuote) -> None:
    expected = {
        "variant_id": quote.variant_id,
        "country": quote.country_code.upper(),
        "mode": quote.mode,
        "qty": quote.qty,
        "delivery_type": quote.delivery_type,
    }
    received = {
        "variant_id": payload.variant_id,
        "country": payload.country.upper(),
        "mode": payload.mode,
        "qty": payload.qty,
        "delivery_type": payload.delivery_type,
    }
    mismatches = [key for key in expected if expected[key] != received[key]]
    if mismatches:
        raise HTTPException(
            status_code=409,
            detail=f"Order request does not match saved quote fields: {', '.join(mismatches)}",
        )


def _existing_idempotent_order(
    session: Session,
    user_id: int,
    idempotency_key: str | None,
) -> Order | None:
    if not idempotency_key:
        return None
    return session.scalar(
        select(Order)
        .options(*order_loader_options())
        .where(Order.user_id == user_id, Order.idempotency_key == idempotency_key)
    )


def create_manual_order_record(
    session: Session,
    payload: CreateOrderIn,
    current_user: CurrentUser,
    idempotency_key: str | None = None,
) -> tuple[Order, bool]:
    validate_payment_proof_host(payload.screenshot_url, get_settings())
    body_key = (payload.idempotency_key or "").strip() or None
    header_key = (idempotency_key or "").strip() or None
    if body_key and header_key and body_key != header_key:
        raise HTTPException(status_code=400, detail="Idempotency key header and body do not match")
    effective_key = header_key or body_key

    existing = _existing_idempotent_order(session, int(current_user["sub"]), effective_key)
    if existing:
        return existing, True

    quote: SavedQuote | None = None
    if payload.saved_quote_id:
        quote = get_saved_quote_or_404(session, payload.saved_quote_id, current_user)
        _assert_quote_payload_matches(payload, quote)
        existing_quote_order = session.scalar(
            select(Order)
            .options(*order_loader_options())
            .where(Order.saved_quote_id == quote.id)
        )
        if existing_quote_order:
            if effective_key and existing_quote_order.idempotency_key == effective_key:
                return existing_quote_order, True
            raise HTTPException(
                status_code=409,
                detail=f"Saved quote is already linked to order {existing_quote_order.id}",
            )
        expiry = _quote_expiry(quote)
        if quote.status == "expired" or (expiry and expiry <= utc_now()):
            _set_quote_status(quote, "expired")
            session.add(quote)
            session.commit()
            raise HTTPException(status_code=409, detail="This saved quote has expired")
        if quote.status not in ORDERED_QUOTE_STATUSES:
            raise HTTPException(status_code=409, detail=f"Saved quote status {quote.status} cannot be ordered")
        quote_result = copy.deepcopy(quote.response or {})
        breakdown = quote_result.get("breakdown")
        if not isinstance(breakdown, dict):
            raise HTTPException(status_code=409, detail="Saved quote has no immutable cost breakdown")
        variant = get_variant_or_404(session, quote.variant_id)
        selected_offer_id = quote_result.get("selected_offer_id")
        if not selected_offer_id:
            raise HTTPException(status_code=409, detail="Saved quote has no locked supplier offer")
        if payload.offer_id and int(payload.offer_id) != int(selected_offer_id):
            raise HTTPException(status_code=409, detail="Selected offer does not match the saved quote")
        offer_id = int(selected_offer_id)
        current_offer = session.scalar(
            select(SellerOffer).where(
                SellerOffer.id == offer_id,
                SellerOffer.is_active.is_(True),
                SellerOffer.stock >= quote.qty,
                SellerOffer.moq <= quote.qty,
                SellerOffer.seller.has(is_active=True),
            )
        )
        if not current_offer:
            raise HTTPException(
                status_code=409,
                detail="The locked supplier offer is no longer available; request a new quote",
            )
        order_country = quote.country_code.upper()
        order_mode = quote.mode
        order_delivery = quote.delivery_type
        order_qty = quote.qty
    else:
        quote_result = build_quote(
            session,
            QuoteRequestIn(
                variant_id=payload.variant_id,
                country=payload.country,
                mode=payload.mode,
                qty=payload.qty,
                delivery_type=payload.delivery_type,
            ),
        )
        breakdown = quote_result["breakdown"]
        variant = get_variant_or_404(session, payload.variant_id)
        offer_id = payload.offer_id or quote_result.get("selected_offer_id")
        order_country = payload.country.upper()
        order_mode = payload.mode
        order_delivery = payload.delivery_type
        order_qty = payload.qty

    trx_normalized = normalize_transaction_id(payload.trx_id)
    duplicate_payment = session.scalar(
        select(ManualPaymentProof.id).where(
            func.lower(ManualPaymentProof.channel) == payload.channel.casefold(),
            ManualPaymentProof.trx_normalized == trx_normalized,
        )
    )
    if duplicate_payment:
        raise HTTPException(status_code=409, detail="This payment transaction ID has already been submitted")

    created_at = utc_now()
    eta = quote_result.get("eta") if isinstance(quote_result, dict) else None
    eta_max_days = eta.get("max_days") if isinstance(eta, dict) else None
    promised_delivery_at = (
        created_at + timedelta(days=int(eta_max_days))
        if eta_max_days is not None
        else None
    )
    quote_snapshot = {
        "saved_quote_id": quote.id if quote else None,
        "captured_at": created_at.isoformat(),
        "variant_id": variant.id,
        "product_name": variant.product.name,
        "variant_name": variant.variant_name or variant.sku or "Variant",
        "country": order_country,
        "mode": order_mode,
        "delivery_type": order_delivery,
        "qty": order_qty,
        "offer_id": int(offer_id) if offer_id is not None else None,
        "response": copy.deepcopy(quote_result),
    }
    order = Order(
        user_id=current_user["sub"],
        saved_quote_id=quote.id if quote else None,
        country_code=order_country,
        mode=order_mode,
        delivery_type=order_delivery,
        status="PENDING",
        quote_snapshot=quote_snapshot,
        idempotency_key=effective_key,
        total_bdt=_decimal_breakdown(breakdown, "total_bdt"),
        shipping_bdt=_decimal_breakdown(breakdown, "shipping_bdt"),
        advance_bdt=_decimal_breakdown(breakdown, "advance_bdt"),
        remaining_bdt=_decimal_breakdown(breakdown, "remaining_bdt"),
        promised_delivery_at=promised_delivery_at,
    )
    order.items.append(
        OrderItem(
            variant_id=variant.id,
            product_name=variant.product.name,
            variant_name=variant.variant_name or variant.sku or "Variant",
            qty=order_qty,
            offer_id=int(offer_id) if offer_id is not None else None,
        )
    )
    order.manual_payment = ManualPaymentProof(
        channel=payload.channel,
        trx_id=payload.trx_id.strip(),
        trx_normalized=trx_normalized,
        screenshot_url=payload.screenshot_url,
        verified=False,
        decision="PENDING",
    )
    order.manual_payment.attempts.append(
        PaymentProofAttempt(
            order=order,
            attempt_number=1,
            channel=payload.channel,
            trx_id=payload.trx_id.strip(),
            trx_normalized=trx_normalized,
            screenshot_url=payload.screenshot_url,
            submitted_by_user_id=int(current_user["sub"]),
            request_id=request_id_context.get(),
        )
    )
    order.history.append(
        OrderStatusHistory(
            status="PENDING",
            previous_status=None,
            note="Order created, advance pending verification",
            actor_user_id=int(current_user["sub"]),
            actor_role=str(current_user.get("role") or "customer"),
            request_id=request_id_context.get(),
        )
    )
    order.shipment = Shipment()

    if quote:
        _set_quote_status(quote, "approved")
        snapshot = dict(quote.response or {})
        snapshot["ordered_at"] = utc_now().isoformat()
        quote.response = snapshot
        session.add(quote)
    session.add(order)
    try:
        session.flush()
        from .customer_account import create_order_invoice_snapshot
        from .notifications import queue_customer_notification

        create_order_invoice_snapshot(session, order)
        queue_customer_notification(
            session,
            user_id=order.user_id,
            category="order",
            title=f"Order #{order.id} created",
            body="Your order was created and its advance payment is awaiting verification.",
            order_id=order.id,
            data={"order_status": order.status, "payment_status": "PENDING"},
            template_key="order_created",
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        replay = _existing_idempotent_order(session, int(current_user["sub"]), effective_key)
        if replay:
            return replay, True
        duplicate_payment = session.scalar(
            select(ManualPaymentProof.id).where(
                func.lower(ManualPaymentProof.channel) == payload.channel.casefold(),
                ManualPaymentProof.trx_normalized == trx_normalized,
            )
        )
        if duplicate_payment:
            raise HTTPException(status_code=409, detail="This payment transaction ID has already been submitted") from exc
        raise
    session.refresh(order)
    invalidate_admin_analytics()
    return order, False


def order_loader_options() -> tuple[Any, ...]:
    return (
        selectinload(Order.items),
        selectinload(Order.history),
        selectinload(Order.payment_adjustments),
        selectinload(Order.shipment).selectinload(Shipment.events),
        selectinload(Order.manual_payment)
        .selectinload(ManualPaymentProof.attempts)
        .selectinload(PaymentProofAttempt.decisions),
        joinedload(Order.saved_quote),
    )


def list_orders_for_user(session: Session, current_user: CurrentUser) -> list[Order]:
    return session.scalars(
        select(Order)
        .options(*order_loader_options())
        .where(Order.user_id == current_user["sub"])
        .order_by(Order.id.desc())
    ).unique().all()


def get_order_or_404(session: Session, order_id: int, current_user: CurrentUser) -> Order:
    order = session.scalar(
        select(Order)
        .options(*order_loader_options())
        .where(Order.id == order_id)
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if current_user["role"] not in {"admin", "operator"} and order.user_id != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return order


def require_operator(current_user: CurrentUser) -> None:
    if current_user["role"] not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Forbidden")


def _order_audit_state(order: Order) -> dict[str, Any]:
    return {
        "status": order.status,
        "tracking_number": order.shipment.tracking_number if order.shipment else None,
        "updated_at": order.updated_at,
    }


def update_order_status_record(
    session: Session,
    order_id: int,
    payload: UpdateOrderStatusIn,
    current_user: CurrentUser,
) -> Order:
    require_operator(current_user)
    order = get_order_or_404(session, order_id, current_user)
    current_status = order.status
    target_status = payload.status
    status_changed = target_status != current_status

    if status_changed and target_status not in ORDER_STATUS_TRANSITIONS.get(current_status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Order cannot transition from {current_status} to {target_status}",
        )
    if target_status == "CONFIRMED" and (
        not order.manual_payment
        or order.manual_payment.decision != "APPROVED"
        or not order.manual_payment.verified
    ):
        raise HTTPException(status_code=409, detail="Payment must be approved before confirming the order")

    if not order.shipment:
        order.shipment = Shipment()
    effective_tracking = (payload.tracking_number or order.shipment.tracking_number or "").strip()
    if status_changed and target_status == "IN_TRANSIT" and not effective_tracking:
        raise HTTPException(status_code=409, detail="A tracking number is required before marking an order in transit")

    before = _order_audit_state(order)
    if payload.tracking_number:
        order.shipment.tracking_number = payload.tracking_number.strip()
    if status_changed:
        order.status = target_status
        if target_status == "DELIVERED" and order.delivered_at is None:
            order.delivered_at = utc_now()
        order.history.append(
            OrderStatusHistory(
                status=target_status,
                previous_status=current_status,
                note=(payload.note or "").strip() or None,
                actor_user_id=int(current_user["sub"]),
                actor_role=str(current_user.get("role") or "operator"),
                request_id=payload.request_id or request_id_context.get(),
            )
        )
    event_note = (payload.shipment_note or payload.note or "").strip() or None
    if status_changed and target_status in {"IN_TRANSIT", "CUSTOMS", "LOCAL_DISPATCH", "DELIVERED"}:
        order.shipment.events.append(ShipmentEvent(status=target_status, note=event_note))
    elif payload.shipment_note:
        order.shipment.events.append(ShipmentEvent(status=target_status, note=event_note))

    order.updated_at = utc_now()
    after = _order_audit_state(order)
    record_admin_audit(
        session,
        current_user,
        action="order.status_changed" if status_changed else "order.logistics_updated",
        entity_type="order",
        entity_id=order.id,
        before=before,
        after=after,
        note=payload.note or payload.shipment_note,
        request_id=payload.request_id,
    )
    from .notifications import queue_customer_notification

    queue_customer_notification(
        session,
        user_id=order.user_id,
        category="order",
        title=f"Order #{order.id} updated",
        body=(payload.note or payload.shipment_note or f"Order status is now {order.status}").strip(),
        order_id=order.id,
        data={
            "order_status": order.status,
            "tracking_number": order.shipment.tracking_number if order.shipment else None,
        },
        template_key="order_status_updated",
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    invalidate_admin_analytics()
    return order


def decide_manual_payment_record(
    session: Session,
    order_id: int,
    payload: AdminPaymentDecisionIn,
    current_user: CurrentUser,
) -> Order:
    require_operator(current_user)
    order = get_order_or_404(session, order_id, current_user)
    payment = order.manual_payment
    if not payment:
        raise HTTPException(status_code=400, detail="No manual payment is attached to this order")
    if order.status == "CANCELLED":
        raise HTTPException(status_code=409, detail="A cancelled order payment cannot be decided")
    if payment.decision == "REVERSED":
        raise HTTPException(
            status_code=409,
            detail="A reversed payment proof is terminal; submit a new payment transaction",
        )
    if payment.decision == "APPROVED" and payload.decision != "APPROVED":
        raise HTTPException(status_code=409, detail="An approved payment cannot be rejected")
    if payment.decision == payload.decision:
        return order

    if payload.decision == "APPROVED":
        duplicate = session.scalar(
            select(ManualPaymentProof.id).where(
                ManualPaymentProof.id != payment.id,
                func.lower(ManualPaymentProof.channel) == payment.channel.casefold(),
                ManualPaymentProof.trx_normalized == payment.trx_normalized,
                ManualPaymentProof.decision == "APPROVED",
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="This transaction ID is already approved for another order")

    before = {
        "decision": payment.decision,
        "verified": payment.verified,
        "verified_at": payment.verified_at,
        "order_status": order.status,
    }
    decided_at = utc_now()
    payment.decision = payload.decision
    payment.decision_reason = (payload.reason or payload.note or "").strip() or None
    payment.decided_at = decided_at
    payment.decided_by_user_id = int(current_user["sub"])

    if payload.decision == "APPROVED":
        payment.verified = True
        payment.verified_at = decided_at
        if order.status == "PENDING":
            order.status = "CONFIRMED"
            order.history.append(
                OrderStatusHistory(
                    status="CONFIRMED",
                    previous_status="PENDING",
                    note=(payload.note or "Advance payment approved by operations").strip(),
                    actor_user_id=int(current_user["sub"]),
                    actor_role=str(current_user.get("role") or "operator"),
                    request_id=payload.request_id or request_id_context.get(),
                )
            )
    else:
        payment.verified = False
        payment.verified_at = None

    from .customer_payments import append_payment_decision
    from .notifications import queue_customer_notification

    append_payment_decision(
        session,
        payment,
        decision=payment.decision,
        reason=payment.decision_reason,
        actor_user_id=int(current_user["sub"]),
        actor_role=str(current_user.get("role") or "operator"),
        request_id=payload.request_id,
        submitted_by_user_id=order.user_id,
    )
    queue_customer_notification(
        session,
        user_id=order.user_id,
        category="order",
        title=f"Payment {payment.decision.lower()} for order #{order.id}",
        body=payment.decision_reason
        or f"Your payment proof is now {payment.decision.lower()}.",
        order_id=order.id,
        data={"order_status": order.status, "payment_status": payment.decision},
        template_key=f"payment_{payment.decision.lower()}",
    )

    order.updated_at = decided_at
    after = {
        "decision": payment.decision,
        "verified": payment.verified,
        "verified_at": payment.verified_at,
        "order_status": order.status,
        "reason": payment.decision_reason,
    }
    record_admin_audit(
        session,
        current_user,
        action=f"payment.{payload.decision.lower()}",
        entity_type="manual_payment",
        entity_id=payment.id,
        before=before,
        after=after,
        note=payload.reason or payload.note,
        request_id=payload.request_id,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    invalidate_admin_analytics()
    return order
