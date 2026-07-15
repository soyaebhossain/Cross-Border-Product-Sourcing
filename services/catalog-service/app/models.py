from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class AccountUser(Base):
    __tablename__ = "accounts_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    phone: Mapped[str | None] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="customer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "catalog_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)

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

    category: Mapped["Category"] = relationship(back_populates="products")
    variants: Mapped[list["ProductVariant"]] = relationship(back_populates="product", cascade="all, delete-orphan")


class ProductVariant(Base):
    __tablename__ = "catalog_product_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("catalog_products.id"), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(80))
    variant_name: Mapped[str | None] = mapped_column(String(120))
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), default=Decimal("0.000"))
    length_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"))
    width_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=Decimal("0.00"))

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
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    variant: Mapped["ProductVariant"] = relationship(back_populates="offers")
    country: Mapped["Country"] = relationship()
    seller: Mapped["Seller"] = relationship(back_populates="offers")


class CurrencyRate(Base):
    __tablename__ = "pricing_currency_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    rate_to_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)


class ServiceFeeRule(Base):
    __tablename__ = "pricing_service_fee_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    fee_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    percent: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0.00"))


class ShippingRateCard(Base):
    __tablename__ = "shipping_rate_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("sourcing_countries.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    min_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    max_kg: Mapped[Decimal] = mapped_column(Numeric(8, 3), nullable=False)
    cost_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    country: Mapped["Country"] = relationship()


class ETARule(Base):
    __tablename__ = "shipping_eta_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    country_id: Mapped[int] = mapped_column(ForeignKey("sourcing_countries.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    delivery_type: Mapped[str] = mapped_column(String(10), nullable=False)
    min_days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_days: Mapped[int] = mapped_column(Integer, nullable=False)

    country: Mapped["Country"] = relationship()


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Order(Base):
    __tablename__ = "orders_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    delivery_type: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    total_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    shipping_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    advance_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    remaining_bdt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    manual_payment: Mapped["ManualPaymentProof | None"] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")
    history: Mapped[list["OrderStatusHistory"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    shipment: Mapped["Shipment | None"] = relationship(back_populates="order", uselist=False, cascade="all, delete-orphan")


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

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders_orders.id"), unique=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(20), default="bKash")
    trx_id: Mapped[str] = mapped_column(String(80), nullable=False)
    screenshot_url: Mapped[str | None] = mapped_column(String(500))
    verified: Mapped[bool] = mapped_column(default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="manual_payment")


class OrderStatusHistory(Base):
    __tablename__ = "orders_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders_orders.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text())
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
