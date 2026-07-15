from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    identifier: str | None = None
    username: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str


class RegisterIn(BaseModel):
    username: str | None = None
    email: str | None = None
    phone: str | None = None
    password: str = Field(min_length=6)
    role: str = "customer"


class QuoteRequestIn(BaseModel):
    variant_id: int
    country: str = Field(min_length=2, max_length=2)
    mode: str
    qty: int = Field(ge=1)
    delivery_type: str


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


class SaveQuoteIn(QuoteRequestIn):
    response: dict[str, Any]


class UpdateQuoteStatusIn(BaseModel):
    status: str = Field(pattern="^(requested|received|approved|expired)$")


class CreateOrderIn(QuoteRequestIn):
    offer_id: int | None = None
    trx_id: str
    channel: str = "bKash"
    screenshot_url: str | None = None


class UpdateOrderStatusIn(BaseModel):
    status: str
    note: str | None = None
    tracking_number: str | None = None
    shipment_note: str | None = None
