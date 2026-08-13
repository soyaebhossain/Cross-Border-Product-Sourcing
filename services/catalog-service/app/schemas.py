from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class LoginIn(BaseModel):
    identifier: str | None = None
    username: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str
    remember: bool = True
    portal: Literal["customer", "admin"] = "customer"


class RegisterIn(BaseModel):
    username: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str = Field(min_length=8, max_length=128)
    role: str = "customer"


class PasswordResetRequestIn(BaseModel):
    identifier: str = Field(min_length=1, max_length=320)


class PasswordResetConfirmIn(BaseModel):
    token: str = Field(min_length=32, max_length=512)
    password: str = Field(min_length=8, max_length=128)


class MFAChallengeIn(BaseModel):
    mfa_token: str = Field(min_length=32, max_length=4096)


class MFAEnrollmentConfirmIn(MFAChallengeIn):
    code: str = Field(min_length=6, max_length=12)


class MFAVerifyIn(MFAChallengeIn):
    code: str | None = Field(default=None, min_length=6, max_length=12)
    recovery_code: str | None = Field(default=None, min_length=10, max_length=30)

    @model_validator(mode="after")
    def require_authenticator_or_recovery_code(self) -> "MFAVerifyIn":
        if not self.code and not self.recovery_code:
            raise ValueError("Authenticator code or recovery code required")
        return self


class QuoteRequestIn(BaseModel):
    variant_id: int
    country: str = Field(min_length=2, max_length=2, pattern="^[A-Za-z]{2}$")
    mode: Literal["LOCAL", "BULK"]
    qty: int = Field(ge=1)
    delivery_type: Literal["DOOR", "PICKUP"]
    language: Literal["en", "bn"] = "en"


class QuoteRecommendIn(BaseModel):
    variant_id: int
    qty: int = Field(default=1, ge=1)
    delivery_type: str = "DOOR"
    priority: str = "balanced"


class CheapestCountryRecommendIn(BaseModel):
    variant_id: int | None = None
    product_slug: str | None = None
    qty: int = Field(default=1, ge=1)
    delivery_type: str = "DOOR"
    priority: str = "balanced"
    countries: list[str] | None = None
    weights: dict[str, float] | None = None
    language: Literal["en", "bn"] = "en"


class SaveQuoteIn(QuoteRequestIn):
    response: dict[str, Any]


class UpdateQuoteStatusIn(BaseModel):
    status: str = Field(pattern="^(requested|received|approved|expired)$")


class AIReviewDecisionIn(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    note: str = Field(min_length=3, max_length=2000)
    request_id: str | None = Field(default=None, max_length=100)


class CreateOrderIn(QuoteRequestIn):
    saved_quote_id: int | None = Field(default=None, ge=1)
    offer_id: int | None = Field(default=None, ge=1)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=80)
    trx_id: str = Field(min_length=3, max_length=80)
    channel: Literal["bKash", "Nagad", "Rocket", "Bank"] = "bKash"
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


class UpdateOrderStatusIn(BaseModel):
    status: Literal["PENDING", "CONFIRMED", "PURCHASED", "IN_TRANSIT", "CUSTOMS", "LOCAL_DISPATCH", "DELIVERED", "CANCELLED"]
    note: str | None = Field(default=None, max_length=1000)
    tracking_number: str | None = Field(default=None, max_length=120)
    shipment_note: str | None = Field(default=None, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_transition_note(self) -> "UpdateOrderStatusIn":
        if not (self.note or self.shipment_note or "").strip():
            raise ValueError("An operational note is required")
        return self


class AdminPaymentDecisionIn(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    reason: str | None = Field(default=None, max_length=1000)
    note: str | None = Field(default=None, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_decision_reason(self) -> "AdminPaymentDecisionIn":
        if not (self.reason or self.note or "").strip():
            raise ValueError("A payment decision note is required")
        return self
