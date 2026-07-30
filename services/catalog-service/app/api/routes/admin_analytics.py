from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from math import ceil
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.orm import Session

from ...analytics_cache import admin_analytics_cache
from ...auth import get_current_user
from ...db import get_session
from ...models import (
    Category,
    ManualPaymentProof,
    Order,
    OrderItem,
    PaymentAdjustment,
    Product,
    ProductVariant,
    SavedQuote,
    Seller,
    SellerOffer,
)


router = APIRouter()
MAX_RANGE_DAYS = 366
ACTIVE_STATUSES = (
    "PENDING",
    "CONFIRMED",
    "PURCHASED",
    "IN_TRANSIT",
    "CUSTOMS",
    "LOCAL_DISPATCH",
)
METRIC_VERSION = "2026-07-30.1"
METRIC_DEFINITIONS = {
    "gross_order_value_bdt": (
        "Sum of non-cancelled order total_bdt for orders created in the selected window; "
        "booked value, not recognized revenue."
    ),
    "verified_cash_bdt": (
        "Approved advance payments verified in the selected window, less currently posted "
        "refunds created in that window."
    ),
    "outstanding_bdt": (
        "Point-in-time non-cancelled order value less net verified cash. It is labelled as-of, "
        "not treated as a window flow."
    ),
    "refunds_bdt": "Posted refund adjustments created in the selected window; reversed refunds are excluded.",
    "realized_margin_bdt": (
        "Delivered order value minus entered actual cost, only for delivered orders with "
        "actual_cost_bdt populated."
    ),
    "quote_to_order_conversion_pct": (
        "Distinct quotes created in the window that link to a non-cancelled order divided by "
        "eligible saved quotes created in the same window."
    ),
    "average_delivery_days": (
        "Average elapsed days from order creation to delivered_at for delivered orders with a "
        "recorded delivered_at."
    ),
    "supplier_sla_pct": (
        "Delivered supplier-linked orders delivered on or before promised_delivery_at divided "
        "by supplier-linked delivered orders with both timestamps."
    ),
    "supplier_defect_rate_pct": (
        "Delivered supplier-linked orders marked quality_defect_reported divided by delivered "
        "supplier-linked orders."
    ),
    "supplier_reliability_pct": (
        "Equal-weight average of on-time SLA and quality-success percentages when both are "
        "available; otherwise the available outcome measure. No outcomes returns null."
    ),
}


def require_operator(user: dict[str, Any]) -> None:
    if user.get("role") not in {"admin", "operator"}:
        raise HTTPException(status_code=403, detail="Admin or operator access required")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def _money(value: Any) -> str:
    return format(_decimal(value), ".2f")


def _percent(numerator: Any, denominator: Any) -> float | None:
    denominator_value = _decimal(denominator)
    if not denominator_value:
        return None
    return round(float(_decimal(numerator) / denominator_value * 100), 2)


def _comparison(current: Any, previous: Any, *, money: bool = True) -> dict[str, Any]:
    current_value = _decimal(current)
    previous_value = _decimal(previous)
    change = current_value - previous_value
    return {
        "current": _money(current_value) if money else int(current_value),
        "previous": _money(previous_value) if money else int(previous_value),
        "change": _money(change) if money else int(change),
        "change_percent": (
            round(float(change / abs(previous_value) * 100), 2)
            if previous_value
            else None
        ),
    }


def _period(
    date_from: date | None,
    date_to: date | None,
    days: int | None,
    timezone_name: str,
    session: Session,
) -> tuple[date, date, datetime, datetime, ZoneInfo]:
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown timezone: {timezone_name}") from exc
    today = datetime.now(zone).date()
    end = date_to or today
    start = date_from or end - timedelta(days=(days or 30) - 1)
    if start > end:
        raise HTTPException(status_code=422, detail="date_from must not be after date_to")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=f"Date range cannot exceed {MAX_RANGE_DAYS} days")
    start_at = datetime.combine(start, time.min, tzinfo=zone).astimezone(timezone.utc)
    end_at = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone).astimezone(timezone.utc)
    if session.bind and session.bind.dialect.name == "sqlite":
        start_at = start_at.replace(tzinfo=None)
        end_at = end_at.replace(tzinfo=None)
    return start, end, start_at, end_at, zone


def _filters(
    start_at: datetime,
    end_at: datetime,
    *,
    status: str | None,
    country: str | None,
    mode: str | None,
) -> list[Any]:
    result: list[Any] = [Order.created_at >= start_at, Order.created_at < end_at]
    if status:
        result.append(Order.status == status)
    if country:
        result.append(Order.country_code == country.upper())
    if mode:
        if mode not in {"LOCAL", "BULK"}:
            raise HTTPException(status_code=422, detail="Unknown sourcing mode")
        result.append(Order.mode == mode)
    return result


def _day_expression(
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
        return func.date(column, f"{sign}{hours:02d}:{minutes:02d}")
    return func.date(func.timezone(timezone_name, column))


def _daily_financials(
    session: Session,
    *,
    start: date,
    end: date,
    start_at: datetime,
    end_at: datetime,
    timezone_name: str,
    zone: ZoneInfo,
    status: str | None,
    country: str | None,
    mode: str | None,
) -> list[dict[str, Any]]:
    dimensions: list[Any] = []
    if status:
        dimensions.append(Order.status == status)
    if country:
        dimensions.append(Order.country_code == country.upper())
    if mode:
        dimensions.append(Order.mode == mode)
    order_day = _day_expression(
        session, Order.created_at, timezone_name, zone, start
    ).label("local_day")
    order_rows = session.execute(
        select(
            order_day,
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_bdt), 0),
        )
        .where(
            Order.created_at >= start_at,
            Order.created_at < end_at,
            Order.status != "CANCELLED",
            *dimensions,
        )
        .group_by(order_day)
    ).all()
    payment_day = _day_expression(
        session, ManualPaymentProof.verified_at, timezone_name, zone, start
    ).label("local_day")
    payment_rows = session.execute(
        select(payment_day, func.coalesce(func.sum(Order.advance_bdt), 0))
        .join(Order, Order.id == ManualPaymentProof.order_id)
        .where(
            ManualPaymentProof.decision == "APPROVED",
            ManualPaymentProof.verified.is_(True),
            ManualPaymentProof.verified_at >= start_at,
            ManualPaymentProof.verified_at < end_at,
            Order.status != "CANCELLED",
            *dimensions,
        )
        .group_by(payment_day)
    ).all()
    refund_day = _day_expression(
        session, PaymentAdjustment.created_at, timezone_name, zone, start
    ).label("local_day")
    refund_rows = session.execute(
        select(
            refund_day,
            func.coalesce(func.sum(PaymentAdjustment.amount_bdt), 0),
        )
        .join(Order, Order.id == PaymentAdjustment.order_id)
        .where(
            PaymentAdjustment.adjustment_type == "REFUND",
            PaymentAdjustment.status == "POSTED",
            PaymentAdjustment.created_at >= start_at,
            PaymentAdjustment.created_at < end_at,
            Order.status != "CANCELLED",
            *dimensions,
        )
        .group_by(refund_day)
    ).all()
    values: dict[str, dict[str, Any]] = {}
    for row in order_rows:
        values[str(row[0])] = {
            "orders": int(row[1] or 0),
            "gross_order_value_bdt": _money(row[2]),
            "verified_cash_bdt": "0.00",
            "refunds_bdt": "0.00",
        }
    for row in payment_rows:
        item = values.setdefault(
            str(row[0]),
            {
                "orders": 0,
                "gross_order_value_bdt": "0.00",
                "verified_cash_bdt": "0.00",
                "refunds_bdt": "0.00",
            },
        )
        item["verified_cash_bdt"] = _money(row[1])
    for row in refund_rows:
        item = values.setdefault(
            str(row[0]),
            {
                "orders": 0,
                "gross_order_value_bdt": "0.00",
                "verified_cash_bdt": "0.00",
                "refunds_bdt": "0.00",
            },
        )
        item["refunds_bdt"] = _money(row[1])
        item["verified_cash_bdt"] = _money(
            _decimal(item["verified_cash_bdt"]) - _decimal(row[1])
        )
    result = []
    cursor = start
    while cursor <= end:
        result.append(
            {
                "date": cursor.isoformat(),
                **values.get(
                    cursor.isoformat(),
                    {
                        "orders": 0,
                        "gross_order_value_bdt": "0.00",
                        "verified_cash_bdt": "0.00",
                        "refunds_bdt": "0.00",
                    },
                ),
            }
        )
        cursor += timedelta(days=1)
    return result


def _financial_metrics(
    session: Session,
    filters: list[Any],
    start_at: datetime,
    end_at: datetime,
    *,
    status: str | None,
    country: str | None,
    mode: str | None,
) -> dict[str, Any]:
    dimensional: list[Any] = []
    if status:
        dimensional.append(Order.status == status)
    if country:
        dimensional.append(Order.country_code == country.upper())
    if mode:
        dimensional.append(Order.mode == mode)
    order_row = session.execute(
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
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                Order.status == "DELIVERED",
                                Order.actual_cost_bdt.is_not(None),
                            ),
                            Order.total_bdt - Order.actual_cost_bdt,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Order.status == "DELIVERED",
                                Order.actual_cost_bdt.is_not(None),
                            ),
                            Order.id,
                        )
                    )
                )
            ),
        ).where(*filters)
    ).one()
    approved_cash = session.scalar(
        select(func.coalesce(func.sum(Order.advance_bdt), 0))
        .join(ManualPaymentProof, ManualPaymentProof.order_id == Order.id)
        .where(
            Order.status != "CANCELLED",
            ManualPaymentProof.decision == "APPROVED",
            ManualPaymentProof.verified.is_(True),
            ManualPaymentProof.verified_at >= start_at,
            ManualPaymentProof.verified_at < end_at,
            *dimensional,
        )
    )
    # Refunds are event flows and therefore use adjustment creation time while
    # preserving the selected order dimensions.
    refunds = session.scalar(
        select(func.coalesce(func.sum(PaymentAdjustment.amount_bdt), 0))
        .join(Order, Order.id == PaymentAdjustment.order_id)
        .where(
            PaymentAdjustment.adjustment_type == "REFUND",
            PaymentAdjustment.status == "POSTED",
            PaymentAdjustment.created_at >= start_at,
            PaymentAdjustment.created_at < end_at,
            *dimensional,
        )
    )
    # The point-in-time outstanding card intentionally does not use the report
    # window. It remains filterable by status/country/mode.
    point_in_time_value = session.scalar(
        select(func.coalesce(func.sum(Order.total_bdt), 0)).where(
            Order.status != "CANCELLED", *dimensional
        )
    )
    point_in_time_cash = session.scalar(
        select(func.coalesce(func.sum(Order.advance_bdt), 0))
        .join(ManualPaymentProof, ManualPaymentProof.order_id == Order.id)
        .where(
            Order.status != "CANCELLED",
            ManualPaymentProof.decision == "APPROVED",
            ManualPaymentProof.verified.is_(True),
            *dimensional,
        )
    )
    point_in_time_refunds = session.scalar(
        select(func.coalesce(func.sum(PaymentAdjustment.amount_bdt), 0))
        .join(Order, Order.id == PaymentAdjustment.order_id)
        .where(
            PaymentAdjustment.adjustment_type == "REFUND",
            PaymentAdjustment.status == "POSTED",
            Order.status != "CANCELLED",
            *dimensional,
        )
    )
    gross = _decimal(order_row[1])
    verified_cash = max(Decimal("0"), _decimal(approved_cash) - _decimal(refunds))
    outstanding = max(
        Decimal("0"),
        _decimal(point_in_time_value)
        - _decimal(point_in_time_cash)
        + _decimal(point_in_time_refunds),
    )
    return {
        "total_orders": int(order_row[0] or 0),
        "gross_order_value_bdt": gross,
        "shipping_value_bdt": _decimal(order_row[2]),
        "verified_cash_bdt": verified_cash,
        "refunds_bdt": _decimal(refunds),
        "outstanding_bdt": outstanding,
        "realized_margin_bdt": _decimal(order_row[3]),
        "realized_margin_orders": int(order_row[4] or 0),
    }


def _funnel(
    session: Session,
    start_at: datetime,
    end_at: datetime,
    *,
    country: str | None,
    mode: str | None,
) -> dict[str, Any]:
    quote_conditions: list[Any] = [
        SavedQuote.created_at >= start_at,
        SavedQuote.created_at < end_at,
        SavedQuote.response.is_not(None),
    ]
    if country:
        quote_conditions.append(SavedQuote.country_code == country.upper())
    if mode:
        quote_conditions.append(SavedQuote.mode == mode)
    quotes = int(
        session.scalar(select(func.count(SavedQuote.id)).where(*quote_conditions)) or 0
    )
    ordered = int(
        session.scalar(
            select(func.count(distinct(Order.saved_quote_id)))
            .join(SavedQuote, SavedQuote.id == Order.saved_quote_id)
            .where(*quote_conditions, Order.status != "CANCELLED")
        )
        or 0
    )
    delivered = int(
        session.scalar(
            select(func.count(distinct(Order.saved_quote_id)))
            .join(SavedQuote, SavedQuote.id == Order.saved_quote_id)
            .where(*quote_conditions, Order.status == "DELIVERED")
        )
        or 0
    )
    return {
        "saved_quotes": quotes,
        "ordered_quotes": min(ordered, quotes),
        "delivered_quotes": min(delivered, ordered, quotes),
        "quote_to_order_conversion_pct": _percent(min(ordered, quotes), quotes),
        "order_to_delivered_conversion_pct": _percent(min(delivered, ordered), ordered),
        "quote_to_delivered_conversion_pct": _percent(min(delivered, quotes), quotes),
    }


def _delivery_metrics(session: Session, filters: list[Any]) -> dict[str, Any]:
    if session.bind and session.bind.dialect.name == "sqlite":
        delivery_days = func.julianday(Order.delivered_at) - func.julianday(Order.created_at)
    else:
        delivery_days = func.extract("epoch", Order.delivered_at - Order.created_at) / 86400
    row = session.execute(
        select(
            func.avg(
                case(
                    (
                        and_(
                            Order.status == "DELIVERED",
                            Order.delivered_at.is_not(None),
                        ),
                        delivery_days,
                    )
                )
            ),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Order.status == "DELIVERED",
                                Order.delivered_at.is_not(None),
                            ),
                            Order.id,
                        )
                    )
                )
            ),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Order.status == "DELIVERED",
                                Order.delivered_at.is_not(None),
                                Order.promised_delivery_at.is_not(None),
                                Order.delivered_at > Order.promised_delivery_at,
                            ),
                            Order.id,
                        )
                    )
                )
            ),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Order.status.in_(ACTIVE_STATUSES),
                                Order.promised_delivery_at.is_not(None),
                                Order.promised_delivery_at < func.now(),
                            ),
                            Order.id,
                        )
                    )
                )
            ),
        ).where(*filters)
    ).one()
    average = round(float(row[0]), 2) if row[0] is not None else None
    return {
        "average_delivery_days": average,
        "delivered_with_timestamp": int(row[1] or 0),
        "delivered_late": int(row[2] or 0),
        "active_overdue": int(row[3] or 0),
        "delayed_shipments": int(row[2] or 0) + int(row[3] or 0),
    }


def _supplier_statement(filters: list[Any]):
    return (
        select(
            Seller.id.label("supplier_id"),
            Seller.name.label("supplier_name"),
            Seller.rating.label("catalog_rating"),
            func.count(distinct(Order.id)).label("orders"),
            func.count(
                distinct(case((Order.status == "DELIVERED", Order.id)))
            ).label("delivered"),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Order.status == "DELIVERED",
                                Order.quality_defect_reported.is_(True),
                            ),
                            Order.id,
                        )
                    )
                )
            ).label("defects"),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Order.status == "DELIVERED",
                                Order.promised_delivery_at.is_not(None),
                                Order.delivered_at.is_not(None),
                            ),
                            Order.id,
                        )
                    )
                )
            ).label("sla_eligible"),
            func.count(
                distinct(
                    case(
                        (
                            and_(
                                Order.status == "DELIVERED",
                                Order.promised_delivery_at.is_not(None),
                                Order.delivered_at.is_not(None),
                                Order.delivered_at <= Order.promised_delivery_at,
                            ),
                            Order.id,
                        )
                    )
                )
            ).label("on_time"),
        )
        .select_from(Seller)
        .join(SellerOffer, SellerOffer.seller_id == Seller.id)
        .join(OrderItem, OrderItem.offer_id == SellerOffer.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(*filters)
        .group_by(Seller.id, Seller.name, Seller.rating)
    )


def _supplier_json(row: Any) -> dict[str, Any]:
    delivered = int(row.delivered or 0)
    sla_eligible = int(row.sla_eligible or 0)
    defect_rate = _percent(row.defects, delivered)
    sla = _percent(row.on_time, sla_eligible)
    quality = None if defect_rate is None else round(100 - defect_rate, 2)
    available = [value for value in (sla, quality) if value is not None]
    reliability = round(sum(available) / len(available), 2) if available else None
    return {
        "supplier_id": int(row.supplier_id),
        "supplier_name": row.supplier_name,
        "catalog_rating": float(row.catalog_rating or 0),
        "orders": int(row.orders or 0),
        "delivered_orders": delivered,
        "defect_orders": int(row.defects or 0),
        "defect_rate_pct": defect_rate,
        "sla_eligible_orders": sla_eligible,
        "on_time_orders": int(row.on_time or 0),
        "sla_pct": sla,
        "reliability_pct": reliability,
    }


def _profitability_statement(
    filters: list[Any],
    dimension: Literal["country", "category", "product"],
):
    realized_filters = [
        *filters,
        Order.status == "DELIVERED",
        Order.actual_cost_bdt.is_not(None),
    ]
    if dimension == "country":
        return (
            select(
                Order.country_code.label("dimension_key"),
                Order.country_code.label("dimension_name"),
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total_bdt), 0).label("revenue"),
                func.coalesce(func.sum(Order.actual_cost_bdt), 0).label("cost"),
                func.coalesce(
                    func.sum(Order.total_bdt - Order.actual_cost_bdt), 0
                ).label("margin"),
            )
            .where(*realized_filters)
            .group_by(Order.country_code)
        )

    order_units = (
        select(OrderItem.order_id, func.sum(OrderItem.qty).label("order_units"))
        .group_by(OrderItem.order_id)
        .subquery()
    )
    share = OrderItem.qty / func.nullif(order_units.c.order_units, 0)
    if dimension == "category":
        key = Category.id
        name = Category.name
    else:
        key = Product.id
        name = Product.name
    return (
        select(
            key.label("dimension_key"),
            name.label("dimension_name"),
            func.count(distinct(Order.id)).label("orders"),
            func.coalesce(func.sum(Order.total_bdt * share), 0).label("revenue"),
            func.coalesce(func.sum(Order.actual_cost_bdt * share), 0).label("cost"),
            func.coalesce(
                func.sum((Order.total_bdt - Order.actual_cost_bdt) * share), 0
            ).label("margin"),
        )
        .select_from(Order)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(order_units, order_units.c.order_id == Order.id)
        .join(ProductVariant, ProductVariant.id == OrderItem.variant_id)
        .join(Product, Product.id == ProductVariant.product_id)
        .join(Category, Category.id == Product.category_id)
        .where(*realized_filters)
        .group_by(key, name)
    )


def _profit_json(row: Any) -> dict[str, Any]:
    revenue = _decimal(row.revenue)
    margin = _decimal(row.margin)
    return {
        "key": row.dimension_key,
        "name": row.dimension_name,
        "orders": int(row.orders or 0),
        "revenue_bdt": _money(revenue),
        "actual_cost_bdt": _money(row.cost),
        "margin_bdt": _money(margin),
        "margin_pct": _percent(margin, revenue),
    }


def _date_context(
    session: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    days: int | None,
    timezone_name: str,
    status: str | None,
    country: str | None,
    mode: str | None,
) -> dict[str, Any]:
    start, end, start_at, end_at, zone = _period(
        date_from, date_to, days, timezone_name, session
    )
    return {
        "start": start,
        "end": end,
        "start_at": start_at,
        "end_at": end_at,
        "zone": zone,
        "filters": _filters(
            start_at, end_at, status=status, country=country, mode=mode
        ),
    }


def _last_updated(session: Session) -> datetime | None:
    order_updated = session.scalar(select(func.max(Order.updated_at)))
    adjustment_updated = session.scalar(select(func.max(PaymentAdjustment.created_at)))
    values = [value for value in (order_updated, adjustment_updated) if value is not None]
    return max(values) if values else None


@router.get("/api/admin/analytics/overview/")
def analytics_overview(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    days: int | None = Query(default=30, ge=1, le=366),
    timezone_name: str = Query(default="Asia/Dhaka", alias="timezone", max_length=80),
    status: str | None = Query(default=None, max_length=20),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    mode: str | None = Query(default=None),
    compare: bool = Query(default=True),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    context = _date_context(
        session,
        date_from=date_from,
        date_to=date_to,
        days=days,
        timezone_name=timezone_name,
        status=status,
        country=country,
        mode=mode,
    )
    cache_key = (
        "overview",
        str(session.bind.url) if session.bind else "unbound",
        context["start"].isoformat(),
        context["end"].isoformat(),
        timezone_name,
        status,
        country,
        mode,
        compare,
    )
    cached = admin_analytics_cache.get(cache_key)
    if cached is not None:
        cached["cache"] = {"hit": True, "ttl_seconds": admin_analytics_cache.ttl_seconds}
        return cached

    financials = _financial_metrics(
        session,
        context["filters"],
        context["start_at"],
        context["end_at"],
        status=status,
        country=country,
        mode=mode,
    )
    funnel = _funnel(
        session,
        context["start_at"],
        context["end_at"],
        country=country,
        mode=mode,
    )
    delivery = _delivery_metrics(session, context["filters"])
    duration = (context["end"] - context["start"]).days + 1
    previous_end = context["start"] - timedelta(days=1)
    previous_start = previous_end - timedelta(days=duration - 1)
    previous_financials: dict[str, Any] = {}
    if compare:
        previous_context = _date_context(
            session,
            date_from=previous_start,
            date_to=previous_end,
            days=None,
            timezone_name=timezone_name,
            status=status,
            country=country,
            mode=mode,
        )
        previous_financials = _financial_metrics(
            session,
            previous_context["filters"],
            previous_context["start_at"],
            previous_context["end_at"],
            status=status,
            country=country,
            mode=mode,
        )

    supplier_rows = session.execute(
        _supplier_statement(context["filters"])
        .order_by(func.count(distinct(Order.id)).desc(), Seller.name.asc())
        .limit(10)
    ).all()
    country_profit_statement = _profitability_statement(context["filters"], "country")
    country_profit = session.execute(
        country_profit_statement
        .order_by(country_profit_statement.selected_columns.margin.desc())
        .limit(10)
    ).all()
    realized_count = int(financials["realized_margin_orders"])
    last_updated = _last_updated(session)
    response = {
        "range": {
            "date_from": context["start"].isoformat(),
            "date_to": context["end"].isoformat(),
            "timezone": timezone_name,
            "comparison_date_from": previous_start.isoformat() if compare else None,
            "comparison_date_to": previous_end.isoformat() if compare else None,
            "filters": {"status": status, "country": country, "mode": mode},
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_last_updated_at": last_updated.isoformat() if last_updated else None,
        "metric_version": METRIC_VERSION,
        "metric_definitions": METRIC_DEFINITIONS,
        "cards": {
            "total_orders": int(financials["total_orders"]),
            "gross_order_value_bdt": _money(financials["gross_order_value_bdt"]),
            "verified_cash_bdt": _money(financials["verified_cash_bdt"]),
            "outstanding_bdt": _money(financials["outstanding_bdt"]),
            "refunds_bdt": _money(financials["refunds_bdt"]),
            "shipping_value_bdt": _money(financials["shipping_value_bdt"]),
            "realized_margin_bdt": (
                _money(financials["realized_margin_bdt"]) if realized_count else None
            ),
            "realized_margin_orders": realized_count,
        },
        "comparison": (
            {
                key: _comparison(
                    financials[key],
                    previous_financials[key],
                    money=(key != "total_orders"),
                )
                for key in (
                    "total_orders",
                    "gross_order_value_bdt",
                    "verified_cash_bdt",
                    "refunds_bdt",
                    "shipping_value_bdt",
                    "realized_margin_bdt",
                )
            }
            if compare
            else None
        ),
        "funnel": funnel,
        "delivery": delivery,
        "daily_financials": _daily_financials(
            session,
            start=context["start"],
            end=context["end"],
            start_at=context["start_at"],
            end_at=context["end_at"],
            timezone_name=timezone_name,
            zone=context["zone"],
            status=status,
            country=country,
            mode=mode,
        ),
        "supplier_performance": [_supplier_json(row) for row in supplier_rows],
        "profitability_by_country": [_profit_json(row) for row in country_profit],
        "coverage": {
            "orders_with_actual_cost": realized_count,
            "delivered_with_timestamp": delivery["delivered_with_timestamp"],
            "supplier_rows_with_outcomes": sum(
                1 for row in supplier_rows if int(row.delivered or 0) > 0
            ),
        },
        "cache": {"hit": False, "ttl_seconds": admin_analytics_cache.ttl_seconds},
    }
    admin_analytics_cache.set(cache_key, response)
    return response


@router.get("/api/admin/analytics/suppliers/")
def supplier_analytics(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    days: int | None = Query(default=30, ge=1, le=366),
    timezone_name: str = Query(default="Asia/Dhaka", alias="timezone", max_length=80),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    mode: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    context = _date_context(
        session,
        date_from=date_from,
        date_to=date_to,
        days=days,
        timezone_name=timezone_name,
        status=None,
        country=country,
        mode=mode,
    )
    statement = _supplier_statement(context["filters"])
    total = int(
        session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    )
    rows = session.execute(
        statement.order_by(func.count(distinct(Order.id)).desc(), Seller.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "items": [_supplier_json(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)),
        "metric_definitions": {
            key: METRIC_DEFINITIONS[key]
            for key in (
                "supplier_sla_pct",
                "supplier_defect_rate_pct",
                "supplier_reliability_pct",
            )
        },
    }


@router.get("/api/admin/analytics/profitability/")
def profitability_analytics(
    dimension: Literal["country", "category", "product"] = Query(default="country"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    days: int | None = Query(default=30, ge=1, le=366),
    timezone_name: str = Query(default="Asia/Dhaka", alias="timezone", max_length=80),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    mode: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    context = _date_context(
        session,
        date_from=date_from,
        date_to=date_to,
        days=days,
        timezone_name=timezone_name,
        status=None,
        country=country,
        mode=mode,
    )
    statement = _profitability_statement(context["filters"], dimension)
    total = int(
        session.scalar(select(func.count()).select_from(statement.subquery())) or 0
    )
    rows = session.execute(
        statement.order_by(statement.selected_columns.margin.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {
        "dimension": dimension,
        "items": [_profit_json(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)),
        "metric_definition": METRIC_DEFINITIONS["realized_margin_bdt"],
        "empty_state": (
            None
            if total
            else "No delivered orders with actual-cost settlement exist in this window."
        ),
    }


@router.get("/api/admin/analytics/delays/")
def delayed_shipments(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    days: int | None = Query(default=30, ge=1, le=366),
    timezone_name: str = Query(default="Asia/Dhaka", alias="timezone", max_length=80),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(user)
    context = _date_context(
        session,
        date_from=date_from,
        date_to=date_to,
        days=days,
        timezone_name=timezone_name,
        status=None,
        country=None,
        mode=None,
    )
    late_condition = or_(
        and_(
            Order.status == "DELIVERED",
            Order.delivered_at.is_not(None),
            Order.promised_delivery_at.is_not(None),
            Order.delivered_at > Order.promised_delivery_at,
        ),
        and_(
            Order.status.in_(ACTIVE_STATUSES),
            Order.promised_delivery_at.is_not(None),
            Order.promised_delivery_at < func.now(),
        ),
    )
    statement = (
        select(Order)
        .where(*context["filters"], late_condition)
        .order_by(Order.promised_delivery_at.asc(), Order.id.asc())
    )
    total = int(
        session.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
        or 0
    )
    orders = session.scalars(
        statement.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return {
        "items": [
            {
                "order_id": order.id,
                "status": order.status,
                "country": order.country_code,
                "promised_delivery_at": order.promised_delivery_at,
                "delivered_at": order.delivered_at,
                "delay_type": "delivered_late" if order.status == "DELIVERED" else "active_overdue",
            }
            for order in orders
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, ceil(total / page_size)),
    }
