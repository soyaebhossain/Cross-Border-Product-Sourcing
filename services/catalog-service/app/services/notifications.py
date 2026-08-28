from __future__ import annotations

import json
import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
from types import SimpleNamespace

import resend
from fastapi import HTTPException
from resend.exceptions import NoContentError, ResendError
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..models import (
    AccountUser,
    CustomerNotification,
    NotificationOutbox,
    NotificationPreference,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeliveryError(RuntimeError):
    def __init__(self, code: str, safe_detail: str) -> None:
        super().__init__(safe_detail)
        self.code = code
        self.safe_detail = safe_detail


@dataclass(frozen=True)
class DeliveryReceipt:
    provider_message_id: str | None = None


class NotificationAdapter(Protocol):
    @property
    def configured(self) -> bool: ...

    def send(self, outbox: NotificationOutbox) -> DeliveryReceipt: ...


class SMTPEmailAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return self.settings.smtp_email_configured

    def send(self, outbox: NotificationOutbox) -> DeliveryReceipt:
        if not self.configured:
            raise DeliveryError("provider_not_configured", "Email provider is not configured")
        message = EmailMessage()
        message["Subject"] = str(outbox.payload.get("title") or "SourceAI notification")
        message["From"] = (
            f"{self.settings.notification_sender_name} <{self.settings.smtp_from_email}>"
        )
        message["To"] = outbox.destination
        message["Message-ID"] = f"<sourceai-outbox-{outbox.id}@notifications.local>"
        message.set_content(str(outbox.payload.get("body") or ""))
        try:
            with smtplib.SMTP(
                self.settings.smtp_host,
                self.settings.smtp_port,
                timeout=15,
            ) as client:
                if self.settings.smtp_starttls:
                    client.starttls(context=ssl.create_default_context())
                if self.settings.smtp_username and self.settings.smtp_password:
                    client.login(
                        self.settings.smtp_username,
                        self.settings.smtp_password,
                    )
                client.send_message(message)
        except (OSError, smtplib.SMTPException):
            # Provider errors are deliberately not copied into logs or stored
            # records because they can echo credentials or destinations.
            raise DeliveryError("provider_delivery_failed", "Email provider rejected the delivery") from None
        return DeliveryReceipt()


class ResendEmailAdapter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def configured(self) -> bool:
        return self.settings.resend_email_configured

    def send(self, outbox: NotificationOutbox) -> DeliveryReceipt:
        if not self.configured or self.settings.resend_api_key is None:
            raise DeliveryError("provider_not_configured", "Email provider is not configured")
        # The SDK uses a module-level key. SourceAI has one immutable provider key per process.
        resend.api_key = self.settings.resend_api_key.get_secret_value()
        title = str(outbox.payload.get("title") or "SourceAI notification")
        body = str(outbox.payload.get("body") or "")
        action_url = str(outbox.payload.get("action_url") or "")
        sender = f"{self.settings.notification_sender_name} <{self.settings.resend_from_email}>"
        try:
            response = resend.Emails.send(
                {
                    "from": sender,
                    "to": [outbox.destination],
                    "subject": title,
                    "text": body,
                    "html": _render_transactional_email_html(title, body, action_url=action_url),
                },
                {"idempotency_key": f"sourceai-outbox-{outbox.id}"},
            )
            provider_id = str(response.get("id") or "").strip()
            if not provider_id:
                raise DeliveryError(
                    "provider_delivery_failed",
                    "Email provider rejected the delivery",
                )
        except DeliveryError:
            raise
        except (ResendError, NoContentError, OSError, ValueError, TypeError):
            # Provider exceptions can echo the API key, recipient, or reset URL.
            raise DeliveryError(
                "provider_delivery_failed",
                "Email provider rejected the delivery",
            ) from None
        return DeliveryReceipt(provider_message_id=provider_id)


def _render_transactional_email_html(title: str, body: str, *, action_url: str = "") -> str:
    safe_title = escape(title)
    safe_body = escape(body).replace("\n", "<br>")
    parsed_action = urlsplit(action_url)
    safe_action = ""
    if (
        parsed_action.scheme in {"http", "https"}
        and parsed_action.netloc
        and not parsed_action.username
        and not parsed_action.password
    ):
        safe_action = escape(action_url, quote=True)
    action_markup = (
        '<tr><td style="padding:0 32px 28px">'
        f'<a href="{safe_action}" style="display:inline-block;border-radius:9px;background:#2563eb;'
        'padding:13px 20px;color:#ffffff;font-size:14px;font-weight:700;text-decoration:none">'
        "Open secure link</a></td></tr>"
        if safe_action
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
  <body style="margin:0;background:#f4f7fb;color:#172033;font-family:Arial,sans-serif">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:32px 16px;background:#f4f7fb">
      <tr><td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;border:1px solid #dbe3ef;border-radius:16px;background:#ffffff">
          <tr><td style="padding:28px 32px 12px;font-size:18px;font-weight:700;color:#12336b">Source<span style="color:#2563eb">AI</span></td></tr>
          <tr><td style="padding:12px 32px 8px"><h1 style="margin:0;font-size:24px;line-height:1.25;color:#0b1730">{safe_title}</h1></td></tr>
          <tr><td style="padding:8px 32px 28px;font-size:15px;line-height:1.7;color:#475569">{safe_body}</td></tr>
          {action_markup}
          <tr><td style="padding:18px 32px;border-top:1px solid #e6ebf2;font-size:12px;color:#8491a5">Security notice from SourceAI</td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>"""


def email_adapter_for(settings: Settings) -> NotificationAdapter:
    if settings.resend_email_configured:
        return ResendEmailAdapter(settings)
    return SMTPEmailAdapter(settings)


def send_password_reset_email(
    destination: str,
    reset_url: str,
    *,
    settings: Settings | None = None,
) -> bool:
    """Send a reset link without persisting the bearer token in the notification tables."""

    runtime_settings = settings or get_settings()
    adapter = email_adapter_for(runtime_settings)
    if not adapter.configured:
        return False
    minutes = max(1, runtime_settings.password_reset_seconds // 60)
    message = SimpleNamespace(
        id=f"password-reset-{uuid4().hex}",
        destination=destination,
        payload={
            "title": "Reset your SourceAI password",
            "body": (
                "A password reset was requested for your SourceAI account.\n\n"
                f"Open this secure link within {minutes} minutes:\n{reset_url}\n\n"
                "If you did not request this, you can safely ignore this email."
            ),
            "action_url": reset_url,
        },
    )
    try:
        adapter.send(message)
    except DeliveryError:
        return False
    return True


def send_password_changed_email(
    destination: str,
    *,
    settings: Settings | None = None,
) -> bool:
    """Send a token-free security notice after a successful reset."""

    runtime_settings = settings or get_settings()
    adapter = email_adapter_for(runtime_settings)
    if not adapter.configured:
        return False
    message = SimpleNamespace(
        id=f"password-changed-{uuid4().hex}",
        destination=destination,
        payload={
            "title": "Your SourceAI password was changed",
            "body": (
                "Your SourceAI password was changed and all existing sessions were signed out.\n\n"
                "If you did not make this change, contact support immediately."
            ),
        },
    )
    try:
        adapter.send(message)
    except DeliveryError:
        return False
    return True


class WebhookNotificationAdapter:
    def __init__(
        self,
        *,
        channel: str,
        webhook_url: str | None,
        api_token: str | None,
        sender_id: str | None,
    ) -> None:
        self.channel = channel
        self.webhook_url = webhook_url
        self.api_token = api_token
        self.sender_id = sender_id

    @property
    def configured(self) -> bool:
        return bool(self.webhook_url and self.api_token)

    def send(self, outbox: NotificationOutbox) -> DeliveryReceipt:
        if not self.configured:
            raise DeliveryError(
                "provider_not_configured",
                f"{self.channel.title()} provider is not configured",
            )
        payload = json.dumps(
            {
                "channel": self.channel,
                "to": outbox.destination,
                "sender_id": self.sender_id,
                "template": outbox.template_key,
                "data": outbox.payload,
                "idempotency_key": f"sourceai-outbox-{outbox.id}",
            }
        ).encode("utf-8")
        request = Request(
            str(self.webhook_url),
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
                "User-Agent": "SourceAI-Notification-Worker/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310 - URL is deployment-owned env config.
                if not 200 <= int(response.status) < 300:
                    raise DeliveryError(
                        "provider_delivery_failed",
                        f"{self.channel.title()} provider rejected the delivery",
                    )
                provider_id = response.headers.get("X-Message-ID")
        except DeliveryError:
            raise
        except (HTTPError, URLError, OSError):
            raise DeliveryError(
                "provider_delivery_failed",
                f"{self.channel.title()} provider rejected the delivery",
            ) from None
        return DeliveryReceipt(provider_message_id=provider_id)


def _adapter_for(channel: str, settings: Settings) -> NotificationAdapter:
    if channel == "email":
        return email_adapter_for(settings)
    if channel == "sms":
        return WebhookNotificationAdapter(
            channel="sms",
            webhook_url=settings.sms_webhook_url,
            api_token=settings.sms_api_token,
            sender_id=settings.sms_sender_id,
        )
    if channel == "whatsapp":
        return WebhookNotificationAdapter(
            channel="whatsapp",
            webhook_url=settings.whatsapp_webhook_url,
            api_token=settings.whatsapp_api_token,
            sender_id=settings.whatsapp_sender_id,
        )
    raise DeliveryError("unsupported_channel", "Notification channel is not supported")


def get_or_create_notification_preferences(
    session: Session,
    user_id: int,
) -> NotificationPreference:
    preference = session.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if preference is None:
        user = session.get(AccountUser, user_id)
        email_available = bool(user and (user.email or "").strip())
        preference = NotificationPreference(
            user_id=user_id,
            order_email=email_available,
            support_email=email_available,
        )
        session.add(preference)
        session.flush()
    return preference


def serialize_notification_preferences(preference: NotificationPreference) -> dict[str, Any]:
    return {
        "order_email": preference.order_email,
        "order_sms": preference.order_sms,
        "order_whatsapp": preference.order_whatsapp,
        "support_email": preference.support_email,
        "support_sms": preference.support_sms,
        "support_whatsapp": preference.support_whatsapp,
        "marketing_email": preference.marketing_email,
        "updated_at": preference.updated_at,
    }


def update_notification_preferences(
    session: Session,
    user_id: int,
    changes: dict[str, bool | None],
) -> NotificationPreference:
    preference = get_or_create_notification_preferences(session, user_id)
    user = session.get(AccountUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    email_requested = any(
        changes.get(field) is True
        for field in ("order_email", "support_email", "marketing_email")
    )
    phone_requested = any(
        changes.get(field) is True
        for field in (
            "order_sms",
            "order_whatsapp",
            "support_sms",
            "support_whatsapp",
        )
    )
    if email_requested and not (user.email or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Add a verified account email before enabling email notifications",
        )
    if phone_requested and not (user.phone or "").strip():
        raise HTTPException(
            status_code=422,
            detail="Add an account phone number before enabling SMS or WhatsApp notifications",
        )
    for field, value in changes.items():
        if value is not None:
            setattr(preference, field, value)
    preference.updated_at = utc_now()
    session.commit()
    session.refresh(preference)
    return preference


def _channel_enabled(
    preference: NotificationPreference,
    category: str,
    channel: str,
) -> bool:
    group = "support" if category in {"support", "dispute"} else "order"
    return bool(getattr(preference, f"{group}_{channel}"))


def queue_customer_notification(
    session: Session,
    *,
    user_id: int,
    category: str,
    title: str,
    body: str,
    order_id: int | None = None,
    data: dict[str, Any] | None = None,
    template_key: str | None = None,
) -> CustomerNotification:
    notification = CustomerNotification(
        user_id=user_id,
        order_id=order_id,
        category=category,
        title=title,
        body=body,
        data=data or {},
    )
    session.add(notification)
    session.flush()

    user = session.get(AccountUser, user_id)
    preference = get_or_create_notification_preferences(session, user_id)
    destinations = {
        "email": user.email if user else None,
        "sms": user.phone if user else None,
        "whatsapp": user.phone if user else None,
    }
    for channel, destination in destinations.items():
        if not _channel_enabled(preference, category, channel):
            continue
        if not destination:
            # The in-app notification remains available. Do not create a
            # permanently failed external delivery with an empty recipient.
            continue
        session.add(
            NotificationOutbox(
                notification_id=notification.id,
                user_id=user_id,
                channel=channel,
                destination=str(destination or ""),
                template_key=template_key or category,
                payload={
                    "title": title,
                    "body": body,
                    "order_id": order_id,
                    **(data or {}),
                },
                status="QUEUED",
                error_code=None,
                error_detail=None,
            )
        )
    return notification


def serialize_outbox(outbox: NotificationOutbox) -> dict[str, Any]:
    destination = outbox.destination
    if "@" in destination:
        left, _, right = destination.partition("@")
        destination_masked = f"{left[:2]}***@{right}"
    elif destination:
        destination_masked = f"***{destination[-4:]}"
    else:
        destination_masked = None
    return {
        "id": outbox.id,
        "channel": outbox.channel,
        "destination_masked": destination_masked,
        "status": outbox.status,
        "attempts": outbox.attempts,
        "next_attempt_at": outbox.next_attempt_at,
        "last_attempt_at": outbox.last_attempt_at,
        "sent_at": outbox.sent_at,
        "provider_message_id": outbox.provider_message_id,
        "error_code": outbox.error_code,
        "error_detail": outbox.error_detail,
        "created_at": outbox.created_at,
    }


def serialize_customer_notification(
    session: Session,
    notification: CustomerNotification,
) -> dict[str, Any]:
    deliveries = session.scalars(
        select(NotificationOutbox)
        .where(NotificationOutbox.notification_id == notification.id)
        .order_by(NotificationOutbox.id)
    ).all()
    return {
        "id": notification.id,
        "order_id": notification.order_id,
        "category": notification.category,
        "title": notification.title,
        "body": notification.body,
        "data": notification.data,
        "read_at": notification.read_at,
        "created_at": notification.created_at,
        "deliveries": [serialize_outbox(item) for item in deliveries],
    }


def dispatch_outbox_batch(
    session: Session,
    *,
    settings: Settings | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    runtime_settings = settings or get_settings()
    batch_size = min(
        max(int(limit or runtime_settings.notification_dispatch_batch_size), 1),
        50,
    )
    now = utc_now()
    stale_before = now - timedelta(minutes=30)
    session.execute(
        update(NotificationOutbox)
        .where(
            NotificationOutbox.status == "PROCESSING",
            NotificationOutbox.claimed_at < stale_before,
        )
        .values(
            status="QUEUED",
            claim_token=None,
            claimed_at=None,
            error_code="stale_claim_recovered",
            error_detail="A stale worker claim was recovered",
        )
    )
    candidate_ids = session.scalars(
        select(NotificationOutbox.id)
        .where(
            NotificationOutbox.status == "QUEUED",
            or_(
                NotificationOutbox.next_attempt_at.is_(None),
                NotificationOutbox.next_attempt_at <= now,
            ),
        )
        .order_by(NotificationOutbox.id)
        .limit(batch_size)
    ).all()
    claims: list[tuple[int, str]] = []
    for item_id in candidate_ids:
        claim_token = uuid4().hex
        claimed = session.execute(
            update(NotificationOutbox)
            .where(
                NotificationOutbox.id == item_id,
                NotificationOutbox.status == "QUEUED",
            )
            .values(
                status="PROCESSING",
                claim_token=claim_token,
                claimed_at=utc_now(),
                attempts=NotificationOutbox.attempts + 1,
                last_attempt_at=utc_now(),
                error_code=None,
                error_detail=None,
            )
        )
        if claimed.rowcount == 1:
            claims.append((item_id, claim_token))
    session.commit()

    result = {"selected": len(claims), "sent": 0, "failed": 0}
    for item_id, claim_token in claims:
        item = session.scalar(
            select(NotificationOutbox).where(
                NotificationOutbox.id == item_id,
                NotificationOutbox.status == "PROCESSING",
                NotificationOutbox.claim_token == claim_token,
            )
        )
        if item is None:
            continue
        try:
            receipt = _adapter_for(item.channel, runtime_settings).send(item)
        except DeliveryError as exc:
            item.status = "FAILED"
            item.error_code = exc.code
            item.error_detail = exc.safe_detail
            result["failed"] += 1
        else:
            item.status = "SENT"
            item.sent_at = utc_now()
            item.provider_message_id = receipt.provider_message_id
            result["sent"] += 1
        item.claim_token = None
        item.claimed_at = None
        session.commit()
    return result


def requeue_failed_outbox(
    session: Session,
    *,
    outbox_id: int,
) -> NotificationOutbox:
    outbox = session.get(NotificationOutbox, outbox_id)
    if outbox is None:
        raise LookupError("Outbox record not found")
    if outbox.status != "FAILED":
        raise ValueError("Only failed deliveries can be requeued")
    outbox.status = "QUEUED"
    outbox.claim_token = None
    outbox.claimed_at = None
    outbox.next_attempt_at = None
    outbox.error_code = None
    outbox.error_detail = None
    session.commit()
    session.refresh(outbox)
    return outbox
