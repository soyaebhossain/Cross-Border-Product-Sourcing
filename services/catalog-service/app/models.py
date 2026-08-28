from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class AccountUser(Base):
    __tablename__ = "accounts_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    username_normalized: Mapped[str | None] = mapped_column(String(150), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    email_normalized: Mapped[str | None] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40), unique=True)
    phone_normalized: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="customer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_failed_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auth_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text())
    mfa_recovery_hashes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    mfa_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mfa_failed_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    mfa_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_totp_counter: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SocialIdentity(Base):
    __tablename__ = "accounts_social_identities"
    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_social_provider_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_users.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthChallenge(Base):
    __tablename__ = "accounts_auth_challenges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_users.id"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    remember: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshSession(Base):
    __tablename__ = "accounts_refresh_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("accounts_users.id"), nullable=False, index=True)
    family_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    remember: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoke_reason: Mapped[str | None] = mapped_column(String(40))
    replaced_by_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "catalog_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    products: Mapped[list["Product"]] = relationship(back_populates="category", cascade="all, delete-orphan")


class Product(Base):
    __tablename__ = "catalog_products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text())
    image: Mapped[str | None] = mapped_column(String(500))
    category_id: Mapped[int] = mapped_column(ForeignKey("catalog_categories.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    category: Mapped["Category"] = relationship(back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = "catalog_product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("catalog_products.id"), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    variant_name: Mapped[str | None] = mapped_column(String(120))
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=Decimal("0.000"))
    length_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"))
    width_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    product: Mapped["Product"] = relationship(back_populates="variants")
    offers: Mapped[list["SellerOffer"]] = relationship(back_populates="variant", cascade="all, delete-orphan")


class Country(Base):
    __tablename__ = "sourcing_countries"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    sellers: Mapped[list["Seller"]] = relationship(back_populates="country", cascade="all, delete-orphan")


class Seller(Base):
    __tablename__ = "sourcing_sellers"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("sourcing_countries.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.00"))
    note: Mapped[str | None] = mapped_column(Text())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    country: Mapped["Country"] = relationship(back_populates="sellers")
    offers: Mapped[list["SellerOffer"]] = relationship(back_populates="seller", cascade="all, delete-orphan")


class SellerOffer(Base):
    __tablename__ = "sourcing_seller_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("catalog_product_variants.id"), nullable=False)
    country_id: Mapped[int] = mapped_column(ForeignKey("sourcing_countries.id"), nullable=False)
    seller_id: Mapped[int] = mapped_column(ForeignKey("sourcing_sellers.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), default="LOCAL")
    price_origin: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    moq: Mapped[int] = mapped_column(Integer, default=1)
    source_url: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    variant: Mapped["ProductVariant"] = relationship(back_populates="offers")
    country: Mapped["Country"] = relationship()
    seller: Mapped["Seller"] = relationship(back_populates="offers")


class CurrencyRate(Base):
    __tablename__ = "pricing_currency_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    rate_to_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ServiceFeeRule(Base):
    __tablename__ = "pricing_service_fee_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    fee_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShippingRateCard(Base):
    __tablename__ = "shipping_rate_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("sourcing_countries.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    min_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    max_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    cost_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    country: Mapped["Country"] = relationship()


class ETARule(Base):
    __tablename__ = "shipping_eta_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("sourcing_countries.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    delivery_type: Mapped[str] = mapped_column(String(10), nullable=False)
    min_days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_days: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    country: Mapped["Country"] = relationship()


class DutyRule(Base):
    __tablename__ = "pricing_duty_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("sourcing_countries.id"), nullable=False)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_categories.id"))
    percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0.00"))
    fixed_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_by_user_id: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    country: Mapped["Country"] = relationship()
    category: Mapped["Category | None"] = relationship()


class SavedQuote(Base):
    __tablename__ = "orders_saved_quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    variant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    delivery_type: Mapped[str] = mapped_column(String(10), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    response: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="requested", server_default="requested", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="saved_quote", lazy="selectin")
    ai_explanation: Mapped["AIDecisionExplanation | None"] = relationship(
        back_populates="saved_quote", uselist=False, cascade="all, delete-orphan"
    )


class AIDecisionExplanation(Base):
    __tablename__ = "ai_decision_explanations"

    id: Mapped[int] = mapped_column(primary_key=True)
    saved_quote_id: Mapped[int] = mapped_column(
        ForeignKey("orders_saved_quotes.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False, server_default="quote-v1")
    deterministic_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    explanation: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    human_review_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", index=True
    )
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="NOT_REQUIRED", server_default="NOT_REQUIRED", index=True
    )
    review_note: Mapped[str | None] = mapped_column(Text())
    reviewed_by_user_id: Mapped[int | None] = mapped_column(Integer, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    saved_quote: Mapped["SavedQuote"] = relationship(back_populates="ai_explanation")


class Order(Base):
    __tablename__ = "orders_orders"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_order_user_idempotency"),
        UniqueConstraint("saved_quote_id", name="uq_order_saved_quote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    saved_quote_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders_saved_quotes.id", ondelete="SET NULL"),
        index=True,
    )
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    delivery_type: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    quote_snapshot: Mapped[dict | None] = mapped_column(JSON)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    total_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    shipping_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    advance_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    remaining_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    actual_cost_bdt: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    promised_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    quality_defect_reported: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    saved_quote: Mapped["SavedQuote | None"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    manual_payment: Mapped["ManualPaymentProof | None"] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")
    history: Mapped[list["OrderStatusHistory"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    shipment: Mapped["Shipment | None"] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")
    payment_adjustments: Mapped[list["PaymentAdjustment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "orders_order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders_orders.id"), nullable=False)
    variant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(120), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    offer_id: Mapped[int | None] = mapped_column(Integer)

    order: Mapped["Order"] = relationship(back_populates="items")


class ManualPaymentProof(Base):
    __tablename__ = "orders_manual_payments"
    __table_args__ = (
        UniqueConstraint("channel", "trx_normalized", name="uq_manual_payment_channel_transaction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders_orders.id"), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="bKash")
    trx_id: Mapped[str] = mapped_column(String(80), nullable=False)
    trx_normalized: Mapped[str] = mapped_column(String(80), nullable=False)
    screenshot_url: Mapped[str | None] = mapped_column(String(500))
    verified: Mapped[bool] = mapped_column(default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING", index=True)
    decision_reason: Mapped[str | None] = mapped_column(Text())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by_user_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="manual_payment")
    adjustments: Mapped[list["PaymentAdjustment"]] = relationship(back_populates="payment")
    attempts: Mapped[list["PaymentProofAttempt"]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
    )


class PaymentAdjustment(Base):
    __tablename__ = "orders_payment_adjustments"
    __table_args__ = (
        UniqueConstraint("transaction_id", name="uq_payment_adjustment_transaction"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders_orders.id"), nullable=False, index=True)
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders_manual_payments.id"), index=True
    )
    adjustment_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), default="POSTED", server_default="POSTED", nullable=False, index=True
    )
    amount_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    transaction_id: Mapped[str] = mapped_column(String(80), nullable=False)
    reason: Mapped[str] = mapped_column(Text(), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    reversed_by_user_id: Mapped[int | None] = mapped_column(Integer)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_reason: Mapped[str | None] = mapped_column(Text())

    order: Mapped["Order"] = relationship(back_populates="payment_adjustments")
    payment: Mapped["ManualPaymentProof | None"] = relationship(back_populates="adjustments")


class OrderStatusHistory(Base):
    __tablename__ = "orders_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders_orders.id"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text())
    actor_user_id: Mapped[int | None] = mapped_column(Integer)
    actor_role: Mapped[str | None] = mapped_column(String(20))
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="history")


class Shipment(Base):
    __tablename__ = "logistics_shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders_orders.id"), unique=True, nullable=False)
    tracking_number: Mapped[str | None] = mapped_column(String(120))

    order: Mapped["Order"] = relationship(back_populates="shipment")
    events: Mapped[list["ShipmentEvent"]] = relationship(back_populates="shipment", cascade="all, delete-orphan")


class ShipmentEvent(Base):
    __tablename__ = "logistics_shipment_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    shipment_id: Mapped[int] = mapped_column(ForeignKey("logistics_shipments.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    shipment: Mapped["Shipment"] = relationship(back_populates="events")


class AdminAuditEvent(Base):
    __tablename__ = "admin_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    before_data: Mapped[dict | None] = mapped_column(JSON)
    after_data: Mapped[dict | None] = mapped_column(JSON)
    note: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CustomerProfile(Base):
    __tablename__ = "customer_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(200))
    company_name: Mapped[str | None] = mapped_column(String(200))
    company_registration_number: Mapped[str | None] = mapped_column(String(120))
    tax_identifier: Mapped[str | None] = mapped_column(String(120))
    preferred_language: Mapped[str] = mapped_column(
        String(10), default="en", server_default="en", nullable=False
    )
    preferred_currency: Mapped[str] = mapped_column(
        String(10), default="BDT", server_default="BDT", nullable=False
    )
    timezone: Mapped[str] = mapped_column(
        String(80), default="Asia/Dhaka", server_default="Asia/Dhaka", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(200))
    line1: Mapped[str] = mapped_column(String(250), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(250))
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    region: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(40))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    phone: Mapped[str] = mapped_column(String(40), nullable=False)
    is_default_shipping: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    is_default_billing: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CustomerInvoice(Base):
    __tablename__ = "customer_invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders_orders.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="BDT", server_default="BDT", nullable=False
    )
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class NotificationPreference(Base):
    __tablename__ = "customer_notification_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    order_email: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    order_sms: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    order_whatsapp: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    support_email: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1", nullable=False
    )
    support_sms: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    support_whatsapp: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    marketing_email: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CustomerNotification(Base):
    __tablename__ = "customer_notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders_orders.id", ondelete="SET NULL"), index=True
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"

    id: Mapped[int] = mapped_column(primary_key=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("customer_notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(320), nullable=False)
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="QUEUED", server_default="QUEUED", nullable=False, index=True
    )
    claim_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_id: Mapped[str | None] = mapped_column(String(200))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders_orders.id", ondelete="SET NULL"), index=True
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(
        String(20), default="NORMAL", server_default="NORMAL", nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="OPEN", server_default="OPEN", nullable=False, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )

    messages: Mapped[list["SupportMessage"]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class SupportMessage(Base):
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    author_role: Mapped[str] = mapped_column(String(20), nullable=False)
    body: Mapped[str] = mapped_column(Text(), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    ticket: Mapped["SupportTicket"] = relationship(back_populates="messages")


class CustomerDispute(Base):
    __tablename__ = "customer_disputes"
    __table_args__ = (
        Index(
            "uq_customer_active_dispute_order",
            "user_id",
            "order_id",
            unique=True,
            sqlite_where=text("status IN ('OPEN', 'UNDER_REVIEW')"),
            postgresql_where=text("status IN ('OPEN', 'UNDER_REVIEW')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders_orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    dispute_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text(), nullable=False)
    requested_resolution: Mapped[str] = mapped_column(Text(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="OPEN", server_default="OPEN", nullable=False, index=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text())
    decided_by_user_id: Mapped[int | None] = mapped_column(Integer)
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        index=True,
    )


class PaymentProofAttempt(Base):
    __tablename__ = "orders_payment_proof_attempts"
    __table_args__ = (
        UniqueConstraint("payment_id", "attempt_number", name="uq_payment_attempt_number"),
        UniqueConstraint(
            "channel",
            "trx_normalized",
            name="uq_payment_attempt_channel_transaction",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("orders_manual_payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    trx_id: Mapped[str] = mapped_column(String(80), nullable=False)
    trx_normalized: Mapped[str] = mapped_column(String(80), nullable=False)
    screenshot_url: Mapped[str | None] = mapped_column(String(500))
    submitted_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("accounts_users.id", ondelete="RESTRICT"), nullable=False
    )
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    payment: Mapped["ManualPaymentProof"] = relationship(back_populates="attempts")
    order: Mapped["Order"] = relationship()
    decisions: Mapped[list["PaymentProofDecision"]] = relationship(
        back_populates="attempt", cascade="all, delete-orphan"
    )


class PaymentProofDecision(Base):
    __tablename__ = "orders_payment_proof_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("orders_payment_proof_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text())
    actor_user_id: Mapped[int | None] = mapped_column(Integer)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    attempt: Mapped["PaymentProofAttempt"] = relationship(back_populates="decisions")
