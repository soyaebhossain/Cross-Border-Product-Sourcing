from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..models import (
    ManualPaymentProof,
    Order,
    OrderItem,
    OrderStatusHistory,
    SavedQuote,
    Shipment,
    ShipmentEvent,
)
from ..schemas import CreateOrderIn, QuoteRequestIn, SaveQuoteIn, UpdateOrderStatusIn
from .sourcing import build_quote, get_variant_or_404


CurrentUser = dict[str, Any]


def save_quote_record(session: Session, payload: SaveQuoteIn, current_user: CurrentUser) -> SavedQuote:
    variant = get_variant_or_404(session, payload.variant_id)
    snapshot = dict(payload.response)
    snapshot["status"] = "requested"
    snapshot["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
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
    )
    session.add(saved_quote)
    session.commit()
    session.refresh(saved_quote)
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
    session.delete(get_saved_quote_or_404(session, quote_id, current_user)); session.commit()


def update_saved_quote_status(session: Session, quote_id: int, value: str, current_user: CurrentUser) -> SavedQuote:
    quote = get_saved_quote_or_404(session, quote_id, current_user)
    if value in {"received", "expired"}:
        require_operator(current_user)
    snapshot = dict(quote.response or {}); snapshot["status"] = value; quote.response = snapshot
    session.add(quote); session.commit(); session.refresh(quote); return quote


def create_manual_order_record(session: Session, payload: CreateOrderIn, current_user: CurrentUser) -> Order:
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
    variant = get_variant_or_404(session, payload.variant_id)

    order = Order(
        user_id=current_user["sub"],
        country_code=payload.country.upper(),
        mode=payload.mode,
        delivery_type=payload.delivery_type,
        status="PENDING",
        total_bdt=Decimal(quote_result["breakdown"]["total_bdt"]),
        shipping_bdt=Decimal(quote_result["breakdown"]["shipping_bdt"]),
        advance_bdt=Decimal(quote_result["breakdown"]["advance_bdt"]),
        remaining_bdt=Decimal(quote_result["breakdown"]["remaining_bdt"]),
    )
    order.items.append(
        OrderItem(
            variant_id=variant.id,
            product_name=variant.product.name,
            variant_name=variant.variant_name or variant.sku or "Variant",
            qty=payload.qty,
            offer_id=payload.offer_id,
        )
    )
    order.manual_payment = ManualPaymentProof(
        channel=payload.channel,
        trx_id=payload.trx_id,
        screenshot_url=payload.screenshot_url,
        verified=False,
    )
    order.history.append(
        OrderStatusHistory(status="PENDING", note="Order created, advance pending verification")
    )
    order.shipment = Shipment()

    session.add(order)
    session.commit()
    session.refresh(order)
    return order


def order_loader_options() -> tuple[Any, ...]:
    return (
        selectinload(Order.items),
        selectinload(Order.history),
        selectinload(Order.shipment).selectinload(Shipment.events),
        joinedload(Order.manual_payment),
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


def update_order_status_record(
    session: Session,
    order_id: int,
    payload: UpdateOrderStatusIn,
    current_user: CurrentUser,
) -> Order:
    require_operator(current_user)
    order = get_order_or_404(session, order_id, current_user)
    order.status = payload.status
    order.history.append(OrderStatusHistory(status=payload.status, note=payload.note))

    if not order.shipment:
        order.shipment = Shipment()
    if payload.tracking_number:
        order.shipment.tracking_number = payload.tracking_number
    if payload.shipment_note:
        order.shipment.events.append(ShipmentEvent(status=payload.status, note=payload.shipment_note))

    session.add(order)
    session.commit()
    session.refresh(order)
    return order
