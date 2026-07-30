from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...auth import get_current_user
from ...customer_schemas import (
    AddressCreateIn,
    AddressUpdateIn,
    AdminDisputeDecisionIn,
    AdminSupportStatusIn,
    CustomerProfileUpdateIn,
    DisputeCancelIn,
    DisputeCreateIn,
    NotificationPreferenceUpdateIn,
    PaymentRetryIn,
    SupportMessageCreateIn,
    SupportTicketCreateIn,
)
from ...db import get_session
from ...models import CustomerNotification, NotificationOutbox
from ...services.customer_account import (
    archive_customer_address,
    build_invoice_html,
    build_invoice_pdf,
    create_customer_address,
    get_customer_address_or_404,
    get_customer_invoice,
    get_or_create_customer_profile,
    list_customer_addresses,
    list_customer_invoices,
    require_customer,
    serialize_address,
    serialize_customer_profile,
    update_customer_address,
    update_customer_profile,
)
from ...services.customer_payments import (
    list_payment_attempts,
    retry_manual_payment,
    serialize_payment_attempt,
)
from ...services.customer_support import (
    add_admin_support_message,
    add_customer_support_message,
    cancel_customer_dispute,
    create_customer_dispute,
    create_support_ticket,
    get_dispute_or_404,
    get_support_ticket_or_404,
    list_admin_disputes,
    list_admin_support_tickets,
    list_customer_disputes,
    list_customer_support_tickets,
    serialize_dispute,
    serialize_support_ticket,
    update_admin_dispute,
    update_admin_support_status,
)
from ...services.notifications import (
    dispatch_outbox_batch,
    get_or_create_notification_preferences,
    requeue_failed_outbox,
    serialize_customer_notification,
    serialize_notification_preferences,
    serialize_outbox,
    update_notification_preferences,
    utc_now,
)
from ...services.orders import record_admin_audit, require_operator


router = APIRouter()


def require_admin(current_user: dict[str, Any]) -> None:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")


def get_current_customer(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_customer(current_user)
    return current_user


@router.get("/api/account/profile/")
def customer_profile(
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    profile = get_or_create_customer_profile(session, current_user)
    return serialize_customer_profile(session, profile)


@router.patch("/api/account/profile/")
def update_profile(
    payload: CustomerProfileUpdateIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    profile = update_customer_profile(session, payload, current_user)
    return serialize_customer_profile(session, profile)


@router.get("/api/account/addresses/")
def addresses(
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> list[dict[str, Any]]:
    return [
        serialize_address(item)
        for item in list_customer_addresses(session, current_user)
    ]


@router.post("/api/account/addresses/", status_code=status.HTTP_201_CREATED)
def create_address(
    payload: AddressCreateIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return serialize_address(create_customer_address(session, payload, current_user))


@router.get("/api/account/addresses/{address_id}/")
def address_detail(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return serialize_address(
        get_customer_address_or_404(session, address_id, current_user)
    )


@router.patch("/api/account/addresses/{address_id}/")
def update_address(
    address_id: int,
    payload: AddressUpdateIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return serialize_address(
        update_customer_address(session, address_id, payload, current_user)
    )


@router.delete(
    "/api/account/addresses/{address_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_address(
    address_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> Response:
    archive_customer_address(session, address_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/account/invoices/")
def invoices(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return list_customer_invoices(
        session,
        current_user,
        limit=limit,
        offset=offset,
    )


@router.get("/api/account/invoices/{order_id}/")
def invoice_detail(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return get_customer_invoice(session, order_id, current_user)


@router.get("/api/account/invoices/{order_id}/pdf/")
def invoice_pdf(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> Response:
    invoice = get_customer_invoice(session, order_id, current_user)
    return Response(
        build_invoice_pdf(invoice),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f"attachment; filename=sourceai-{invoice['invoice_number'].lower()}.pdf"
            )
        },
    )


@router.get("/api/account/invoices/{order_id}/download/")
def invoice_unicode_download(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> Response:
    invoice = get_customer_invoice(session, order_id, current_user)
    return Response(
        build_invoice_html(invoice),
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename=sourceai-{invoice['invoice_number'].lower()}.html"
            )
        },
    )


@router.get("/api/account/notification-preferences/")
def notification_preferences(
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    preference = get_or_create_notification_preferences(
        session,
        int(current_user["sub"]),
    )
    session.commit()
    return serialize_notification_preferences(preference)


@router.patch("/api/account/notification-preferences/")
def update_preferences(
    payload: NotificationPreferenceUpdateIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    preference = update_notification_preferences(
        session,
        int(current_user["sub"]),
        payload.model_dump(exclude_unset=True),
    )
    return serialize_notification_preferences(preference)


@router.get("/api/account/notifications/")
def notifications(
    unread_only: bool = False,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    filters = [CustomerNotification.user_id == current_user["sub"]]
    if unread_only:
        filters.append(CustomerNotification.read_at.is_(None))
    total = int(
        session.scalar(select(func.count(CustomerNotification.id)).where(*filters))
        or 0
    )
    items = session.scalars(
        select(CustomerNotification)
        .where(*filters)
        .order_by(CustomerNotification.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            serialize_customer_notification(session, item) for item in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/api/account/notifications/read-all/")
def mark_all_notifications_read(
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, int]:
    unread = session.scalars(
        select(CustomerNotification).where(
            CustomerNotification.user_id == current_user["sub"],
            CustomerNotification.read_at.is_(None),
        )
    ).all()
    marked_at = utc_now()
    for notification in unread:
        notification.read_at = marked_at
    session.commit()
    return {"updated": len(unread)}


@router.post("/api/account/notifications/{notification_id}/read/")
def mark_notification_read(
    notification_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    notification = session.scalar(
        select(CustomerNotification).where(
            CustomerNotification.id == notification_id,
            CustomerNotification.user_id == current_user["sub"],
        )
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = utc_now()
        session.commit()
        session.refresh(notification)
    return serialize_customer_notification(session, notification)


@router.get("/api/account/support-tickets/")
def support_tickets(
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return list_customer_support_tickets(
        session,
        current_user,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.post("/api/account/support-tickets/", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: SupportTicketCreateIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    ticket = create_support_ticket(session, payload, current_user)
    return serialize_support_ticket(ticket, include_messages=True)


@router.get("/api/account/support-tickets/{ticket_id}/")
def support_ticket_detail(
    ticket_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    ticket = get_support_ticket_or_404(session, ticket_id, current_user)
    return serialize_support_ticket(ticket, include_messages=True)


@router.post("/api/account/support-tickets/{ticket_id}/messages/")
def add_ticket_message(
    ticket_id: int,
    payload: SupportMessageCreateIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    ticket = add_customer_support_message(
        session,
        ticket_id,
        payload,
        current_user,
    )
    return serialize_support_ticket(ticket, include_messages=True)


@router.get("/api/account/disputes/")
def disputes(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return list_customer_disputes(
        session,
        current_user,
        limit=limit,
        offset=offset,
    )


@router.post("/api/account/disputes/", status_code=status.HTTP_201_CREATED)
def create_dispute(
    payload: DisputeCreateIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return serialize_dispute(create_customer_dispute(session, payload, current_user))


@router.get("/api/account/disputes/{dispute_id}/")
def dispute_detail(
    dispute_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return serialize_dispute(get_dispute_or_404(session, dispute_id, current_user))


@router.post("/api/account/disputes/{dispute_id}/cancel/")
def cancel_dispute(
    dispute_id: int,
    payload: DisputeCancelIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    return serialize_dispute(
        cancel_customer_dispute(session, dispute_id, payload, current_user)
    )


@router.get("/api/account/orders/{order_id}/payment-attempts/")
def payment_attempts(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> list[dict[str, Any]]:
    return list_payment_attempts(session, order_id, current_user)


@router.post("/api/account/orders/{order_id}/payment-retry/")
def retry_payment(
    order_id: int,
    payload: PaymentRetryIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_customer),
) -> dict[str, Any]:
    order, attempt = retry_manual_payment(
        session,
        order_id,
        payload,
        current_user,
    )
    return {
        "order_id": order.id,
        "order_status": order.status,
        "payment_status": order.manual_payment.decision,
        "attempt": serialize_payment_attempt(attempt),
    }


@router.get("/api/admin/support-tickets/")
def admin_support_tickets(
    q: str | None = Query(default=None, max_length=200),
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return list_admin_support_tickets(
        session,
        current_user,
        q=q,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/api/admin/support-tickets/{ticket_id}/")
def admin_support_ticket_detail(
    ticket_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(current_user)
    return serialize_support_ticket(
        get_support_ticket_or_404(session, ticket_id, current_user),
        include_messages=True,
    )


@router.post("/api/admin/support-tickets/{ticket_id}/messages/")
def admin_add_support_message(
    ticket_id: int,
    payload: SupportMessageCreateIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    ticket = add_admin_support_message(
        session,
        ticket_id,
        payload,
        current_user,
    )
    return serialize_support_ticket(ticket, include_messages=True)


@router.patch("/api/admin/support-tickets/{ticket_id}/status/")
def admin_update_support_status(
    ticket_id: int,
    payload: AdminSupportStatusIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    ticket = update_admin_support_status(
        session,
        ticket_id,
        payload,
        current_user,
    )
    return serialize_support_ticket(ticket, include_messages=True)


@router.get("/api/admin/disputes/")
def admin_disputes(
    q: str | None = Query(default=None, max_length=100),
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return list_admin_disputes(
        session,
        current_user,
        q=q,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )


@router.get("/api/admin/disputes/{dispute_id}/")
def admin_dispute_detail(
    dispute_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(current_user)
    return serialize_dispute(get_dispute_or_404(session, dispute_id, current_user))


@router.patch("/api/admin/disputes/{dispute_id}/")
def admin_update_dispute(
    dispute_id: int,
    payload: AdminDisputeDecisionIn,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return serialize_dispute(
        update_admin_dispute(session, dispute_id, payload, current_user)
    )


@router.get("/api/admin/notifications/outbox/")
def admin_notification_outbox(
    status_filter: str | None = Query(default=None, alias="status", max_length=20),
    channel: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(current_user)
    filters = []
    if status_filter:
        filters.append(NotificationOutbox.status == status_filter.upper())
    if channel:
        filters.append(NotificationOutbox.channel == channel.lower())
    total = int(session.scalar(select(func.count(NotificationOutbox.id)).where(*filters)) or 0)
    items = session.scalars(
        select(NotificationOutbox)
        .where(*filters)
        .order_by(NotificationOutbox.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [serialize_outbox(item) for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/api/admin/notifications/outbox/{outbox_id}/")
def admin_notification_outbox_detail(
    outbox_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_operator(current_user)
    item = session.get(NotificationOutbox, outbox_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Outbox record not found")
    return serialize_outbox(item)


@router.post("/api/admin/notifications/outbox/dispatch/")
def admin_dispatch_outbox(
    limit: int = Query(default=1, ge=1, le=1),
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, int]:
    require_admin(current_user)
    result = dispatch_outbox_batch(session, limit=limit)
    record_admin_audit(
        session,
        current_user,
        action="notification_outbox.dispatched",
        entity_type="notification_outbox_batch",
        entity_id="batch",
        after=result,
        note="Notification outbox dispatch requested",
    )
    session.commit()
    return result


@router.post("/api/admin/notifications/outbox/{outbox_id}/requeue/")
def admin_requeue_outbox(
    outbox_id: int,
    session: Session = Depends(get_session),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    require_admin(current_user)
    try:
        item = requeue_failed_outbox(session, outbox_id=outbox_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record_admin_audit(
        session,
        current_user,
        action="notification_outbox.requeued",
        entity_type="notification_outbox",
        entity_id=item.id,
        after={"status": item.status},
        note="Failed notification requeued",
    )
    session.commit()
    return serialize_outbox(item)
