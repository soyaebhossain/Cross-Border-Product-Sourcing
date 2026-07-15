from __future__ import annotations

from decimal import Decimal
from typing import Any

from .config import get_settings
from .models import Category, Country, Order, Product, ProductVariant, SavedQuote


settings = get_settings()


def decimal_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value, "f")


def normalize_image_path(src: str | None) -> str | None:
    if not src:
        return None
    if src.startswith("http://") or src.startswith("https://") or src.startswith("//"):
        return src
    if src.startswith(settings.media_url_path):
        return src
    return f"{settings.media_url_path}/{src.lstrip('/')}"


def serialize_category(category: Category) -> dict[str, Any]:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
    }


def serialize_country(country: Country) -> dict[str, Any]:
    return {
        "code": country.code,
        "name": country.name,
    }


def serialize_variant(variant: ProductVariant) -> dict[str, Any]:
    return {
        "id": variant.id,
        "sku": variant.sku,
        "variant_name": variant.variant_name,
        "weight_kg": decimal_str(variant.weight_kg),
        "length_cm": decimal_str(variant.length_cm),
        "width_cm": decimal_str(variant.width_cm),
        "height_cm": decimal_str(variant.height_cm),
    }


def serialize_product(product: Product) -> dict[str, Any]:
    variants = [serialize_variant(variant) for variant in product.variants]
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "model": product.model,
        "description": product.description,
        "image": normalize_image_path(product.image),
        "category": serialize_category(product.category),
        "variants": variants,
        "default_variant_id": variants[0]["id"] if variants else None,
    }


def serialize_saved_quote(saved_quote: SavedQuote) -> dict[str, Any]:
    return {
        "id": saved_quote.id,
        "variant_id": saved_quote.variant_id,
        "product_name": saved_quote.product_name,
        "variant_name": saved_quote.variant_name,
        "country_id": saved_quote.country_code,
        "mode": saved_quote.mode,
        "delivery_type": saved_quote.delivery_type,
        "qty": saved_quote.qty,
        "response": saved_quote.response,
        "status": (saved_quote.response or {}).get("status", "requested"),
        "expires_at": (saved_quote.response or {}).get("expires_at"),
        "created_at": saved_quote.created_at,
    }


def serialize_order(order: Order) -> dict[str, Any]:
    return {
        "id": order.id,
        "status": order.status,
        "country_id": order.country_code,
        "mode": order.mode,
        "delivery_type": order.delivery_type,
        "total_bdt": decimal_str(order.total_bdt),
        "advance_bdt": decimal_str(order.advance_bdt),
        "remaining_bdt": decimal_str(order.remaining_bdt),
        "items": [
            {
                "variant_id": item.variant_id,
                "product_name": item.product_name,
                "variant_name": item.variant_name,
                "qty": item.qty,
                "offer_id": item.offer_id,
            }
            for item in order.items
        ],
        "manual_payment": {
            "channel": order.manual_payment.channel,
            "trx_id": order.manual_payment.trx_id,
            "screenshot_url": order.manual_payment.screenshot_url,
            "verified": order.manual_payment.verified,
            "verified_at": order.manual_payment.verified_at,
            "created_at": order.manual_payment.created_at,
        }
        if order.manual_payment
        else None,
        "shipment": {
            "tracking_number": order.shipment.tracking_number,
            "events": [
                {
                    "status": event.status,
                    "note": event.note,
                    "created_at": event.created_at,
                }
                for event in order.shipment.events
            ],
        }
        if order.shipment
        else {"tracking_number": None, "events": []},
        "history": [
            {
                "status": history.status,
                "note": history.note,
                "created_at": history.created_at,
            }
            for history in order.history
        ],
        "payment_intents": [],
        "created_at": order.created_at,
    }
