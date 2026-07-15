from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from ..models import (
    Country,
    CurrencyRate,
    ETARule,
    Product,
    ProductVariant,
    SellerOffer,
    ServiceFeeRule,
    ShippingRateCard,
)
from ..schemas import CheapestCountryRecommendIn, QuoteRecommendIn, QuoteRequestIn
from ..serializers import decimal_str


def get_variant_or_404(session: Session, variant_id: int) -> ProductVariant:
    variant = session.scalar(
        select(ProductVariant)
        .options(joinedload(ProductVariant.product))
        .where(ProductVariant.id == variant_id)
    )
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant


def get_country_or_404(session: Session, code: str) -> Country:
    country = session.scalar(select(Country).where(Country.code == code.upper()))
    if not country:
        raise HTTPException(status_code=404, detail="Country not found")
    return country


def get_variant_for_recommendation(
    session: Session,
    variant_id: int | None = None,
    product_slug: str | None = None,
) -> ProductVariant:
    if variant_id is not None:
        return get_variant_or_404(session, variant_id)

    if not product_slug:
        raise HTTPException(status_code=422, detail="Either variant_id or product_slug is required")

    product = session.scalar(
        select(Product)
        .options(selectinload(Product.variants), joinedload(Product.category))
        .where(Product.slug == product_slug)
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.variants:
        raise HTTPException(status_code=404, detail="Product has no variants")

    return product.variants[0]


def to_bdt(session: Session, amount: Decimal, currency: str) -> Decimal:
    if currency.upper() == "BDT":
        return amount
    rate = session.scalar(select(CurrencyRate).where(CurrencyRate.currency == currency.upper()))
    if not rate:
        return amount
    return amount * rate.rate_to_bdt


def shipping_cost_bdt(session: Session, country: Country, mode: str, total_weight: Decimal) -> Decimal:
    method = "AIR" if mode == "LOCAL" else "SEA"
    card = session.scalar(
        select(ShippingRateCard)
        .where(
            ShippingRateCard.country_id == country.id,
            ShippingRateCard.method == method,
            ShippingRateCard.min_kg <= total_weight,
            ShippingRateCard.max_kg >= total_weight,
        )
        .order_by(ShippingRateCard.cost_bdt.asc())
        .limit(1)
    )
    return card.cost_bdt if card else Decimal("0.00")


def eta_range(session: Session, country: Country, mode: str, delivery_type: str) -> tuple[int, int]:
    rule = session.scalar(
        select(ETARule).where(
            ETARule.country_id == country.id,
            ETARule.mode == mode,
            ETARule.delivery_type == delivery_type,
        )
    )
    if not rule:
        return (7, 14) if mode == "LOCAL" else (15, 30)
    return rule.min_days, rule.max_days


def service_fee_bdt(session: Session, mode: str, subtotal: Decimal) -> Decimal:
    rule = session.scalar(select(ServiceFeeRule).where(ServiceFeeRule.mode == mode))
    if not rule:
        return Decimal("0.00")
    percent_fee = subtotal * (rule.percent / Decimal("100.00"))
    return rule.fee_bdt + percent_fee


def build_quote(session: Session, payload: QuoteRequestIn) -> dict[str, Any]:
    variant = get_variant_or_404(session, payload.variant_id)
    country = get_country_or_404(session, payload.country)

    offers = session.scalars(
        select(SellerOffer)
        .options(joinedload(SellerOffer.seller))
        .where(
            SellerOffer.variant_id == variant.id,
            SellerOffer.country_id == country.id,
            SellerOffer.mode == payload.mode,
            SellerOffer.stock >= payload.qty,
            SellerOffer.moq <= payload.qty,
        )
    ).all()

    offers = sorted(offers, key=lambda item: (item.price_origin, -float(item.seller.rating)))
    top_offers = offers[:3]
    selected = top_offers[0] if top_offers else None

    origin_total = Decimal("0.00")
    currency = "USD"
    if selected:
        currency = selected.currency
        origin_total = Decimal(selected.price_origin) * Decimal(payload.qty)

    origin_bdt = to_bdt(session, origin_total, currency)
    total_weight = Decimal(variant.weight_kg) * Decimal(payload.qty)
    shipping_bdt = shipping_cost_bdt(session, country, payload.mode, total_weight)
    subtotal = origin_bdt + shipping_bdt
    customs_duty = subtotal * Decimal("0.05")
    vat_tax = subtotal * Decimal("0.05")
    handling_charge = service_fee_bdt(session, payload.mode, subtotal)
    other_import_cost = Decimal("0.00")
    duty_vat = customs_duty + vat_tax
    service_fee = handling_charge
    total = origin_bdt + shipping_bdt + customs_duty + vat_tax + handling_charge + other_import_cost
    advance_ratio = Decimal("0.60") if payload.mode == "LOCAL" else Decimal("0.80")
    advance = total * advance_ratio
    remaining = total - advance
    eta_min, eta_max = eta_range(session, country, payload.mode, payload.delivery_type)

    return {
        "offers_top": [
            {
                "id": offer.id,
                "seller": offer.seller.name,
                "price_origin": decimal_str(offer.price_origin),
                "currency": offer.currency,
                "stock": offer.stock,
                "rating": decimal_str(offer.seller.rating),
                "moq": offer.moq,
            }
            for offer in top_offers
        ],
        "selected_offer_id": selected.id if selected else None,
        "breakdown": {
            "product_cost_bdt": decimal_str(origin_bdt),
            "origin_price_bdt": decimal_str(origin_bdt),
            "shipping_bdt": decimal_str(shipping_bdt),
            "customs_duty_bdt": decimal_str(customs_duty),
            "vat_tax_bdt": decimal_str(vat_tax),
            "handling_charge_bdt": decimal_str(handling_charge),
            "other_import_cost_bdt": decimal_str(other_import_cost),
            "duty_vat_bdt": decimal_str(duty_vat),
            "service_fee_bdt": decimal_str(service_fee),
            "total_bdt": decimal_str(total),
            "advance_bdt": decimal_str(advance),
            "remaining_bdt": decimal_str(remaining),
        },
        "eta": {
            "min_days": eta_min,
            "max_days": eta_max,
        },
    }


def recommendation_weights(priority: str) -> dict[str, Decimal]:
    priorities = {
        "cheap": {
            "cost": Decimal("1.00"),
            "time": Decimal("0.20"),
            "quality": Decimal("0.10"),
            "reliability": Decimal("0.10"),
        },
        "fast": {
            "cost": Decimal("0.45"),
            "time": Decimal("1.00"),
            "quality": Decimal("0.12"),
            "reliability": Decimal("0.18"),
        },
        "balanced": {
            "cost": Decimal("0.80"),
            "time": Decimal("0.50"),
            "quality": Decimal("0.18"),
            "reliability": Decimal("0.20"),
        },
    }
    return priorities.get(priority.lower(), priorities["balanced"])


def build_reliability_score(offer: SellerOffer, qty: int) -> Decimal:
    rating_component = (Decimal(offer.seller.rating or 0) / Decimal("5.00")) * Decimal("0.70")
    stock_ratio = Decimal(min(offer.stock, max(qty, 1) * 20)) / Decimal(max(qty, 1) * 20)
    stock_component = stock_ratio * Decimal("0.30")
    return min(rating_component + stock_component, Decimal("1.00"))


def normalized_weights(payload: CheapestCountryRecommendIn) -> dict[str, Decimal]:
    """Return 0..1 buyer weights; custom values may be percentages or fractions."""
    defaults = recommendation_weights(payload.priority)
    mapped = {
        "price": defaults["cost"], "quality": defaults["quality"],
        "delivery": defaults["time"], "reliability": defaults["reliability"],
        "risk": Decimal("0.35"),
    }
    if payload.weights:
        for key in mapped:
            if key in payload.weights:
                value = Decimal(str(max(0, payload.weights[key])))
                mapped[key] = value / Decimal("100") if value > 1 else value
    total = sum(mapped.values()) or Decimal("1")
    return {key: value / total for key, value in mapped.items()}


def risk_assessment(reliability: Decimal, quality: Decimal, eta_max: int, mode: str) -> tuple[str, Decimal, list[str]]:
    points = Decimal("0")
    weaknesses: list[str] = []
    if reliability < Decimal("0.65"):
        points += Decimal("0.40"); weaknesses.append("limited supplier reliability")
    if quality < Decimal("7"):
        points += Decimal("0.25"); weaknesses.append("quality evidence is below target")
    if eta_max > 25:
        points += Decimal("0.25"); weaknesses.append("delivery time is long")
    if mode == "BULK":
        points += Decimal("0.10"); weaknesses.append("sea freight has higher delay exposure")
    level = "High" if points >= Decimal("0.60") else "Medium" if points >= Decimal("0.30") else "Low"
    return level, min(points, Decimal("1")), weaknesses


def build_country_recommendations(
    session: Session,
    payload: CheapestCountryRecommendIn,
) -> dict[str, Any]:
    variant = get_variant_for_recommendation(
        session,
        variant_id=payload.variant_id,
        product_slug=payload.product_slug,
    )
    requested_country_codes = [code.strip().upper() for code in payload.countries or [] if code.strip()]
    weights = normalized_weights(payload)

    country_query = select(Country).order_by(Country.name.asc())
    if requested_country_codes:
        country_query = country_query.where(Country.code.in_(requested_country_codes))
    countries = session.scalars(country_query).all()
    if not countries:
        raise HTTPException(status_code=404, detail="No sourcing countries found")

    recommendations: list[dict[str, Any]] = []
    for country in countries:
        for mode in ("LOCAL", "BULK"):
            try:
                quote = build_quote(
                    session,
                    QuoteRequestIn(
                        variant_id=variant.id,
                        country=country.code,
                        mode=mode,
                        qty=payload.qty,
                        delivery_type=payload.delivery_type,
                    ),
                )
            except HTTPException:
                continue

            selected_offer_id = quote.get("selected_offer_id")
            if not selected_offer_id:
                continue

            selected_offer = session.scalar(
                select(SellerOffer)
                .options(joinedload(SellerOffer.seller), joinedload(SellerOffer.country))
                .where(SellerOffer.id == selected_offer_id)
            )
            if not selected_offer:
                continue

            total_bdt = Decimal(quote["breakdown"]["total_bdt"])
            eta_max = Decimal(str(quote["eta"]["max_days"]))
            quality_score = Decimal(selected_offer.seller.rating or 0) * Decimal("2.00")
            reliability_score = build_reliability_score(selected_offer, payload.qty)
            risk_level, risk_score, weaknesses = risk_assessment(reliability_score, quality_score, int(eta_max), mode)

            recommendations.append(
                {
                    "country": {"code": country.code, "name": country.name},
                    "mode": mode,
                    "risk_level": risk_level, "risk_score": risk_score, "weaknesses": weaknesses,
                    "estimated_total_bdt": quote["breakdown"]["total_bdt"],
                    "estimated_shipping_bdt": quote["breakdown"]["shipping_bdt"],
                    "estimated_duty_vat_bdt": quote["breakdown"]["duty_vat_bdt"],
                    "estimated_service_fee_bdt": quote["breakdown"]["service_fee_bdt"],
                    "eta": quote["eta"],
                    "quality_score": quality_score,
                    "reliability_score": reliability_score,
                    "selected_offer": {
                        "id": selected_offer.id,
                        "seller_name": selected_offer.seller.name,
                        "price_origin": decimal_str(selected_offer.price_origin),
                        "currency": selected_offer.currency,
                        "stock": selected_offer.stock,
                        "moq": selected_offer.moq,
                        "source_url": selected_offer.source_url,
                    },
                }
            )

    if not recommendations:
        raise HTTPException(status_code=404, detail="No sourcing recommendations available")

    lowest_cost = min(Decimal(item["estimated_total_bdt"]) for item in recommendations)
    fastest_eta = min(item["eta"]["max_days"] for item in recommendations)
    best_quality = max(Decimal(item["quality_score"]) for item in recommendations)

    max_cost = max(Decimal(item["estimated_total_bdt"]) for item in recommendations) or Decimal("1")
    max_eta = max(Decimal(str(item["eta"]["max_days"])) for item in recommendations) or Decimal("1")
    for item in recommendations:
        cost_value = Decimal(item["estimated_total_bdt"])
        eta_value = Decimal(str(item["eta"]["max_days"]))
        item["score"] = Decimal("100") * (
            (Decimal("1") - cost_value / max_cost) * weights["price"]
            + (Decimal(item["quality_score"]) / Decimal("10")) * weights["quality"]
            + (Decimal("1") - eta_value / max_eta) * weights["delivery"]
            + Decimal(item["reliability_score"]) * weights["reliability"]
            + (Decimal("1") - Decimal(item["risk_score"])) * weights["risk"]
        )
    recommendations.sort(key=lambda item: item["score"], reverse=True)
    ranked_recommendations: list[dict[str, Any]] = []
    for index, item in enumerate(recommendations, start=1):
        reasons: list[str] = []
        if Decimal(item["estimated_total_bdt"]) == lowest_cost:
            reasons.append("lowest landed cost")
        if item["eta"]["max_days"] == fastest_eta:
            reasons.append("fastest ETA")
        if Decimal(item["quality_score"]) == best_quality:
            reasons.append("strongest supplier quality")
        if not reasons:
            reasons.append("balanced trade-off across cost, ETA, and supplier quality")

        ranked_recommendations.append(
            {
                "rank": index,
                "country": item["country"],
                "mode": item["mode"],
                "score": decimal_str(item["score"]),
                "estimated_total_bdt": item["estimated_total_bdt"],
                "estimated_shipping_bdt": item["estimated_shipping_bdt"],
                "estimated_duty_vat_bdt": item["estimated_duty_vat_bdt"],
                "estimated_service_fee_bdt": item["estimated_service_fee_bdt"],
                "eta": item["eta"],
                "quality_score": decimal_str(item["quality_score"]),
                "reliability_score": decimal_str(item["reliability_score"]),
                "risk_level": item["risk_level"],
                "risk_score": decimal_str(item["risk_score"]),
                "weaknesses": item["weaknesses"],
                "advantages": reasons,
                "selected_offer": item["selected_offer"],
                "reason": ", ".join(reasons).capitalize() + ".",
            }
        )

    return {
        "product": {
            "id": variant.product.id,
            "name": variant.product.name,
            "slug": variant.product.slug,
            "variant_id": variant.id,
            "variant_name": variant.variant_name or variant.sku or "Default",
        },
        "priority": payload.priority.lower(),
        "delivery_type": payload.delivery_type,
        "qty": payload.qty,
        "methodology": {
            "type": "heuristic-hybrid",
            "summary": "Ranks countries using landed cost, ETA, seller quality, and reliability from the rebuilt sourcing dataset.",
            "weights": {key: decimal_str(value) for key, value in weights.items()},
        },
        "recommendations": ranked_recommendations,
        "data_gaps": [
            "Supply-chain CSV rows are imported as dataset-backed products, suppliers, stock, MOQ, and origin prices.",
            "Supplier quality is estimated from inspection results and defect rates in the CSV.",
            "Shipping and tariff rules are still normalized reference estimates until carrier-specific feeds are connected.",
            "External marketplace and tariff feeds should replace seeded heuristics before production rollout.",
        ],
    }


def recommend_routes(session: Session, payload: QuoteRecommendIn) -> list[dict[str, Any]]:
    priorities = {
        "fast": {"time": Decimal("0.70"), "cost": Decimal("0.30")},
        "cheap": {"time": Decimal("0.30"), "cost": Decimal("0.70")},
        "balanced": {"time": Decimal("0.50"), "cost": Decimal("0.50")},
    }
    weights = priorities.get(payload.priority.lower(), priorities["balanced"])
    countries = session.scalars(select(Country).where(Country.code.in_(["CN", "SG", "TH"]))).all()
    routes: list[dict[str, Any]] = []

    for country in countries:
        for mode in ["LOCAL", "BULK"]:
            try:
                quote = build_quote(
                    session,
                    QuoteRequestIn(
                        variant_id=payload.variant_id,
                        country=country.code,
                        mode=mode,
                        qty=payload.qty,
                        delivery_type=payload.delivery_type,
                    ),
                )
            except HTTPException:
                continue

            total = Decimal(quote["breakdown"]["total_bdt"])
            eta_max = Decimal(str(quote["eta"]["max_days"]))
            score = (weights["cost"] * total) + (weights["time"] * eta_max * Decimal("1000"))
            routes.append(
                {
                    "country": country.code,
                    "mode": mode,
                    "total_bdt": quote["breakdown"]["total_bdt"],
                    "eta": quote["eta"],
                    "selected_offer_id": quote["selected_offer_id"],
                    "offers_top": quote["offers_top"],
                    "score": decimal_str(score),
                }
            )

    return sorted(routes, key=lambda route: Decimal(route["score"]))
