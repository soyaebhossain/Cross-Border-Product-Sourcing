from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from math import ceil
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, case, cast, distinct, func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from ...auth import get_current_user
from ...db import get_session
from ...models import (
    AccountUser,
    AdminAuditEvent,
    Category,
    Country,
    ManualPaymentProof,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    SavedQuote,
    Seller,
    SellerOffer,
)
from ...schemas import AdminPaymentDecisionIn
from ...supplier_risk import (
    HIGH_RISK_RATING_CUTOFF,
    MEDIUM_RISK_RATING_CUTOFF,
    supplier_risk_label,
)
from ...services.orders import (
    decide_manual_payment_record,
    order_loader_options,
)


router = APIRouter()
ORDER_STAGES = (
    "PENDING",
    "CONFIRMED",
    "PURCHASED",
    "IN_TRANSIT",
    "CUSTOMS",
    "LOCAL_DISPATCH",
    "DELIVERED",
    "CANCELLED",
)
PAYMENT_DECISIONS = ("PENDING", "APPROVED", "REJECTED", "REVERSED")
ACTIVE_ORDER_STATUSES = tuple(
    status for status in ORDER_STAGES if status not in {"DELIVERED", "CANCELLED"}
)
OUTSTANDING_ORDER_STATUSES = (
    "CONFIRMED",
    "PURCHASED",
    "IN_TRANSIT",
    "CUSTOMS",
    "LOCAL_DISPATCH",
)
MAX_OVERVIEW_DAYS = 366


def require_operator(user: dict[str, Any]) -> None:
    if user.get("role") not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Admin or operator access required")


def require_admin_only(user: dict[str, Any]) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")


# Backward-compatible name used by earlier code and tests.
require_admin = require_operator


def _percentage(value: int, total: int) -> float:
    return round(value / total * 100, 1) if total else 0.0


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Any) -> str:
    return format(_decimal(value), ".2f")


def _pages(total: int, page_size: int) -> int:
    return max(1, ceil(total / page_size))


def _paginate_scalars(
    session: Session,
    statement,
    *,
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = int(session.scalar(count_statement) or 0)
    items = session.scalars(
        statement.offset((page - 1) * page_size).limit(page_size)
    ).unique().all()
    return items, total


def _page_payload(items: list[dict[str, Any]], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": _pages(total, page_size),
    }


def _user_map(session: Session, user_ids: set[int]) -> dict[int, AccountUser]:
    if not user_ids:
        return {}
    return {
        item.id: item
        for item in session.scalars(select(AccountUser).where(AccountUser.id.in_(user_ids))).all()
    }


def _customer(user_id: int, users: dict[int, AccountUser]) -> dict[str, Any]:
    user = users.get(user_id)
    return {
        "id": user_id,
        "username": user.username if user else None,
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "source": "local" if user else "unavailable",
    }


def _serialize_admin_order(order: Order, users: dict[int, AccountUser]) -> dict[str, Any]:
    payment = order.manual_payment
    shipment = order.shipment
    verifier = users.get(payment.decided_by_user_id) if payment and payment.decided_by_user_id else None
    return {
        "id": order.id,
        "user_id": order.user_id,
        "customer": _customer(order.user_id, users),
        "saved_quote_id": order.saved_quote_id,
        "status": order.status,
        "country": order.country_code,
        "mode": order.mode,
        "delivery_type": order.delivery_type,
        "total_bdt": _money(order.total_bdt),
        "shipping_bdt": _money(order.shipping_bdt),
        "advance_bdt": _money(order.advance_bdt),
        "remaining_bdt": _money(order.remaining_bdt),
        "actual_cost_bdt": _money(order.actual_cost_bdt) if order.actual_cost_bdt is not None else None,
        "promised_delivery_at": order.promised_delivery_at,
        "delivered_at": order.delivered_at,
        "quality_defect_reported": order.quality_defect_reported,
        "items": [
            {
                "variant_id": item.variant_id,
                "product_name": item.product_name,
                "variant_name": item.variant_name,
                "qty": item.qty,
                "offer_id": item.offer_id,
            }
            for item in order.items
        ],
        "payment": {
            "id": payment.id,
            "channel": payment.channel,
            "trx_id": payment.trx_id,
            "screenshot_url": payment.screenshot_url,
            "verified": payment.verified,
            "decision": payment.decision,
            "decision_reason": payment.decision_reason,
            "submitted_at": payment.created_at,
            "decided_at": payment.decided_at,
            "decided_by_user_id": payment.decided_by_user_id,
            "verifier": {
                "id": verifier.id,
                "username": verifier.username,
            }
            if verifier
            else None,
        }
        if payment
        else None,
        "tracking_number": shipment.tracking_number if shipment else None,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def _serialize_payment(payment: ManualPaymentProof, users: dict[int, AccountUser]) -> dict[str, Any]:
    order = payment.order
    verifier = users.get(payment.decided_by_user_id) if payment.decided_by_user_id else None
    return {
        "id": payment.id,
        "order_id": order.id,
        "customer": _customer(order.user_id, users),
        "channel": payment.channel,
        "trx_id": payment.trx_id,
        "screenshot_url": payment.screenshot_url,
        "advance_bdt": _money(order.advance_bdt),
        "order_total_bdt": _money(order.total_bdt),
        "order_status": order.status,
        "decision": payment.decision,
        "decision_reason": payment.decision_reason,
        "verified": payment.verified,
        "submitted_at": payment.created_at,
        "decided_at": payment.decided_at,
        "decided_by_user_id": payment.decided_by_user_id,
        "verifier": {
            "id": verifier.id,
            "username": verifier.username,
        }
        if verifier
        else None,
    }


def _resolve_timezone(value: str) -> ZoneInfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown timezone: {value}") from exc


def _resolve_period(
    date_from: date | None,
    date_to: date | None,
    timezone_name: str,
    session: Session,
) -> tuple[date, date, datetime, datetime, ZoneInfo]:
    zone = _resolve_timezone(timezone_name)
    local_today = datetime.now(zone).date()
    end_date = date_to or local_today
    start_date = date_from or (end_date - timedelta(days=29))
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    if (end_date - start_date).days + 1 > MAX_OVERVIEW_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"Overview date range cannot exceed {MAX_OVERVIEW_DAYS} days",
        )
    start_utc = datetime.combine(start_date, time.min, tzinfo=zone).astimezone(timezone.utc)
    end_utc = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
    if session.bind and session.bind.dialect.name == "sqlite":
        start_utc = start_utc.replace(tzinfo=None)
        end_utc = end_utc.replace(tzinfo=None)
    return start_date, end_date, start_utc, end_utc, zone


def _order_filters(
    *,
    start_at: datetime,
    end_at: datetime,
    status: str | None,
    country: str | None,
    mode: str | None,
) -> list[Any]:
    return [
        Order.created_at >= start_at,
        Order.created_at < end_at,
        *_order_dimensions(status=status, country=country, mode=mode),
    ]


def _order_dimensions(
    *,
    status: str | None,
    country: str | None,
    mode: str | None,
) -> list[Any]:
    filters: list[Any] = []
    if status:
        if status not in ORDER_STAGES:
            raise HTTPException(status_code=422, detail="Unknown order status")
        filters.append(Order.status == status)
    if country:
        filters.append(Order.country_code == country.upper())
    if mode:
        if mode not in {"LOCAL", "BULK"}:
            raise HTTPException(status_code=422, detail="Unknown sourcing mode")
        filters.append(Order.mode == mode)
    return filters


def _period_metrics(
    session: Session,
    filters: list[Any],
    *,
    start_at: datetime,
    end_at: datetime,
    status: str | None,
    country: str | None,
    mode: str | None,
) -> dict[str, Decimal | int]:
    row = session.execute(
        select(
            func.count(Order.id),
            func.coalesce(
                func.sum(case((Order.status != "CANCELLED", Order.total_bdt), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((Order.status != "CANCELLED", Order.shipping_bdt), else_=0)),
                0,
            ),
        )
        .select_from(Order)
        .where(*filters)
    ).one()
    verified_advance = session.scalar(
        select(func.coalesce(func.sum(Order.advance_bdt), 0))
        .join(ManualPaymentProof, ManualPaymentProof.order_id == Order.id)
        .where(
            Order.status != "CANCELLED",
            ManualPaymentProof.decision == "APPROVED",
            ManualPaymentProof.verified.is_(True),
            ManualPaymentProof.verified_at >= start_at,
            ManualPaymentProof.verified_at < end_at,
            *_order_dimensions(status=status, country=country, mode=mode),
        )
    )
    return {
        "total_orders": int(row[0] or 0),
        "gross_order_value_bdt": _decimal(row[1]),
        "shipping_value_bdt": _decimal(row[2]),
        "verified_advance_bdt": _decimal(verified_advance),
    }


def _outstanding_balance(
    session: Session,
    *,
    status: str | None,
    country: str | None,
    mode: str | None,
) -> Decimal:
    return _decimal(
        session.scalar(
            select(func.coalesce(func.sum(Order.remaining_bdt), 0)).where(
                Order.status.in_(OUTSTANDING_ORDER_STATUSES),
                *_order_dimensions(status=status, country=country, mode=mode),
            )
        )
    )


def _metric_comparison(current: dict[str, Decimal | int], previous: dict[str, Decimal | int]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, current_value in current.items():
        previous_value = previous.get(key, 0)
        current_decimal = _decimal(current_value)
        previous_decimal = _decimal(previous_value)
        change = current_decimal - previous_decimal
        change_percent = (
            round(float(change / abs(previous_decimal) * 100), 2)
            if previous_decimal
            else None
        )
        result[key] = {
            "current": int(current_value) if key == "total_orders" else _money(current_value),
            "previous": int(previous_value) if key == "total_orders" else _money(previous_value),
            "change": int(change) if key == "total_orders" else _money(change),
            "change_percent": change_percent,
        }
    return result


def _local_day_expression(
    session: Session,
    column: Any,
    timezone_name: str,
    zone: ZoneInfo,
    anchor: date,
):
    if session.bind and session.bind.dialect.name == "sqlite":
        offset = zone.utcoffset(datetime.combine(anchor, time(12), tzinfo=zone)) or timedelta()
        total_minutes = int(offset.total_seconds() // 60)
        sign = "+" if total_minutes >= 0 else "-"
        hours, minutes = divmod(abs(total_minutes), 60)
        modifier = f"{sign}{hours:02d}:{minutes:02d}"
        return func.date(column, modifier)
    return func.date(func.timezone(timezone_name, column))


@router.get("/api/admin/overview/")
def overview(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    timezone_name: str = Query(default="Asia/Dhaka", alias="timezone", max_length=80),
    status: str | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    mode: str | None = Query(default=None),
    compare: bool = Query(default=True),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    start_date, end_date, start_at, end_at, zone = _resolve_period(
        date_from,
        date_to,
        timezone_name,
        session,
    )
    filters = _order_filters(
        start_at=start_at,
        end_at=end_at,
        status=status,
        country=country,
        mode=mode,
    )
    metrics = _period_metrics(
        session,
        filters,
        start_at=start_at,
        end_at=end_at,
        status=status,
        country=country,
        mode=mode,
    )
    outstanding_balance = _outstanding_balance(
        session,
        status=status,
        country=country,
        mode=mode,
    )

    duration_days = (end_date - start_date).days + 1
    previous_end_date = start_date - timedelta(days=1)
    previous_start_date = previous_end_date - timedelta(days=duration_days - 1)
    _, _, previous_start, previous_end, _ = _resolve_period(
        previous_start_date,
        previous_end_date,
        timezone_name,
        session,
    )
    previous_filters = _order_filters(
        start_at=previous_start,
        end_at=previous_end,
        status=status,
        country=country,
        mode=mode,
    )
    previous_metrics = (
        _period_metrics(
            session,
            previous_filters,
            start_at=previous_start,
            end_at=previous_end,
            status=status,
            country=country,
            mode=mode,
        )
        if compare
        else {}
    )

    order_day_expression = _local_day_expression(
        session, Order.created_at, timezone_name, zone, start_date
    ).label("local_day")
    daily_order_rows = session.execute(
        select(
            order_day_expression,
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_bdt), 0),
            func.coalesce(func.sum(Order.shipping_bdt), 0),
        )
        .select_from(Order)
        .where(*filters, Order.status != "CANCELLED")
        .group_by(order_day_expression)
        .order_by(order_day_expression)
    ).all()
    daily_by_date = {
        str(row[0]): {
            "orders": int(row[1]),
            "order_value_bdt": _money(row[2]),
            "shipping_bdt": _money(row[3]),
            "verified_advance_bdt": "0.00",
        }
        for row in daily_order_rows
    }
    payment_day_expression = _local_day_expression(
        session, ManualPaymentProof.verified_at, timezone_name, zone, start_date
    ).label("local_day")
    daily_payment_rows = session.execute(
        select(
            payment_day_expression,
            func.coalesce(func.sum(Order.advance_bdt), 0),
        )
        .join(Order, Order.id == ManualPaymentProof.order_id)
        .where(
            Order.status != "CANCELLED",
            ManualPaymentProof.decision == "APPROVED",
            ManualPaymentProof.verified.is_(True),
            ManualPaymentProof.verified_at >= start_at,
            ManualPaymentProof.verified_at < end_at,
            *_order_dimensions(status=status, country=country, mode=mode),
        )
        .group_by(payment_day_expression)
        .order_by(payment_day_expression)
    ).all()
    for row in daily_payment_rows:
        item = daily_by_date.setdefault(
            str(row[0]),
            {
                "orders": 0,
                "order_value_bdt": "0.00",
                "shipping_bdt": "0.00",
                "verified_advance_bdt": "0.00",
            },
        )
        item["verified_advance_bdt"] = _money(row[1])
    daily_revenue = []
    cursor = start_date
    while cursor <= end_date:
        key = cursor.isoformat()
        values = daily_by_date.get(
            key,
            {
                "orders": 0,
                "order_value_bdt": "0.00",
                "shipping_bdt": "0.00",
                "verified_advance_bdt": "0.00",
            },
        )
        daily_revenue.append({"date": key, **values})
        cursor += timedelta(days=1)

    stage_counts = {
        row[0]: int(row[1])
        for row in session.execute(
            select(Order.status, func.count(Order.id))
            .where(*filters)
            .group_by(Order.status)
        )
    }
    total_orders = int(metrics["total_orders"])

    delivery_rows = session.execute(
        select(
            Order.delivery_type,
            func.count(distinct(Order.id)),
            func.coalesce(func.sum(OrderItem.qty), 0),
        )
        .join(OrderItem, OrderItem.order_id == Order.id)
        .where(*filters, Order.status != "CANCELLED")
        .group_by(Order.delivery_type)
        .order_by(func.count(distinct(Order.id)).desc())
    ).all()
    active_delivery_orders = sum(int(row[1]) for row in delivery_rows)
    total_units = sum(int(row[2]) for row in delivery_rows)

    flow_expression = case(
        (ManualPaymentProof.id.is_not(None), "Manual payment"),
        else_="Other flow",
    ).label("payment_flow")
    flow_counts = {
        row[0]: int(row[1])
        for row in session.execute(
            select(flow_expression, func.count(distinct(Order.id)))
            .select_from(Order)
            .outerjoin(ManualPaymentProof, ManualPaymentProof.order_id == Order.id)
            .where(*filters)
            .group_by(flow_expression)
        )
    }

    top_items = [
        {"name": row[0], "units": int(row[1])}
        for row in session.execute(
            select(OrderItem.product_name, func.sum(OrderItem.qty))
            .join(Order, Order.id == OrderItem.order_id)
            .where(*filters, Order.status != "CANCELLED")
            .group_by(OrderItem.product_name)
            .order_by(func.sum(OrderItem.qty).desc(), OrderItem.product_name.asc())
            .limit(8)
        )
    ]
    country_names = dict(session.execute(select(Country.code, Country.name)).all())
    top_countries = [
        {
            "country": country_names.get(row[0], row[0]),
            "country_code": row[0],
            "orders": int(row[1]),
        }
        for row in session.execute(
            select(Order.country_code, func.count(Order.id))
            .where(*filters, Order.status != "CANCELLED")
            .group_by(Order.country_code)
            .order_by(func.count(Order.id).desc(), Order.country_code.asc())
            .limit(5)
        )
    ]

    sellers = session.scalars(
        select(Seller)
        .options(joinedload(Seller.country))
        .order_by(Seller.rating.asc(), Seller.id.asc())
        .limit(10)
    ).all()
    recent_orders = session.scalars(
        select(Order)
        .options(*order_loader_options())
        .where(*filters)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(12)
    ).unique().all()
    recent_users = _user_map(
        session,
        {
            user_id
            for order in recent_orders
            for user_id in (
                order.user_id,
                order.manual_payment.decided_by_user_id if order.manual_payment else None,
            )
            if user_id is not None
        },
    )

    pending_payment_statement = (
        select(ManualPaymentProof)
        .join(Order, Order.id == ManualPaymentProof.order_id)
        .options(joinedload(ManualPaymentProof.order))
        .where(
            ManualPaymentProof.decision == "PENDING",
            Order.status != "CANCELLED",
        )
        .order_by(ManualPaymentProof.created_at.asc(), ManualPaymentProof.id.asc())
    )
    pending_payment_total = int(
        session.scalar(
            select(func.count()).select_from(pending_payment_statement.order_by(None).subquery())
        )
        or 0
    )
    payment_preview = session.scalars(pending_payment_statement.limit(12)).unique().all()
    payment_users = _user_map(
        session,
        {
            user_id
            for payment in payment_preview
            for user_id in (payment.order.user_id, payment.decided_by_user_id)
            if user_id is not None
        },
    )

    quote_filters = [SavedQuote.created_at >= start_at, SavedQuote.created_at < end_at]
    quote_count = int(
        session.scalar(select(func.count(SavedQuote.id)).where(*quote_filters)) or 0
    )
    active_orders = int(
        session.scalar(
            select(func.count(Order.id)).where(Order.status.in_(ACTIVE_ORDER_STATUSES))
        )
        or 0
    )

    cards = {
        "total_orders": total_orders,
        "products": int(
            session.scalar(
                select(func.count(Product.id)).where(Product.is_active.is_(True))
            )
            or 0
        ),
        "suppliers": int(
            session.scalar(select(func.count(Seller.id)).where(Seller.is_active.is_(True)))
            or 0
        ),
        "offers": int(
            session.scalar(
                select(func.count(SellerOffer.id)).where(SellerOffer.is_active.is_(True))
            )
            or 0
        ),
        "saved_quotes": quote_count,
        "active_orders": active_orders,
        "gross_order_value_bdt": _money(metrics["gross_order_value_bdt"]),
        "verified_advance_bdt": _money(metrics["verified_advance_bdt"]),
        "outstanding_bdt": _money(outstanding_balance),
        "shipping_value_bdt": _money(metrics["shipping_value_bdt"]),
    }
    return {
        "range": {
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "timezone": timezone_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "comparison_date_from": previous_start_date.isoformat() if compare else None,
            "comparison_date_to": previous_end_date.isoformat() if compare else None,
            "filters": {"status": status, "country": country, "mode": mode},
        },
        "cards": cards,
        "comparison": _metric_comparison(metrics, previous_metrics) if compare else None,
        "daily_revenue": daily_revenue,
        "top_items": top_items,
        "order_stages": [
            {
                "status": stage,
                "count": stage_counts.get(stage, 0),
                "percentage": _percentage(stage_counts.get(stage, 0), total_orders),
            }
            for stage in ORDER_STAGES
        ],
        "order_types": [
            {
                "type": flow,
                "count": flow_counts.get(flow, 0),
                "percentage": _percentage(flow_counts.get(flow, 0), total_orders),
            }
            for flow in ("Manual payment", "Other flow")
        ],
        "delivery_options": [
            {
                "type": row[0],
                "orders": int(row[1]),
                "orders_percentage": _percentage(int(row[1]), active_delivery_orders),
                "units": int(row[2]),
                "units_percentage": _percentage(int(row[2]), total_units),
            }
            for row in delivery_rows
        ],
        "top_countries": top_countries,
        "supplier_alerts": [
            {
                "id": seller.id,
                "name": seller.name,
                "country": seller.country.name,
                "rating": float(seller.rating),
                "risk": supplier_risk_label(seller.rating),
            }
            for seller in sellers
        ],
        "recent_orders": [
            {
                **_serialize_admin_order(order, recent_users),
                "payment_verified": bool(order.manual_payment and order.manual_payment.verified),
            }
            for order in recent_orders
        ],
        "payment_queue": [
            {
                **_serialize_payment(payment, payment_users),
                # Legacy keys retained for the current frontend.
                "order_id": payment.order.id,
                "advance_bdt": _money(payment.order.advance_bdt),
            }
            for payment in payment_preview
        ],
        "payment_queue_total": pending_payment_total,
    }


@router.get("/api/admin/orders/")
def list_admin_orders(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    status: str | None = Query(default=None),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    mode: str | None = Query(default=None),
    payment_decision: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = select(Order).options(*order_loader_options())
    if status:
        if status not in ORDER_STAGES:
            raise HTTPException(status_code=422, detail="Unknown order status")
        statement = statement.where(Order.status == status)
    if country:
        statement = statement.where(Order.country_code == country.upper())
    if mode:
        if mode not in {"LOCAL", "BULK"}:
            raise HTTPException(status_code=422, detail="Unknown sourcing mode")
        statement = statement.where(Order.mode == mode)
    if payment_decision:
        if payment_decision not in PAYMENT_DECISIONS:
            raise HTTPException(status_code=422, detail="Unknown payment decision")
        statement = statement.where(
            Order.manual_payment.has(ManualPaymentProof.decision == payment_decision)
        )
    if date_from:
        statement = statement.where(Order.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        statement = statement.where(
            Order.created_at < datetime.combine(date_to + timedelta(days=1), time.min)
        )
    search = q.strip()
    if search:
        matching_users = select(AccountUser.id).where(
            or_(
                AccountUser.username.ilike(f"%{search}%"),
                AccountUser.email.ilike(f"%{search}%"),
                AccountUser.phone.ilike(f"%{search}%"),
            )
        )
        statement = statement.where(
            or_(
                cast(Order.id, String).ilike(f"%{search}%"),
                Order.country_code.ilike(f"%{search}%"),
                Order.user_id.in_(matching_users),
                Order.items.any(OrderItem.product_name.ilike(f"%{search}%")),
                Order.manual_payment.has(ManualPaymentProof.trx_id.ilike(f"%{search}%")),
            )
        )
    statement = statement.order_by(Order.created_at.desc(), Order.id.desc())
    orders, total = _paginate_scalars(session, statement, page=page, page_size=page_size)
    users = _user_map(
        session,
        {
            user_id
            for order in orders
            for user_id in (
                order.user_id,
                order.manual_payment.decided_by_user_id if order.manual_payment else None,
            )
            if user_id is not None
        },
    )
    return _page_payload(
        [_serialize_admin_order(order, users) for order in orders],
        total,
        page,
        page_size,
    )


@router.get("/api/admin/payments/")
def list_admin_payments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    decision: str | None = Query(default="PENDING"),
    channel: str | None = Query(default=None, max_length=20),
    q: str = Query(default="", max_length=120),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = (
        select(ManualPaymentProof)
        .join(Order, Order.id == ManualPaymentProof.order_id)
        .options(joinedload(ManualPaymentProof.order))
    )
    if decision:
        if decision not in PAYMENT_DECISIONS:
            raise HTTPException(status_code=422, detail="Unknown payment decision")
        statement = statement.where(ManualPaymentProof.decision == decision)
    if channel:
        statement = statement.where(func.lower(ManualPaymentProof.channel) == channel.casefold())
    search = q.strip()
    if search:
        matching_users = select(AccountUser.id).where(
            or_(
                AccountUser.username.ilike(f"%{search}%"),
                AccountUser.email.ilike(f"%{search}%"),
                AccountUser.phone.ilike(f"%{search}%"),
            )
        )
        statement = statement.where(
            or_(
                cast(Order.id, String).ilike(f"%{search}%"),
                ManualPaymentProof.trx_id.ilike(f"%{search}%"),
                Order.user_id.in_(matching_users),
            )
        )
    statement = statement.order_by(
        ManualPaymentProof.created_at.asc()
        if decision == "PENDING"
        else ManualPaymentProof.created_at.desc(),
        ManualPaymentProof.id.asc(),
    )
    payments, total = _paginate_scalars(session, statement, page=page, page_size=page_size)
    users = _user_map(
        session,
        {
            user_id
            for payment in payments
            for user_id in (payment.order.user_id, payment.decided_by_user_id)
            if user_id is not None
        },
    )
    return _page_payload(
        [_serialize_payment(payment, users) for payment in payments],
        total,
        page,
        page_size,
    )


@router.get("/api/admin/quotes/")
def list_admin_quotes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    status: str | None = Query(default=None, max_length=20),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    mode: str | None = Query(default=None),
    expired: bool | None = Query(default=None),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = select(SavedQuote)
    if status:
        statement = statement.where(SavedQuote.status == status)
    if country:
        statement = statement.where(SavedQuote.country_code == country.upper())
    if mode:
        statement = statement.where(SavedQuote.mode == mode)
    if expired is True:
        statement = statement.where(SavedQuote.expires_at < datetime.now(timezone.utc))
    elif expired is False:
        statement = statement.where(
            or_(SavedQuote.expires_at.is_(None), SavedQuote.expires_at >= datetime.now(timezone.utc))
        )
    search = q.strip()
    if search:
        matching_users = select(AccountUser.id).where(
            or_(
                AccountUser.username.ilike(f"%{search}%"),
                AccountUser.email.ilike(f"%{search}%"),
                AccountUser.phone.ilike(f"%{search}%"),
            )
        )
        statement = statement.where(
            or_(
                cast(SavedQuote.id, String).ilike(f"%{search}%"),
                SavedQuote.product_name.ilike(f"%{search}%"),
                SavedQuote.variant_name.ilike(f"%{search}%"),
                SavedQuote.user_id.in_(matching_users),
            )
        )
    statement = statement.order_by(SavedQuote.created_at.desc(), SavedQuote.id.desc())
    quotes, total = _paginate_scalars(session, statement, page=page, page_size=page_size)
    users = _user_map(session, {quote.user_id for quote in quotes})
    items = [
        {
            "id": quote.id,
            "customer": _customer(quote.user_id, users),
            "product_name": quote.product_name,
            "variant_name": quote.variant_name,
            "variant_id": quote.variant_id,
            "country": quote.country_code,
            "mode": quote.mode,
            "delivery_type": quote.delivery_type,
            "qty": quote.qty,
            "status": quote.status,
            "expires_at": quote.expires_at,
            "created_at": quote.created_at,
            "updated_at": quote.updated_at,
            "order_ids": [order.id for order in quote.orders],
            "total_bdt": _money((quote.response or {}).get("breakdown", {}).get("total_bdt")),
        }
        for quote in quotes
    ]
    return _page_payload(items, total, page, page_size)


@router.get("/api/admin/products/")
def list_admin_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    category: str | None = Query(default=None, max_length=120),
    active: bool | None = Query(default=None),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = select(Product).options(
        joinedload(Product.category),
        selectinload(Product.variants),
    )
    if category:
        statement = statement.where(Product.category.has(Category.slug == category))
    if active is not None:
        statement = statement.where(Product.is_active.is_(active))
    search = q.strip()
    if search:
        statement = statement.where(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.slug.ilike(f"%{search}%"),
                Product.model.ilike(f"%{search}%"),
                Product.variants.any(ProductVariant.sku.ilike(f"%{search}%")),
            )
        )
    statement = statement.order_by(Product.name.asc(), Product.id.asc())
    products, total = _paginate_scalars(session, statement, page=page, page_size=page_size)
    product_ids = [product.id for product in products]
    offer_counts = {
        row[0]: int(row[1])
        for row in session.execute(
            select(ProductVariant.product_id, func.count(SellerOffer.id))
            .join(SellerOffer, SellerOffer.variant_id == ProductVariant.id)
            .where(
                ProductVariant.product_id.in_(product_ids),
                SellerOffer.is_active.is_(True),
            )
            .group_by(ProductVariant.product_id)
        )
    } if product_ids else {}
    items = [
        {
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "model": product.model,
            "image": product.image,
            "category": {
                "id": product.category.id,
                "name": product.category.name,
                "slug": product.category.slug,
            },
            "variant_count": len(product.variants),
            "offer_count": offer_counts.get(product.id, 0),
            "is_active": product.is_active,
            "archived_at": product.archived_at,
        }
        for product in products
    ]
    return _page_payload(items, total, page, page_size)


@router.get("/api/admin/suppliers/")
def list_admin_suppliers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    risk: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    statement = select(Seller).options(joinedload(Seller.country))
    if active is not None:
        statement = statement.where(Seller.is_active.is_(active))
    if country:
        statement = statement.where(Seller.country.has(Country.code == country.upper()))
    if risk == "High":
        statement = statement.where(Seller.rating < HIGH_RISK_RATING_CUTOFF)
    elif risk == "Medium":
        statement = statement.where(
            Seller.rating >= HIGH_RISK_RATING_CUTOFF,
            Seller.rating < MEDIUM_RISK_RATING_CUTOFF,
        )
    elif risk == "Low":
        statement = statement.where(Seller.rating >= MEDIUM_RISK_RATING_CUTOFF)
    elif risk:
        raise HTTPException(status_code=422, detail="Unknown supplier risk")
    search = q.strip()
    if search:
        statement = statement.where(
            or_(
                Seller.name.ilike(f"%{search}%"),
                Seller.note.ilike(f"%{search}%"),
                Seller.country.has(Country.name.ilike(f"%{search}%")),
            )
        )
    statement = statement.order_by(Seller.rating.asc(), Seller.name.asc())
    sellers, total = _paginate_scalars(session, statement, page=page, page_size=page_size)
    seller_ids = [seller.id for seller in sellers]
    offer_counts = {
        row[0]: int(row[1])
        for row in session.execute(
            select(SellerOffer.seller_id, func.count(SellerOffer.id))
            .where(
                SellerOffer.seller_id.in_(seller_ids),
                SellerOffer.is_active.is_(True),
            )
            .group_by(SellerOffer.seller_id)
        )
    } if seller_ids else {}
    items = [
        {
            "id": seller.id,
            "name": seller.name,
            "country": {"code": seller.country.code, "name": seller.country.name},
            "rating": float(seller.rating),
            "risk": supplier_risk_label(seller.rating),
            "note": seller.note,
            "offer_count": offer_counts.get(seller.id, 0),
            "is_active": seller.is_active,
            "archived_at": seller.archived_at,
        }
        for seller in sellers
    ]
    return _page_payload(items, total, page, page_size)


@router.get("/api/admin/users/")
def list_admin_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    q: str = Query(default="", max_length=120),
    role: str | None = Query(default=None, max_length=20),
    is_active: bool | None = Query(default=None),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin_only(user)
    statement = select(AccountUser)
    if role:
        statement = statement.where(AccountUser.role == role)
    if is_active is not None:
        statement = statement.where(AccountUser.is_active.is_(is_active))
    search = q.strip()
    if search:
        statement = statement.where(
            or_(
                AccountUser.username.ilike(f"%{search}%"),
                AccountUser.email.ilike(f"%{search}%"),
                AccountUser.phone.ilike(f"%{search}%"),
            )
        )
    statement = statement.order_by(AccountUser.created_at.desc(), AccountUser.id.desc())
    users, total = _paginate_scalars(session, statement, page=page, page_size=page_size)
    items = [
        {
            "id": account.id,
            "username": account.username,
            "email": account.email,
            "phone": account.phone,
            "role": account.role,
            "is_active": account.is_active,
            "is_staff": account.is_staff,
            "is_superuser": account.is_superuser,
            "created_at": account.created_at,
        }
        for account in users
    ]
    return _page_payload(items, total, page, page_size)


@router.get("/api/admin/audit-events/")
def list_admin_audit_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    action: str | None = Query(default=None, max_length=80),
    entity_type: str | None = Query(default=None, max_length=50),
    actor_user_id: int | None = Query(default=None, ge=1),
    q: str = Query(default="", max_length=120),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin_only(user)
    statement = select(AdminAuditEvent)
    if action:
        statement = statement.where(AdminAuditEvent.action == action)
    if entity_type:
        statement = statement.where(AdminAuditEvent.entity_type == entity_type)
    if actor_user_id:
        statement = statement.where(AdminAuditEvent.actor_user_id == actor_user_id)
    search = q.strip()
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                AdminAuditEvent.action.ilike(pattern),
                AdminAuditEvent.entity_type.ilike(pattern),
                cast(AdminAuditEvent.entity_id, String).ilike(pattern),
                AdminAuditEvent.note.ilike(pattern),
                AdminAuditEvent.actor_role.ilike(pattern),
            )
        )
    statement = statement.order_by(AdminAuditEvent.created_at.desc(), AdminAuditEvent.id.desc())
    events, total = _paginate_scalars(session, statement, page=page, page_size=page_size)
    items = [
        {
            "id": event.id,
            "actor_user_id": event.actor_user_id,
            "actor_role": event.actor_role,
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "request_id": event.request_id,
            "before": event.before_data,
            "after": event.after_data,
            "note": event.note,
            "created_at": event.created_at,
        }
        for event in events
    ]
    return _page_payload(items, total, page, page_size)


@router.patch("/api/admin/orders/{order_id}/payment-decision/")
def decide_payment(
    order_id: int,
    payload: AdminPaymentDecisionIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    order = decide_manual_payment_record(session, order_id, payload, user)
    users = _user_map(
        session,
        {
            user_id
            for user_id in (
                order.user_id,
                order.manual_payment.decided_by_user_id if order.manual_payment else None,
            )
            if user_id is not None
        },
    )
    return _serialize_admin_order(order, users)


@router.patch("/api/admin/payments/{payment_id}/decision/")
def decide_payment_by_id(
    payment_id: int,
    payload: AdminPaymentDecisionIn,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    payment = session.get(ManualPaymentProof, payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment proof not found")
    order = decide_manual_payment_record(session, payment.order_id, payload, user)
    users = _user_map(
        session,
        {
            user_id
            for user_id in (
                order.user_id,
                order.manual_payment.decided_by_user_id if order.manual_payment else None,
            )
            if user_id is not None
        },
    )
    return _serialize_admin_order(order, users)


@router.post("/api/admin/orders/{order_id}/verify-payment/")
def verify_payment(
    order_id: int,
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Compatibility wrapper for the existing frontend.

    New clients should use ``payment-decision`` and provide an explicit reason.
    """

    require_operator(user)
    order = decide_manual_payment_record(
        session,
        order_id,
        AdminPaymentDecisionIn(
            decision="APPROVED",
            note="Advance payment approved from the compatibility action",
        ),
        user,
    )
    return {
        "id": order.id,
        "status": order.status,
        "payment_verified": bool(order.manual_payment and order.manual_payment.verified),
        "payment_decision": order.manual_payment.decision if order.manual_payment else None,
    }
