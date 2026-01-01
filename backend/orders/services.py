from decimal import Decimal
from django.utils import timezone
from catalog.models import ProductVariant
from sourcing.models import Country, SellerOffer
from pricing.models import CurrencyRate, ServiceFeeRule
from shipping.models import ShippingRateCard, ETARule
from .models import OrderStatusHistory, Order

def to_bdt(amount: Decimal, currency: str) -> Decimal:
    if currency.upper() == "BDT":
        return amount
    rate = CurrencyRate.objects.filter(currency=currency.upper()).first()
    if not rate:
        # fallback: treat as 1:1 to avoid crash, but better to raise
        return amount
    return (amount * rate.rate_to_bdt)

def pick_best_offer(variant, country, mode, qty: int):
    offers = (SellerOffer.objects
              .filter(variant=variant, country=country, mode=mode, stock__gte=qty, moq__lte=qty)
              .order_by("price_origin", "-seller__rating"))
    return offers

def shipping_cost_bdt(country, mode, weight_kg: Decimal) -> Decimal:
    method = "AIR" if mode == "LOCAL" else "SEA"
    card = (ShippingRateCard.objects
            .filter(country=country, method=method, min_kg__lte=weight_kg, max_kg__gte=weight_kg)
            .order_by("cost_bdt")
            .first())
    return card.cost_bdt if card else Decimal("0.0")

def eta_range(country, mode, delivery_type):
    rule = ETARule.objects.filter(country=country, mode=mode, delivery_type=delivery_type).first()
    if not rule:
        return (7, 14) if mode == "LOCAL" else (15, 30)
    return (rule.min_days, rule.max_days)

def service_fee_bdt(mode, subtotal_bdt: Decimal) -> Decimal:
    rule = ServiceFeeRule.objects.filter(mode=mode).first()
    if not rule:
        return Decimal("0.0")
    pct = (subtotal_bdt * (rule.percent / Decimal("100.0"))) if rule.percent else Decimal("0.0")
    return (rule.fee_bdt or Decimal("0.0")) + pct

def duty_vat_estimate_bdt(subtotal_bdt: Decimal) -> Decimal:
    # MVP: simple placeholder, later category-based import rules
    # Example: 10% estimate
    return subtotal_bdt * Decimal("0.10")

def advance_ratio(mode: str) -> Decimal:
    # MVP rule: Local 60%, Bulk 80%
    return Decimal("0.60") if mode == "LOCAL" else Decimal("0.80")

def generate_quote(variant_id: int, country_code: str, mode: str, qty: int, delivery_type: str):
    variant = ProductVariant.objects.get(id=variant_id)
    country = Country.objects.get(code=country_code.upper())

    offers_qs = pick_best_offer(variant, country, mode, qty)
    top_offers = list(offers_qs[:3])
    selected = top_offers[0] if top_offers else None

    # origin price
    origin_total = Decimal("0.0")
    currency = "USD"
    if selected:
        currency = selected.currency
        origin_total = Decimal(selected.price_origin) * Decimal(qty)

    origin_bdt = to_bdt(origin_total, currency)

    # shipping based on variant weight * qty
    total_weight = Decimal(variant.weight_kg) * Decimal(qty)
    ship_bdt = shipping_cost_bdt(country, mode, total_weight)

    subtotal = origin_bdt + ship_bdt
    duty_vat = duty_vat_estimate_bdt(subtotal)
    fee = service_fee_bdt(mode, subtotal)

    total = subtotal + duty_vat + fee
    adv = total * advance_ratio(mode)
    rem = total - adv

    eta_min, eta_max = eta_range(country, mode, delivery_type)

    return {
        "offers_top": [
            {
                "id": o.id,
                "seller": o.seller.name,
                "price_origin": str(o.price_origin),
                "currency": o.currency,
                "stock": o.stock,
                "rating": str(o.seller.rating),
                "moq": o.moq,
            } for o in top_offers
        ],
        "selected_offer_id": selected.id if selected else None,
        "breakdown": {
            "origin_price_bdt": str(origin_bdt),
            "shipping_bdt": str(ship_bdt),
            "duty_vat_bdt": str(duty_vat),
            "service_fee_bdt": str(fee),
            "total_bdt": str(total),
            "advance_bdt": str(adv),
            "remaining_bdt": str(rem),
        },
        "eta": {"min_days": eta_min, "max_days": eta_max},
    }


def record_status(order: Order, status: str, note: str | None = None):
    order.status = status
    order.save(update_fields=["status"])
    OrderStatusHistory.objects.create(order=order, status=status, note=note)
    return order


def recommend_routes(variant_id: int, qty: int, delivery_type: str, priority: str = "balanced"):
    """
    Lightweight heuristic recommender (acts as AI layer for now):
    Evaluates each country + mode combo, calculates total cost and ETA,
    and ranks by weighted score (time vs cost).
    """
    priority = priority.lower()
    weights = {
        "fast": {"time": Decimal("0.7"), "cost": Decimal("0.3")},
        "cheap": {"time": Decimal("0.3"), "cost": Decimal("0.7")},
        "balanced": {"time": Decimal("0.5"), "cost": Decimal("0.5")},
    }.get(priority, {"time": Decimal("0.5"), "cost": Decimal("0.5")})

    routes = []
    countries = Country.objects.filter(code__in=["CN", "SG", "TH"])
    for country in countries:
        for mode in [Order.MODE_LOCAL, Order.MODE_BULK]:
            try:
                quote = generate_quote(variant_id, country.code, mode, qty, delivery_type)
                total = Decimal(quote["breakdown"]["total_bdt"])
                eta_max = Decimal(str(quote["eta"]["max_days"]))
                score = (weights["cost"] * total) + (weights["time"] * eta_max * Decimal("1000"))
                routes.append(
                    {
                        "country": country.code,
                        "mode": mode,
                        "total_bdt": str(total),
                        "eta": quote["eta"],
                        "selected_offer_id": quote["selected_offer_id"],
                        "score": str(score),
                        "offers_top": quote["offers_top"],
                    }
                )
            except Exception:
                # skip routes with missing data
                continue

    routes_sorted = sorted(routes, key=lambda r: Decimal(r["score"]))
    return routes_sorted
