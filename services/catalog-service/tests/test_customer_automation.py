from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.api.routes.customer import get_current_customer
from app.auth import ALLOWED_ROLES
from app.customer_schemas import (
    AddressCreateIn,
    AdminDisputeDecisionIn,
    AdminSupportStatusIn,
    CustomerProfileUpdateIn,
    DisputeCreateIn,
    PaymentRetryIn,
    SupportMessageCreateIn,
    SupportTicketCreateIn,
)
from app.models import (
    AccountUser,
    AdminAuditEvent,
    CustomerAddress,
    CustomerInvoice,
    ManualPaymentProof,
    NotificationOutbox,
    Order,
    OrderItem,
    PaymentProofAttempt,
    PaymentProofDecision,
)
from app.schemas import AdminPaymentDecisionIn, CreateOrderIn
from app.security import request_id_context
from app.services.customer_account import (
    build_invoice_html,
    build_invoice_pdf,
    create_customer_address,
    get_customer_address_or_404,
    get_customer_invoice,
    serialize_customer_profile,
    update_customer_profile,
)
from app.services.customer_payments import retry_manual_payment
from app.services.customer_support import (
    add_admin_support_message,
    create_customer_dispute,
    create_support_ticket,
    update_admin_dispute,
    update_admin_support_status,
)
from app.services.notifications import (
    dispatch_outbox_batch,
    queue_customer_notification,
)
from app.services.orders import decide_manual_payment_record
from app.db import Base


ADMIN = {"sub": 1, "role": "admin"}
CUSTOMER = {"sub": 2, "role": "customer"}
OTHER_CUSTOMER = {"sub": 3, "role": "customer"}


@pytest.fixture()
def session() -> Session:
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as value:
        value.add_all(
            [
                AccountUser(
                    id=1,
                    username="admin",
                    email="admin@example.test",
                    password_hash="not-used",
                    role="admin",
                    is_active=True,
                    is_staff=True,
                    is_superuser=True,
                ),
                AccountUser(
                    id=2,
                    username="buyer",
                    email="buyer@example.test",
                    phone="+8801700000000",
                    password_hash="not-used",
                    role="customer",
                    is_active=True,
                ),
                AccountUser(
                    id=3,
                    username="other",
                    email="other@example.test",
                    password_hash="not-used",
                    role="customer",
                    is_active=True,
                ),
            ]
        )
        order = Order(
            id=10,
            user_id=2,
            country_code="CN",
            mode="LOCAL",
            delivery_type="DOOR",
            status="PENDING",
            quote_snapshot={"locked": True},
            total_bdt=Decimal("1250.00"),
            shipping_bdt=Decimal("250.00"),
            advance_bdt=Decimal("750.00"),
            remaining_bdt=Decimal("500.00"),
        )
        order.items.append(
            OrderItem(
                variant_id=50,
                product_name="Medical monitor",
                variant_name="Standard",
                qty=2,
            )
        )
        order.manual_payment = ManualPaymentProof(
            channel="bKash",
            trx_id="OLD-TX-01",
            trx_normalized="oldtx01",
            verified=False,
            decision="REJECTED",
            decision_reason="Reference not found",
            decided_by_user_id=1,
        )
        value.add(order)
        value.commit()
        payment = order.manual_payment
        first_attempt = PaymentProofAttempt(
            payment_id=payment.id,
            order_id=order.id,
            attempt_number=1,
            channel=payment.channel,
            trx_id=payment.trx_id,
            trx_normalized=payment.trx_normalized,
            screenshot_url=None,
            submitted_by_user_id=2,
        )
        first_attempt.decisions.append(
            PaymentProofDecision(
                decision="REJECTED",
                reason="Reference not found",
                actor_user_id=1,
                actor_role="admin",
            )
        )
        value.add(first_attempt)
        value.commit()
        yield value
    engine.dispose()


def test_customer_profile_address_defaults_and_ownership(session: Session) -> None:
    profile = update_customer_profile(
        session,
        CustomerProfileUpdateIn(
            full_name="ক্রয় ব্যবস্থাপক",
            company_name="আল আমিন ট্রেডিং",
            preferred_language="bn",
            preferred_currency="usd",
            timezone="Asia/Dhaka",
        ),
        CUSTOMER,
    )
    serialized = serialize_customer_profile(session, profile)
    assert serialized["preferences"] == {
        "language": "bn",
        "currency": "USD",
        "timezone": "Asia/Dhaka",
    }

    home = create_customer_address(
        session,
        AddressCreateIn(
            label="Office",
            recipient_name="ক্রয় ব্যবস্থাপক",
            company_name="আল আমিন ট্রেডিং",
            line1="১২৩ মতিঝিল",
            city="ঢাকা",
            country_code="bd",
            phone="+8801700000000",
        ),
        CUSTOMER,
    )
    assert home.is_default_shipping and home.is_default_billing
    with pytest.raises(HTTPException) as forbidden:
        get_customer_address_or_404(session, home.id, OTHER_CUSTOMER)
    assert forbidden.value.status_code == 403


def test_invoice_snapshot_is_immutable_and_unicode_download_is_lossless(
    session: Session,
) -> None:
    update_customer_profile(
        session,
        CustomerProfileUpdateIn(
            full_name="ক্রয় ব্যবস্থাপক",
            company_name="আল আমিন ট্রেডিং",
        ),
        CUSTOMER,
    )
    address = create_customer_address(
        session,
        AddressCreateIn(
            label="Billing",
            recipient_name="ক্রয় ব্যবস্থাপক",
            line1="১২৩ মতিঝিল",
            city="ঢাকা",
            country_code="BD",
            phone="+8801700000000",
        ),
        CUSTOMER,
    )
    first = get_customer_invoice(session, 10, CUSTOMER)
    stored = session.scalar(select(CustomerInvoice).where(CustomerInvoice.order_id == 10))
    assert stored is not None
    captured_snapshot = stored.snapshot

    address.line1 = "Changed after issue"
    session.get(Order, 10).total_bdt = Decimal("9999.00")
    session.commit()
    second = get_customer_invoice(session, 10, CUSTOMER)

    assert second["total_bdt"] == first["total_bdt"] == "1250.00"
    assert stored.snapshot == captured_snapshot
    html = build_invoice_html(second)
    assert "ক্রয় ব্যবস্থাপক".encode("utf-8") in html
    assert html.startswith(b"<!doctype html>")
    pdf = build_invoice_pdf(second)
    assert pdf.startswith(b"%PDF-1.4")

    with pytest.raises(HTTPException) as forbidden:
        get_customer_invoice(session, 10, OTHER_CUSTOMER)
    assert forbidden.value.status_code == 403


def test_payment_retry_preserves_attempts_and_records_one_decision_per_action(
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.customer_payments.get_settings",
        lambda: Settings(database_url="sqlite://", payment_proof_allowed_hosts="proofs.example.test"),
    )
    order, retry = retry_manual_payment(
        session,
        10,
        PaymentRetryIn(
            channel="Nagad",
            trx_id="NEW-TX-02",
            screenshot_url="https://proofs.example.test/payment/new.png",
        ),
        CUSTOMER,
    )
    assert retry.attempt_number == 2
    assert order.manual_payment.decision == "PENDING"
    assert session.scalar(
        select(PaymentProofAttempt.trx_id).where(
            PaymentProofAttempt.attempt_number == 1
        )
    ) == "OLD-TX-01"

    decided = decide_manual_payment_record(
        session,
        10,
        AdminPaymentDecisionIn(
            decision="APPROVED",
            reason="Verified against settlement report",
            request_id="req-payment-approved",
        ),
        ADMIN,
    )
    assert decided.status == "CONFIRMED"
    decisions = session.scalars(
        select(PaymentProofDecision).where(
            PaymentProofDecision.attempt_id == retry.id,
            PaymentProofDecision.decision == "APPROVED",
        )
    ).all()
    assert len(decisions) == 1
    assert decisions[0].request_id == "req-payment-approved"

    with pytest.raises(HTTPException, match="order is pending"):
        retry_manual_payment(
            session,
            10,
            PaymentRetryIn(channel="Nagad", trx_id="NEW-TX-03"),
            CUSTOMER,
        )


def test_notifications_queue_real_delivery_and_fail_closed_without_provider(
    session: Session,
) -> None:
    notification = queue_customer_notification(
        session,
        user_id=2,
        category="order",
        title="Order update",
        body="Payment received",
        order_id=10,
    )
    session.commit()
    outbox = session.scalar(
        select(NotificationOutbox).where(
            NotificationOutbox.notification_id == notification.id
        )
    )
    assert outbox is not None and outbox.status == "QUEUED"

    result = dispatch_outbox_batch(
        session,
        settings=Settings(database_url="sqlite://"),
        limit=10,
    )
    session.refresh(outbox)
    assert result == {"selected": 1, "sent": 0, "failed": 1}
    assert outbox.status == "FAILED"
    assert outbox.error_code == "provider_not_configured"
    assert outbox.claim_token is None
    assert "buyer@example.test" not in (outbox.error_detail or "")


def test_support_dispute_ownership_and_privileged_audit(
    session: Session,
) -> None:
    context = request_id_context.set("req-support-create")
    try:
        ticket = create_support_ticket(
            session,
            SupportTicketCreateIn(
                subject="Payment help",
                category="PAYMENT",
                priority="HIGH",
                message="Please review the rejected reference.",
                order_id=10,
            ),
            CUSTOMER,
        )
    finally:
        request_id_context.reset(context)
    assert ticket.messages[0].request_id == "req-support-create"

    add_admin_support_message(
        session,
        ticket.id,
        SupportMessageCreateIn(body="We are reviewing the settlement report."),
        ADMIN,
    )
    ticket = update_admin_support_status(
        session,
        ticket.id,
        AdminSupportStatusIn(
            status="RESOLVED",
            note="The payment retry option is enabled.",
            request_id="req-support-resolve",
        ),
        ADMIN,
    )
    assert ticket.status == "RESOLVED"

    dispute = create_customer_dispute(
        session,
        DisputeCreateIn(
            order_id=10,
            dispute_type="PAYMENT",
            description="The earlier transaction was reversed unexpectedly.",
            requested_resolution="Review and confirm the new transaction.",
        ),
        CUSTOMER,
    )
    dispute = update_admin_dispute(
        session,
        dispute.id,
        AdminDisputeDecisionIn(
            status="UNDER_REVIEW",
            note="Assigned to payment operations.",
            request_id="req-dispute-review",
        ),
        ADMIN,
    )
    assert dispute.status == "UNDER_REVIEW"
    events = session.scalars(
        select(AdminAuditEvent).where(
            AdminAuditEvent.request_id.in_(
                ("req-support-resolve", "req-dispute-review")
            )
        )
    ).all()
    assert {event.action for event in events} == {
        "support.status_changed",
        "dispute.status_changed",
    }


def test_payment_proof_urls_are_https_only() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        PaymentRetryIn(
            channel="bKash",
            trx_id="ABC123",
            screenshot_url="http://proofs.example.test/file.png",
        )
    with pytest.raises(ValueError, match="HTTPS"):
        CreateOrderIn(
            variant_id=1,
            country="CN",
            mode="LOCAL",
            qty=1,
            delivery_type="DOOR",
            trx_id="ABC123",
            screenshot_url="javascript:alert(1)",
        )


def test_customer_dependency_rejects_admin_and_operator() -> None:
    assert ALLOWED_ROLES == {"customer", "operator", "admin"}
    with pytest.raises(HTTPException) as admin_forbidden:
        get_current_customer(ADMIN)
    assert admin_forbidden.value.status_code == 403
    with pytest.raises(HTTPException) as operator_forbidden:
        get_current_customer({"sub": 4, "role": "operator"})
    assert operator_forbidden.value.status_code == 403


def test_production_notification_transports_fail_closed() -> None:
    base = {
        "environment": "production",
        "database_url": (
            "postgresql+psycopg://sourceai:unique-password@db:5432/cross_border"
        ),
        "jwt_secret": "unique-production-jwt-secret-with-at-least-32-characters",
        "cors_origins": "https://app.example.test",
        "frontend_url": "https://app.example.test",
        "secure_cookies": True,
        "mfa_encryption_key": "EnFxjaW8RPNIWnzKAp9uQz891m0RVLkLxn1QV9gaf0c=",
        "payment_proof_allowed_hosts": "proofs.example.test",
        "error_monitoring_dsn": "https://public-key@errors.example.test/1",
    }
    with pytest.raises(RuntimeError, match="SMS provider webhook must use HTTPS"):
        Settings(
            **base,
            sms_webhook_url="http://sms.example.test/send",
            sms_api_token="secret-token",
        ).validate_runtime_security()
    with pytest.raises(RuntimeError, match="SMTP_STARTTLS"):
        Settings(
            **base,
            smtp_host="smtp.example.test",
            smtp_from_email="orders@example.test",
            smtp_starttls=False,
        ).validate_runtime_security()
