from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..customer_schemas import AddressCreateIn, AddressUpdateIn, CustomerProfileUpdateIn
from ..models import (
    AccountUser,
    CustomerAddress,
    CustomerInvoice,
    CustomerProfile,
    Order,
)
from .financial_operations import financial_snapshot
from .orders import get_order_or_404, order_loader_options


CurrentUser = dict[str, Any]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require_customer(current_user: CurrentUser) -> None:
    if current_user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Customer account access required")


def get_or_create_customer_profile(
    session: Session,
    current_user: CurrentUser,
) -> CustomerProfile:
    require_customer(current_user)
    profile = session.scalar(
        select(CustomerProfile).where(CustomerProfile.user_id == current_user["sub"])
    )
    if profile is None:
        profile = CustomerProfile(user_id=int(current_user["sub"]))
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def serialize_customer_profile(
    session: Session,
    profile: CustomerProfile,
) -> dict[str, Any]:
    user = session.get(AccountUser, profile.user_id)
    return {
        "user_id": profile.user_id,
        "username": user.username if user else None,
        "email": user.email if user else None,
        "phone": user.phone if user else None,
        "full_name": profile.full_name,
        "company": {
            "name": profile.company_name,
            "registration_number": profile.company_registration_number,
            "tax_identifier": profile.tax_identifier,
        },
        "preferences": {
            "language": profile.preferred_language,
            "currency": profile.preferred_currency,
            "timezone": profile.timezone,
        },
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def update_customer_profile(
    session: Session,
    payload: CustomerProfileUpdateIn,
    current_user: CurrentUser,
) -> CustomerProfile:
    profile = get_or_create_customer_profile(session, current_user)
    values = payload.model_dump(exclude_unset=True)
    if "preferred_currency" in values and values["preferred_currency"]:
        values["preferred_currency"] = values["preferred_currency"].upper()
    for field, value in values.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(profile, field, value)
    profile.updated_at = utc_now()
    session.commit()
    session.refresh(profile)
    return profile


def serialize_address(address: CustomerAddress) -> dict[str, Any]:
    return {
        "id": address.id,
        "label": address.label,
        "recipient_name": address.recipient_name,
        "company_name": address.company_name,
        "line1": address.line1,
        "line2": address.line2,
        "city": address.city,
        "region": address.region,
        "postal_code": address.postal_code,
        "country_code": address.country_code,
        "phone": address.phone,
        "is_default_shipping": address.is_default_shipping,
        "is_default_billing": address.is_default_billing,
        "created_at": address.created_at,
        "updated_at": address.updated_at,
    }


def list_customer_addresses(
    session: Session,
    current_user: CurrentUser,
) -> list[CustomerAddress]:
    require_customer(current_user)
    return session.scalars(
        select(CustomerAddress)
        .where(
            CustomerAddress.user_id == current_user["sub"],
            CustomerAddress.archived_at.is_(None),
        )
        .order_by(
            CustomerAddress.is_default_shipping.desc(),
            CustomerAddress.is_default_billing.desc(),
            CustomerAddress.id.desc(),
        )
    ).all()


def get_customer_address_or_404(
    session: Session,
    address_id: int,
    current_user: CurrentUser,
) -> CustomerAddress:
    require_customer(current_user)
    address = session.scalar(
        select(CustomerAddress).where(
            CustomerAddress.id == address_id,
            CustomerAddress.archived_at.is_(None),
        )
    )
    if address is None:
        raise HTTPException(status_code=404, detail="Address not found")
    if address.user_id != current_user["sub"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    return address


def _clear_other_defaults(
    session: Session,
    *,
    user_id: int,
    address_id: int | None,
    shipping: bool,
    billing: bool,
) -> None:
    if not shipping and not billing:
        return
    addresses = session.scalars(
        select(CustomerAddress).where(
            CustomerAddress.user_id == user_id,
            CustomerAddress.archived_at.is_(None),
        )
    ).all()
    for existing in addresses:
        if address_id is not None and existing.id == address_id:
            continue
        if shipping:
            existing.is_default_shipping = False
        if billing:
            existing.is_default_billing = False


def _lock_customer_account(session: Session, user_id: int) -> None:
    # Serializes default-address changes for one customer on PostgreSQL. SQLite
    # serializes writers at the database level.
    session.scalar(
        select(AccountUser.id)
        .where(AccountUser.id == user_id)
        .with_for_update()
    )


def create_customer_address(
    session: Session,
    payload: AddressCreateIn,
    current_user: CurrentUser,
) -> CustomerAddress:
    require_customer(current_user)
    user_id = int(current_user["sub"])
    _lock_customer_account(session, user_id)
    address_count = int(
        session.scalar(
            select(func.count(CustomerAddress.id)).where(
                CustomerAddress.user_id == user_id,
                CustomerAddress.archived_at.is_(None),
            )
        )
        or 0
    )
    values = payload.model_dump()
    if address_count == 0:
        values["is_default_shipping"] = True
        values["is_default_billing"] = True
    _clear_other_defaults(
        session,
        user_id=user_id,
        address_id=None,
        shipping=bool(values["is_default_shipping"]),
        billing=bool(values["is_default_billing"]),
    )
    address = CustomerAddress(user_id=user_id, **values)
    session.add(address)
    session.commit()
    session.refresh(address)
    return address


def update_customer_address(
    session: Session,
    address_id: int,
    payload: AddressUpdateIn,
    current_user: CurrentUser,
) -> CustomerAddress:
    address = get_customer_address_or_404(session, address_id, current_user)
    _lock_customer_account(session, address.user_id)
    values = payload.model_dump(exclude_unset=True)
    for flag in ("is_default_shipping", "is_default_billing"):
        if values.get(flag) is not False or not getattr(address, flag):
            continue
        replacement = session.scalar(
            select(CustomerAddress)
            .where(
                CustomerAddress.user_id == address.user_id,
                CustomerAddress.id != address.id,
                CustomerAddress.archived_at.is_(None),
            )
            .order_by(CustomerAddress.id.desc())
        )
        if replacement is None:
            label = "shipping" if flag == "is_default_shipping" else "billing"
            raise HTTPException(
                status_code=409,
                detail=f"The only active address must remain the default {label} address",
            )
        setattr(replacement, flag, True)
    _clear_other_defaults(
        session,
        user_id=address.user_id,
        address_id=address.id,
        shipping=values.get("is_default_shipping") is True,
        billing=values.get("is_default_billing") is True,
    )
    for field, value in values.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(address, field, value)
    address.updated_at = utc_now()
    session.commit()
    session.refresh(address)
    return address


def archive_customer_address(
    session: Session,
    address_id: int,
    current_user: CurrentUser,
) -> None:
    address = get_customer_address_or_404(session, address_id, current_user)
    _lock_customer_account(session, address.user_id)
    was_shipping = address.is_default_shipping
    was_billing = address.is_default_billing
    address.is_default_shipping = False
    address.is_default_billing = False
    address.archived_at = utc_now()
    address.updated_at = address.archived_at
    replacement = session.scalar(
        select(CustomerAddress)
        .where(
            CustomerAddress.user_id == address.user_id,
            CustomerAddress.id != address.id,
            CustomerAddress.archived_at.is_(None),
        )
        .order_by(CustomerAddress.id.desc())
    )
    if replacement is not None:
        if was_shipping:
            replacement.is_default_shipping = True
        if was_billing:
            replacement.is_default_billing = True
    session.commit()


def _money(value: Decimal | int | str | None) -> str:
    return format(Decimal(str(value or 0)), ".2f")


def _invoice_address(address: CustomerAddress | None) -> dict[str, Any] | None:
    if address is None:
        return None
    return {
        "label": address.label,
        "recipient_name": address.recipient_name,
        "company_name": address.company_name,
        "line1": address.line1,
        "line2": address.line2,
        "city": address.city,
        "region": address.region,
        "postal_code": address.postal_code,
        "country_code": address.country_code,
        "phone": address.phone,
    }


def create_order_invoice_snapshot(
    session: Session,
    order: Order,
) -> CustomerInvoice:
    existing = session.scalar(
        select(CustomerInvoice).where(CustomerInvoice.order_id == order.id)
    )
    if existing is not None:
        return existing
    user = session.get(AccountUser, order.user_id)
    profile = session.scalar(
        select(CustomerProfile).where(CustomerProfile.user_id == order.user_id)
    )
    shipping = session.scalar(
        select(CustomerAddress)
        .where(
            CustomerAddress.user_id == order.user_id,
            CustomerAddress.archived_at.is_(None),
            CustomerAddress.is_default_shipping.is_(True),
        )
        .order_by(CustomerAddress.id.desc())
    )
    billing = session.scalar(
        select(CustomerAddress)
        .where(
            CustomerAddress.user_id == order.user_id,
            CustomerAddress.archived_at.is_(None),
            CustomerAddress.is_default_billing.is_(True),
        )
        .order_by(CustomerAddress.id.desc())
    )
    snapshot = {
        "schema_version": 1,
        "captured_at": utc_now().isoformat(),
        "customer": {
            "user_id": order.user_id,
            "username": user.username if user else None,
            "email": user.email if user else None,
            "phone": user.phone if user else None,
            "full_name": profile.full_name if profile else None,
            "company_name": profile.company_name if profile else None,
            "company_registration_number": (
                profile.company_registration_number if profile else None
            ),
            "tax_identifier": profile.tax_identifier if profile else None,
        },
        "shipping_address": _invoice_address(shipping),
        "billing_address": _invoice_address(billing),
        "order": {
            "id": order.id,
            "country_code": order.country_code,
            "mode": order.mode,
            "delivery_type": order.delivery_type,
            "total_bdt": _money(order.total_bdt),
            "shipping_bdt": _money(order.shipping_bdt),
            "advance_bdt": _money(order.advance_bdt),
            "remaining_bdt": _money(order.remaining_bdt),
            "items": [
                {
                    "product_name": item.product_name,
                    "variant_name": item.variant_name,
                    "qty": item.qty,
                    "offer_id": item.offer_id,
                }
                for item in order.items
            ],
        },
    }
    invoice = CustomerInvoice(
        order_id=order.id,
        user_id=order.user_id,
        invoice_number=f"INV-{order.id:08d}",
        currency="BDT",
        snapshot=snapshot,
        issued_at=order.created_at or utc_now(),
    )
    session.add(invoice)
    session.flush()
    return invoice


def serialize_invoice(
    session: Session,
    order: Order,
    invoice: CustomerInvoice,
) -> dict[str, Any]:
    payment = order.manual_payment
    financials = financial_snapshot(session, order)
    payment_status = payment.decision if payment else "UNPAID"
    snapshot = invoice.snapshot or {}
    order_snapshot = snapshot.get("order") or {}
    return {
        "id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "order_id": order.id,
        "issued_at": invoice.issued_at,
        "currency": invoice.currency,
        "status": "VOID" if order.status == "CANCELLED" else "ISSUED",
        "payment_status": payment_status,
        "customer_id": order.user_id,
        "customer": snapshot.get("customer"),
        "shipping_address": snapshot.get("shipping_address"),
        "billing_address": snapshot.get("billing_address"),
        "country_code": order_snapshot.get("country_code", order.country_code),
        "items": order_snapshot.get("items", []),
        "total_bdt": order_snapshot.get("total_bdt", _money(order.total_bdt)),
        "shipping_bdt": order_snapshot.get(
            "shipping_bdt", _money(order.shipping_bdt)
        ),
        "advance_bdt": order_snapshot.get("advance_bdt", _money(order.advance_bdt)),
        "remaining_bdt": order_snapshot.get(
            "remaining_bdt", _money(order.remaining_bdt)
        ),
        **financials,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


def list_customer_invoices(
    session: Session,
    current_user: CurrentUser,
    *,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    require_customer(current_user)
    filters = (Order.user_id == current_user["sub"],)
    total = int(session.scalar(select(func.count(Order.id)).where(*filters)) or 0)
    orders = session.scalars(
        select(Order)
        .options(*order_loader_options())
        .where(*filters)
        .order_by(Order.id.desc())
        .offset(offset)
        .limit(limit)
    ).unique().all()
    invoices = [create_order_invoice_snapshot(session, order) for order in orders]
    session.commit()
    return {
        "items": [
            serialize_invoice(session, order, invoice)
            for order, invoice in zip(orders, invoices, strict=True)
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_customer_invoice(
    session: Session,
    order_id: int,
    current_user: CurrentUser,
) -> dict[str, Any]:
    require_customer(current_user)
    order = get_order_or_404(session, order_id, current_user)
    invoice = create_order_invoice_snapshot(session, order)
    session.commit()
    session.refresh(invoice)
    return serialize_invoice(session, order, invoice)


def simple_pdf(lines: list[str]) -> bytes:
    safe_lines = []
    for line in lines:
        latin = line.encode("latin-1", errors="replace").decode("latin-1")
        safe_lines.append(
            latin.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        )
    stream = (
        "BT /F1 11 Tf 50 790 Td "
        + " 0 -20 Td ".join(f"({line}) Tj" for line in safe_lines)
        + " ET"
    )
    stream_bytes = stream.encode("latin-1")
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        (
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj"
        ),
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        (
            f"5 0 obj << /Length {len(stream_bytes)} >> stream\n"
            f"{stream}\nendstream endobj"
        ),
    ]
    result = b"%PDF-1.4\n"
    offsets = [0]
    for item in objects:
        offsets.append(len(result))
        result += (item + "\n").encode("latin-1")
    xref = len(result)
    result += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")
    for offset in offsets[1:]:
        result += f"{offset:010d} 00000 n \n".encode("ascii")
    result += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF"
    ).encode("ascii")
    return result


def build_invoice_pdf(invoice: dict[str, Any]) -> bytes:
    customer = invoice.get("customer") or {}
    address = invoice.get("billing_address") or invoice.get("shipping_address") or {}
    lines = [
        "SourceAI Invoice",
        f"Invoice: {invoice['invoice_number']}",
        f"Order: #{invoice['order_id']}",
        f"Issued: {invoice['issued_at']}",
        f"Status: {invoice['status']}",
        f"Customer: {customer.get('full_name') or customer.get('username') or ''}",
        f"Company: {customer.get('company_name') or ''}",
        (
            "Address: "
            f"{address.get('line1') or ''}, {address.get('city') or ''}, "
            f"{address.get('country_code') or ''}"
        ),
    ]
    lines.extend(
        f"{item['product_name']} - {item['variant_name']} x {item['qty']}"
        for item in invoice["items"]
    )
    lines.extend(
        (
            f"Total: BDT {invoice['total_bdt']}",
            f"Verified cash: BDT {invoice['net_verified_cash_bdt']}",
            f"Outstanding: BDT {invoice['outstanding_bdt']}",
            f"Payment status: {invoice['payment_status']}",
        )
    )
    return simple_pdf(lines)


def build_invoice_html(invoice: dict[str, Any]) -> bytes:
    """UTF-8 invoice download for Bangla/English and browser PDF printing."""

    customer = invoice.get("customer") or {}
    address = invoice.get("billing_address") or invoice.get("shipping_address") or {}
    item_rows = "".join(
        (
            "<tr>"
            f"<td>{escape(str(item['product_name']))}</td>"
            f"<td>{escape(str(item['variant_name']))}</td>"
            f"<td>{int(item['qty'])}</td>"
            "</tr>"
        )
        for item in invoice["items"]
    )
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(invoice["invoice_number"])}</title>
  <style>
    body {{ font-family: system-ui, "Noto Sans Bengali", sans-serif; margin: 2rem; color: #10213d; }}
    header {{ display: flex; justify-content: space-between; gap: 2rem; }}
    table {{ width: 100%; border-collapse: collapse; margin: 2rem 0; }}
    th, td {{ border-bottom: 1px solid #d8e0ec; padding: .7rem; text-align: left; }}
    .money {{ font-variant-numeric: tabular-nums; }}
    @media print {{ body {{ margin: 0; }} }}
  </style>
</head>
<body>
  <header>
    <div><h1>SourceAI Invoice</h1><p>{escape(invoice["invoice_number"])}</p></div>
    <div><p>Order #{invoice["order_id"]}</p><p>{escape(str(invoice["issued_at"]))}</p></div>
  </header>
  <section>
    <h2>{escape(str(customer.get("full_name") or customer.get("username") or ""))}</h2>
    <p>{escape(str(customer.get("company_name") or ""))}</p>
    <p>{escape(str(address.get("line1") or ""))}, {escape(str(address.get("city") or ""))},
       {escape(str(address.get("country_code") or ""))}</p>
  </section>
  <table>
    <thead><tr><th>Product</th><th>Variant</th><th>Quantity</th></tr></thead>
    <tbody>{item_rows}</tbody>
  </table>
  <p class="money">Total: BDT {escape(invoice["total_bdt"])}</p>
  <p class="money">Verified cash: BDT {escape(invoice["net_verified_cash_bdt"])}</p>
  <p class="money">Outstanding: BDT {escape(invoice["outstanding_bdt"])}</p>
</body>
</html>"""
    return document.encode("utf-8")
