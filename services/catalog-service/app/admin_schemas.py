from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AuditNoteIn(BaseModel):
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class ArchiveIn(AuditNoteIn):
    archived: bool = True


class BulkArchiveIn(ArchiveIn):
    ids: list[int] = Field(min_length=1, max_length=100)


class CategoryCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class CategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class ProductCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    category_id: int = Field(ge=1)
    model: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=10000)
    image: str | None = Field(default=None, max_length=500)


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=200,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    category_id: int | None = Field(default=None, ge=1)
    model: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=10000)
    image: str | None = Field(default=None, max_length=500)
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class VariantCreateIn(BaseModel):
    product_id: int = Field(ge=1)
    sku: str | None = Field(default=None, max_length=80)
    variant_name: str | None = Field(default=None, max_length=120)
    weight_kg: Decimal = Field(default=Decimal("0"), ge=0)
    length_cm: Decimal = Field(default=Decimal("0"), ge=0)
    width_cm: Decimal = Field(default=Decimal("0"), ge=0)
    height_cm: Decimal = Field(default=Decimal("0"), ge=0)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        normalized = value.strip().upper() if value is not None else ""
        return normalized or None


class VariantUpdateIn(BaseModel):
    sku: str | None = Field(default=None, max_length=80)
    variant_name: str | None = Field(default=None, max_length=120)
    weight_kg: Decimal | None = Field(default=None, ge=0)
    length_cm: Decimal | None = Field(default=None, ge=0)
    width_cm: Decimal | None = Field(default=None, ge=0)
    height_cm: Decimal | None = Field(default=None, ge=0)
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        normalized = value.strip().upper() if value is not None else ""
        return normalized or None


class SupplierCreateIn(BaseModel):
    country_id: int = Field(ge=1)
    name: str = Field(min_length=2, max_length=120)
    rating: Decimal = Field(default=Decimal("0"), ge=0, le=5)
    note: str | None = Field(default=None, max_length=5000)


class SupplierUpdateIn(BaseModel):
    country_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    supplier_note: str | None = Field(default=None, max_length=5000)
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class OfferCreateIn(BaseModel):
    variant_id: int = Field(ge=1)
    country_id: int = Field(ge=1)
    seller_id: int = Field(ge=1)
    mode: Literal["LOCAL", "BULK"] = "LOCAL"
    price_origin: Decimal = Field(gt=0, le=Decimal("9999999999.99"))
    currency: str = Field(default="USD", min_length=3, max_length=10, pattern=r"^[A-Za-z]+$")
    stock: int = Field(default=0, ge=0)
    moq: int = Field(default=1, ge=1)
    source_url: str | None = Field(default=None, max_length=500)


class OfferUpdateIn(BaseModel):
    variant_id: int | None = Field(default=None, ge=1)
    country_id: int | None = Field(default=None, ge=1)
    seller_id: int | None = Field(default=None, ge=1)
    mode: Literal["LOCAL", "BULK"] | None = None
    price_origin: Decimal | None = Field(
        default=None,
        gt=0,
        le=Decimal("9999999999.99"),
    )
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=10,
        pattern=r"^[A-Za-z]+$",
    )
    stock: int | None = Field(default=None, ge=0)
    moq: int | None = Field(default=None, ge=1)
    source_url: str | None = Field(default=None, max_length=500)
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class UserAdminUpdateIn(BaseModel):
    role: Literal["customer", "operator", "admin"] | None = None
    is_active: bool | None = None
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_change(self) -> "UserAdminUpdateIn":
        if self.role is None and self.is_active is None:
            raise ValueError("At least one user field must be changed")
        return self


class CurrencyRateIn(BaseModel):
    currency: str = Field(min_length=3, max_length=10, pattern=r"^[A-Za-z]+$")
    rate_to_bdt: Decimal = Field(gt=0)
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class ServiceFeeRuleIn(BaseModel):
    mode: Literal["LOCAL", "BULK"]
    fee_bdt: Decimal = Field(default=Decimal("0"), ge=0)
    percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class ShippingRateCardIn(BaseModel):
    country_id: int = Field(ge=1)
    method: Literal["AIR", "SEA"]
    min_kg: Decimal = Field(ge=0)
    max_kg: Decimal = Field(gt=0)
    cost_bdt: Decimal = Field(ge=0)
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_range(self) -> "ShippingRateCardIn":
        if self.max_kg <= self.min_kg:
            raise ValueError("max_kg must be greater than min_kg")
        return self


class ETARuleIn(BaseModel):
    country_id: int = Field(ge=1)
    mode: Literal["LOCAL", "BULK"]
    delivery_type: Literal["DOOR", "PICKUP"]
    min_days: int = Field(ge=0, le=365)
    max_days: int = Field(ge=0, le=365)
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_range(self) -> "ETARuleIn":
        if self.max_days < self.min_days:
            raise ValueError("max_days must not be less than min_days")
        return self


class DutyRuleIn(BaseModel):
    country_id: int = Field(ge=1)
    category_id: int | None = Field(default=None, ge=1)
    percent: Decimal = Field(ge=0, le=100)
    fixed_bdt: Decimal = Field(default=Decimal("0"), ge=0)
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_dates(self) -> "DutyRuleIn":
        if self.effective_from and self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be after effective_from")
        return self


class PaymentReversalIn(AuditNoteIn):
    pass


class RefundCreateIn(BaseModel):
    amount_bdt: Decimal = Field(gt=0)
    transaction_id: str | None = Field(default=None, min_length=6, max_length=80)
    reason: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)


class RefundReverseIn(AuditNoteIn):
    pass


class OrderSettlementIn(BaseModel):
    actual_cost_bdt: Decimal | None = Field(default=None, ge=0)
    promised_delivery_at: datetime | None = None
    delivered_at: datetime | None = None
    quality_defect_reported: bool | None = None
    note: str = Field(min_length=3, max_length=1000)
    request_id: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def require_change(self) -> "OrderSettlementIn":
        if (
            self.actual_cost_bdt is None
            and self.promised_delivery_at is None
            and self.delivered_at is None
            and self.quality_defect_reported is None
        ):
            raise ValueError("At least one settlement or fulfilment field is required")
        return self
