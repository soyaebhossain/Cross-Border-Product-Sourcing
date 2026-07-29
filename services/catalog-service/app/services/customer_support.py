from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..customer_schemas import (
    AdminDisputeDecisionIn,
    AdminSupportStatusIn,
    DisputeCancelIn,
    DisputeCreateIn,
    SupportMessageCreateIn,
    SupportTicketCreateIn,
)
from ..models import CustomerDispute, SupportMessage, SupportTicket
from ..security import request_id_context
from .customer_account import require_customer
from .notifications import queue_customer_notification
from .orders import get_order_or_404, record_admin_audit, require_operator


CurrentUser = dict[str, Any]
DISPUTE_TRANSITIONS = {
    "OPEN": {"UNDER_REVIEW", "RESOLVED", "REJECTED"},
    "UNDER_REVIEW": {"RESOLVED", "REJECTED"},
    "RESOLVED": set(),
    "REJECTED": set(),
    "CANCELLED": set(),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _public_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16].upper()}"


def serialize_support_ticket(
    ticket: SupportTicket,
    *,
    include_messages: bool,
) -> dict[str, Any]:
    result = {
        "id": ticket.id,
        "public_id": ticket.public_id,
        "user_id": ticket.user_id,
        "order_id": ticket.order_id,
        "subject": ticket.subject,
        "category": ticket.category,
        "priority": ticket.priority,
        "status": ticket.status,
        "resolved_at": ticket.resolved_at,
        "closed_at": ticket.closed_at,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }
    if include_messages:
        result["messages"] = [
            {
                "id": message.id,
                "author_user_id": message.author_user_id,
                "author_role": message.author_role,
                "body": message.body,
                "request_id": message.request_id,
                "created_at": message.created_at,
            }
            for message in sorted(
                ticket.messages,
                key=lambda item: (item.created_at, item.id),
            )
        ]
    return result


def get_support_ticket_or_404(
    session: Session,
    ticket_id: int,
    current_user: CurrentUser,
) -> SupportTicket:
    ticket = session.scalar(
        select(SupportTicket)
        .options(selectinload(SupportTicket.messages))
        .where(SupportTicket.id == ticket_id)
    )
    if ticket is None:
        raise HTTPException(status_code=404, detail="Support ticket not found")
    if current_user.get("role") not in {"admin", "operator"}:
        require_customer(current_user)
        if ticket.user_id != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Forbidden")
    return ticket


def create_support_ticket(
    session: Session,
    payload: SupportTicketCreateIn,
    current_user: CurrentUser,
) -> SupportTicket:
    require_customer(current_user)
    if payload.order_id is not None:
        get_order_or_404(session, payload.order_id, current_user)
    ticket = SupportTicket(
        public_id=_public_id("SUP"),
        user_id=int(current_user["sub"]),
        order_id=payload.order_id,
        subject=payload.subject.strip(),
        category=payload.category,
        priority=payload.priority,
        status="OPEN",
    )
    ticket.messages.append(
        SupportMessage(
            author_user_id=int(current_user["sub"]),
            author_role="customer",
            body=payload.message.strip(),
            request_id=request_id_context.get(),
        )
    )
    session.add(ticket)
    session.flush()
    queue_customer_notification(
        session,
        user_id=ticket.user_id,
        category="support",
        title=f"Support ticket {ticket.public_id} opened",
        body="Your support request has been received.",
        order_id=ticket.order_id,
        data={"ticket_id": ticket.id, "status": ticket.status},
        template_key="support_ticket_opened",
    )
    session.commit()
    session.refresh(ticket)
    return get_support_ticket_or_404(session, ticket.id, current_user)


def list_customer_support_tickets(
    session: Session,
    current_user: CurrentUser,
    *,
    status_filter: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    require_customer(current_user)
    filters = [SupportTicket.user_id == current_user["sub"]]
    if status_filter:
        filters.append(SupportTicket.status == status_filter)
    total = int(session.scalar(select(func.count(SupportTicket.id)).where(*filters)) or 0)
    tickets = session.scalars(
        select(SupportTicket)
        .where(*filters)
        .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            serialize_support_ticket(ticket, include_messages=False)
            for ticket in tickets
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def add_customer_support_message(
    session: Session,
    ticket_id: int,
    payload: SupportMessageCreateIn,
    current_user: CurrentUser,
) -> SupportTicket:
    require_customer(current_user)
    ticket = get_support_ticket_or_404(session, ticket_id, current_user)
    if ticket.status == "CLOSED":
        raise HTTPException(status_code=409, detail="Closed support tickets cannot receive messages")
    ticket.messages.append(
        SupportMessage(
            author_user_id=int(current_user["sub"]),
            author_role="customer",
            body=payload.body.strip(),
            request_id=request_id_context.get(),
        )
    )
    if ticket.status in {"RESOLVED", "WAITING_CUSTOMER"}:
        ticket.status = "OPEN"
        ticket.resolved_at = None
    ticket.updated_at = utc_now()
    session.commit()
    return get_support_ticket_or_404(session, ticket.id, current_user)


def list_admin_support_tickets(
    session: Session,
    current_user: CurrentUser,
    *,
    q: str | None,
    status_filter: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    require_operator(current_user)
    filters = []
    if status_filter:
        filters.append(SupportTicket.status == status_filter)
    if q:
        needle = f"%{q.strip()}%"
        filters.append(
            or_(
                SupportTicket.public_id.ilike(needle),
                SupportTicket.subject.ilike(needle),
            )
        )
    total = int(session.scalar(select(func.count(SupportTicket.id)).where(*filters)) or 0)
    tickets = session.scalars(
        select(SupportTicket)
        .where(*filters)
        .order_by(SupportTicket.updated_at.desc(), SupportTicket.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            serialize_support_ticket(ticket, include_messages=False)
            for ticket in tickets
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def add_admin_support_message(
    session: Session,
    ticket_id: int,
    payload: SupportMessageCreateIn,
    current_user: CurrentUser,
) -> SupportTicket:
    require_operator(current_user)
    ticket = get_support_ticket_or_404(session, ticket_id, current_user)
    if ticket.status == "CLOSED":
        raise HTTPException(status_code=409, detail="Closed support tickets cannot receive messages")
    before = {"status": ticket.status, "message_count": len(ticket.messages)}
    ticket.messages.append(
        SupportMessage(
            author_user_id=int(current_user["sub"]),
            author_role=str(current_user.get("role") or "operator"),
            body=payload.body.strip(),
            request_id=request_id_context.get(),
        )
    )
    ticket.status = "WAITING_CUSTOMER"
    ticket.updated_at = utc_now()
    session.flush()
    record_admin_audit(
        session,
        current_user,
        action="support.reply_added",
        entity_type="support_ticket",
        entity_id=ticket.id,
        before=before,
        after={"status": ticket.status, "message_count": len(ticket.messages)},
        note="Support response added",
    )
    queue_customer_notification(
        session,
        user_id=ticket.user_id,
        category="support",
        title=f"New reply on {ticket.public_id}",
        body=payload.body.strip(),
        order_id=ticket.order_id,
        data={"ticket_id": ticket.id, "status": ticket.status},
        template_key="support_reply",
    )
    session.commit()
    return get_support_ticket_or_404(session, ticket.id, current_user)


def update_admin_support_status(
    session: Session,
    ticket_id: int,
    payload: AdminSupportStatusIn,
    current_user: CurrentUser,
) -> SupportTicket:
    require_operator(current_user)
    ticket = get_support_ticket_or_404(session, ticket_id, current_user)
    if ticket.status == payload.status:
        return ticket
    if ticket.status == "CLOSED":
        raise HTTPException(status_code=409, detail="Closed support tickets are terminal")
    before = {"status": ticket.status}
    ticket.status = payload.status
    now = utc_now()
    ticket.resolved_at = now if payload.status == "RESOLVED" else None
    ticket.closed_at = now if payload.status == "CLOSED" else None
    ticket.updated_at = now
    ticket.messages.append(
        SupportMessage(
            author_user_id=int(current_user["sub"]),
            author_role=str(current_user.get("role") or "operator"),
            body=payload.note.strip(),
            request_id=payload.request_id or request_id_context.get(),
        )
    )
    session.flush()
    record_admin_audit(
        session,
        current_user,
        action="support.status_changed",
        entity_type="support_ticket",
        entity_id=ticket.id,
        before=before,
        after={"status": ticket.status},
        note=payload.note,
        request_id=payload.request_id,
    )
    queue_customer_notification(
        session,
        user_id=ticket.user_id,
        category="support",
        title=f"Support ticket {ticket.public_id} updated",
        body=payload.note.strip(),
        order_id=ticket.order_id,
        data={"ticket_id": ticket.id, "status": ticket.status},
        template_key="support_status",
    )
    session.commit()
    return get_support_ticket_or_404(session, ticket.id, current_user)


def serialize_dispute(dispute: CustomerDispute) -> dict[str, Any]:
    return {
        "id": dispute.id,
        "public_id": dispute.public_id,
        "user_id": dispute.user_id,
        "order_id": dispute.order_id,
        "type": dispute.dispute_type,
        "description": dispute.description,
        "requested_resolution": dispute.requested_resolution,
        "status": dispute.status,
        "resolution_note": dispute.resolution_note,
        "decided_by_user_id": dispute.decided_by_user_id,
        "request_id": dispute.request_id,
        "decided_at": dispute.decided_at,
        "created_at": dispute.created_at,
        "updated_at": dispute.updated_at,
    }


def get_dispute_or_404(
    session: Session,
    dispute_id: int,
    current_user: CurrentUser,
) -> CustomerDispute:
    dispute = session.get(CustomerDispute, dispute_id)
    if dispute is None:
        raise HTTPException(status_code=404, detail="Dispute not found")
    if current_user.get("role") not in {"admin", "operator"}:
        require_customer(current_user)
        if dispute.user_id != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Forbidden")
    return dispute


def create_customer_dispute(
    session: Session,
    payload: DisputeCreateIn,
    current_user: CurrentUser,
) -> CustomerDispute:
    require_customer(current_user)
    get_order_or_404(session, payload.order_id, current_user)
    duplicate = session.scalar(
        select(CustomerDispute.id).where(
            CustomerDispute.user_id == current_user["sub"],
            CustomerDispute.order_id == payload.order_id,
            CustomerDispute.status.in_(("OPEN", "UNDER_REVIEW")),
        )
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="An active dispute already exists for this order",
        )
    dispute = CustomerDispute(
        public_id=_public_id("DSP"),
        user_id=int(current_user["sub"]),
        order_id=payload.order_id,
        dispute_type=payload.dispute_type,
        description=payload.description.strip(),
        requested_resolution=payload.requested_resolution.strip(),
        status="OPEN",
        request_id=request_id_context.get(),
    )
    session.add(dispute)
    try:
        session.flush()
        queue_customer_notification(
            session,
            user_id=dispute.user_id,
            category="dispute",
            title=f"Dispute {dispute.public_id} opened",
            body="Your dispute has been received for review.",
            order_id=dispute.order_id,
            data={"dispute_id": dispute.id, "status": dispute.status},
            template_key="dispute_opened",
        )
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="An active dispute already exists for this order",
        ) from exc
    session.refresh(dispute)
    return dispute


def list_customer_disputes(
    session: Session,
    current_user: CurrentUser,
    *,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    require_customer(current_user)
    filters = (CustomerDispute.user_id == current_user["sub"],)
    total = int(session.scalar(select(func.count(CustomerDispute.id)).where(*filters)) or 0)
    disputes = session.scalars(
        select(CustomerDispute)
        .where(*filters)
        .order_by(CustomerDispute.updated_at.desc(), CustomerDispute.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [serialize_dispute(item) for item in disputes],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def cancel_customer_dispute(
    session: Session,
    dispute_id: int,
    payload: DisputeCancelIn,
    current_user: CurrentUser,
) -> CustomerDispute:
    require_customer(current_user)
    dispute = get_dispute_or_404(session, dispute_id, current_user)
    if dispute.status not in {"OPEN", "UNDER_REVIEW"}:
        raise HTTPException(status_code=409, detail="This dispute can no longer be cancelled")
    dispute.status = "CANCELLED"
    dispute.resolution_note = payload.note.strip()
    dispute.request_id = request_id_context.get()
    dispute.updated_at = utc_now()
    session.commit()
    session.refresh(dispute)
    return dispute


def list_admin_disputes(
    session: Session,
    current_user: CurrentUser,
    *,
    q: str | None,
    status_filter: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    require_operator(current_user)
    filters = []
    if status_filter:
        filters.append(CustomerDispute.status == status_filter)
    if q:
        needle = f"%{q.strip()}%"
        filters.append(
            or_(
                CustomerDispute.public_id.ilike(needle),
                CustomerDispute.description.ilike(needle),
            )
        )
    total = int(session.scalar(select(func.count(CustomerDispute.id)).where(*filters)) or 0)
    disputes = session.scalars(
        select(CustomerDispute)
        .where(*filters)
        .order_by(CustomerDispute.updated_at.desc(), CustomerDispute.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [serialize_dispute(item) for item in disputes],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def update_admin_dispute(
    session: Session,
    dispute_id: int,
    payload: AdminDisputeDecisionIn,
    current_user: CurrentUser,
) -> CustomerDispute:
    require_operator(current_user)
    dispute = get_dispute_or_404(session, dispute_id, current_user)
    if payload.status == dispute.status:
        return dispute
    if payload.status not in DISPUTE_TRANSITIONS.get(dispute.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid dispute transition: {dispute.status} -> {payload.status}",
        )
    before = {"status": dispute.status, "resolution_note": dispute.resolution_note}
    dispute.status = payload.status
    dispute.resolution_note = payload.note.strip()
    dispute.request_id = payload.request_id or request_id_context.get()
    dispute.updated_at = utc_now()
    if payload.status in {"RESOLVED", "REJECTED"}:
        dispute.decided_at = dispute.updated_at
        dispute.decided_by_user_id = int(current_user["sub"])
    session.flush()
    record_admin_audit(
        session,
        current_user,
        action="dispute.status_changed",
        entity_type="customer_dispute",
        entity_id=dispute.id,
        before=before,
        after={
            "status": dispute.status,
            "resolution_note": dispute.resolution_note,
        },
        note=payload.note,
        request_id=payload.request_id,
    )
    queue_customer_notification(
        session,
        user_id=dispute.user_id,
        category="dispute",
        title=f"Dispute {dispute.public_id} updated",
        body=payload.note.strip(),
        order_id=dispute.order_id,
        data={"dispute_id": dispute.id, "status": dispute.status},
        template_key="dispute_status",
    )
    session.commit()
    session.refresh(dispute)
    return dispute
