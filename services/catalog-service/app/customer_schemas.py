from __future__ import annotations

from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator


class CustomerProfileUpdateIn(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    company_registration_number: str | None = Field(default=None, max_length=120)
    tax_identifier: str | None = Field(default=None, max_length=120)
    preferred_language: Literal["en", "bn"] | None = None
    preferred_currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=10,
        pattern=r"^[A-Za-z]+$",
    )
    timezone: str | None = Field(default=None, min_length=1, max_length=80)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def require_change(self) -> "CustomerProfileUpdateIn":
        if not self.model_fields_set:
            raise ValueError("At least one profile field is required")
        return self


class AddressCreateIn(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    recipient_name: str = Field(min_length=2, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    line1: str = Field(min_length=3, max_length=250)
    line2: str | None = Field(default=None, max_length=250)
    city: str = Field(min_length=2, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=40)
    country_code: str = Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")
    phone: str = Field(min_length=5, max_length=40)
    is_default_shipping: bool = False
    is_default_billing: bool = False

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.upper()


class AddressUpdateIn(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    recipient_name: str | None = Field(default=None, min_length=2, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)
    line1: str | None = Field(default=None, min_length=3, max_length=250)
    line2: str | None = Field(default=None, max_length=250)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=40)
    country_code: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Za-z]{2}$",
    )
    phone: str | None = Field(default=None, min_length=5, max_length=40)
    is_default_shipping: bool | None = None
    is_default_billing: bool | None = None

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @model_validator(mode="after")
    def require_change(self) -> "AddressUpdateIn":
        if not self.model_fields_set:
            raise ValueError("At least one address field is required")
        return self


class NotificationPreferenceUpdateIn(BaseModel):
    order_email: bool | None = None
    order_sms: bool | None = None
    order_whatsapp: bool | None = None
    support_email: bool | None = None
    support_sms: bool | None = None
    support_whatsapp: bool | None = None
    marketing_email: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "NotificationPreferenceUpdateIn":
        if not self.model_fields_set:
            raise ValueError("At least one notification preference is required")
        return self


class SupportTicketCreateIn(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    category: Literal[
        "ORDER",
        "PAYMENT",
        "SHIPPING",
        "PRODUCT",
        "ACCOUNT",
        "OTHER",
    ] = "OTHER"
    priority: Literal["LOW", "NORMAL", "HIGH", "URGENT"] = "NORMAL"
    message: str = Field(min_length=3, max_length=5000)
    order_id: int | None = Field(default=None, ge=1)


class SupportMessageCreateIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class AdminSupportStatusIn(BaseModel):
    status: Literal[
        "OPEN",
        "IN_PROGRESS",
        "WAITING_CUSTOMER",
        "RESOLVED",
        "CLOSED",
    ]
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class DisputeCreateIn(BaseModel):
    order_id: int = Field(ge=1)
    dispute_type: Literal[
        "PAYMENT",
        "PRODUCT_QUALITY",
        "MISSING_ITEM",
        "DELIVERY",
        "REFUND",
        "OTHER",
    ]
    description: str = Field(min_length=10, max_length=5000)
    requested_resolution: str = Field(min_length=3, max_length=2000)


class DisputeCancelIn(BaseModel):
    note: str = Field(min_length=3, max_length=1000)


class AdminDisputeDecisionIn(BaseModel):
    status: Literal["UNDER_REVIEW", "RESOLVED", "REJECTED"]
    note: str = Field(min_length=3, max_length=2000)
    request_id: str | None = Field(default=None, max_length=100)


class PaymentRetryIn(BaseModel):
    channel: Literal["bKash", "Nagad", "Rocket", "Bank"] = "bKash"
    trx_id: str = Field(min_length=3, max_length=80)
    screenshot_url: str | None = Field(default=None, max_length=500)

    @field_validator("screenshot_url")
    @classmethod
    def validate_payment_proof_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Payment proof must use a valid HTTPS URL")
        return value
