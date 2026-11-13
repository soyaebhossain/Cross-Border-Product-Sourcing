from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, or_, select
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...db import get_session
from ...models import Order, PurchaseOrder, Seller
from ...services.orders import order_loader_options
from ...services.procurement import (
    change_purchase_order_status,
    create_purchase_order,
    erp_summary,
    get_purchase_order_or_404,
    order_profit_and_loss,
    po_loader_options,
    record_goods_receipt,
    record_supplier_payment,
    reverse_supplier_payment,
    serialize_purchase_order,
    supplier_payables,
)
from .admin_operations import _page, _paginate, require_admin, require_operator

router = APIRouter()

PurchaseOrderStatus = Literal["DRAFT", "SENT", "CONFIRMED", "RECEIVED", "CLOSED", "CANCELLED"]


class PurchaseOrderCreateIn(BaseModel):
    unit_cost_origin: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    expected_at: datetime | None = None
    note: str | None = Field(default=None, max_length=1000)


class PurchaseOrderStatusIn(BaseModel):
    status: PurchaseOrderStatus
    note: str = Field(min_length=3, max_length=1000)


class GoodsReceiptIn(BaseModel):
    received_qty: int = Field(gt=0, le=1_000_000)
    accepted_qty: int = Field(ge=0, le=1_000_000)
    rejected_qty: int = Field(ge=0, le=1_000_000)
    qc_note: str | None = Field(default=None, max_length=1000)


class SupplierPaymentIn(BaseModel):
    amount_origin: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    method: str = Field(min_length=2, max_length=40)
    reference: str | None = Field(default=None, max_length=120)
    note: str = Field(min_length=3, max_length=1000)


class SupplierPaymentReverseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


@router.get("/api/admin/erp/summary/")
def admin_erp_summary(
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    return erp_summary(session)


@router.get("/api/admin/purchase-orders/")
def list_purchase_orders(
    q: str = Query(default="", max_length=120),
    po_status: str = Query(default="", alias="status", max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = (
        select(PurchaseOrder)
        .options(*po_loader_options())
        .join(Seller, Seller.id == PurchaseOrder.seller_id)
        .order_by(PurchaseOrder.id.desc())
    )
    if po_status:
        statement = statement.where(PurchaseOrder.status == po_status.upper())
    if q.strip():
        needle = f"%{q.strip().lower()}%"
        statement = statement.where(
            or_(
                PurchaseOrder.po_number.ilike(needle),
                Seller.name.ilike(needle),
                cast(PurchaseOrder.order_id, String).ilike(needle),
            )
        )
    records, total = _paginate(session, statement, page, page_size)
    return _page([serialize_purchase_order(item) for item in records], total, page, page_size)


@router.post("/api/admin/orders/{order_id}/purchase-orders/", status_code=status.HTTP_201_CREATED)
def create_order_purchase_order(
    order_id: int,
    payload: PurchaseOrderCreateIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    purchase_order = create_purchase_order(
        session,
        order_id,
        unit_cost_origin=payload.unit_cost_origin,
        expected_at=payload.expected_at,
        note=payload.note,
        current_user=user,
    )
    return serialize_purchase_order(purchase_order, detail=True)


@router.get("/api/admin/purchase-orders/{po_id}/")
def purchase_order_detail(
    po_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    return serialize_purchase_order(get_purchase_order_or_404(session, po_id), detail=True)


@router.post("/api/admin/purchase-orders/{po_id}/status/")
def set_purchase_order_status(
    po_id: int,
    payload: PurchaseOrderStatusIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    purchase_order = change_purchase_order_status(
        session, po_id, status=payload.status, note=payload.note, current_user=user
    )
    return serialize_purchase_order(purchase_order, detail=True)


@router.post("/api/admin/purchase-orders/{po_id}/receipts/", status_code=status.HTTP_201_CREATED)
def add_goods_receipt(
    po_id: int,
    payload: GoodsReceiptIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    purchase_order = record_goods_receipt(
        session,
        po_id,
        received=payload.received_qty,
        accepted=payload.accepted_qty,
        rejected=payload.rejected_qty,
        qc_note=payload.qc_note,
        current_user=user,
    )
    return serialize_purchase_order(purchase_order, detail=True)


@router.post("/api/admin/purchase-orders/{po_id}/payments/", status_code=status.HTTP_201_CREATED)
def add_supplier_payment(
    po_id: int,
    payload: SupplierPaymentIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    purchase_order = record_supplier_payment(
        session,
        po_id,
        amount_origin=payload.amount_origin,
        method=payload.method,
        reference=payload.reference,
        note=payload.note,
        current_user=user,
    )
    return serialize_purchase_order(purchase_order, detail=True)


@router.post("/api/admin/supplier-payments/{payment_id}/reverse/")
def reverse_payment_to_supplier(
    payment_id: int,
    payload: SupplierPaymentReverseIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(user)
    purchase_order = reverse_supplier_payment(session, payment_id, reason=payload.reason, current_user=user)
    return serialize_purchase_order(purchase_order, detail=True)


@router.get("/api/admin/finance/payables/")
def finance_payables(
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    return supplier_payables(session)


@router.get("/api/admin/finance/order-pnl/")
def finance_order_pnl(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = (
        select(Order)
        .options(*order_loader_options())
        .where(Order.status.notin_(("PENDING", "CANCELLED")))
        .order_by(Order.id.desc())
    )
    records, total = _paginate(session, statement, page, page_size)
    return _page([order_profit_and_loss(session, order) for order in records], total, page, page_size)
