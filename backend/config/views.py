from datetime import date, timedelta
from decimal import Decimal
from django.template.response import TemplateResponse
from django.db import models
from orders.models import Order, ManualPaymentProof, OrderItem
from catalog.models import Product


def admin_dashboard(request):
    """
    Admin dashboard driven by live data (simple aggregates).
    """
    total_orders = Order.objects.count()
    total_products = Product.objects.count()
    total_revenue = Order.objects.aggregate(total=models.Sum("total_bdt"))["total"] or Decimal("0.0")
    shipping_sum = Order.objects.aggregate(total=models.Sum("shipping_bdt"))["total"] or Decimal("0.0")

    manual_ids = ManualPaymentProof.objects.values_list("order_id", flat=True)
    manual_orders_count = Order.objects.filter(id__in=manual_ids).count()
    website_orders_count = max(total_orders - manual_orders_count, 0)

    # Daily revenue last 10 days
    daily_rows = []
    today = date.today()
    for i in range(10):
        d = today - timedelta(days=i)
        qs_day = Order.objects.filter(created_at__date=d)
        all_sum = qs_day.aggregate(s=models.Sum("total_bdt"))["s"] or Decimal("0.0")
        manual_sum = qs_day.filter(id__in=manual_ids).aggregate(s=models.Sum("total_bdt"))["s"] or Decimal("0.0")
        web_sum = all_sum - manual_sum
        daily_rows.append({
            "sl": i + 1,
            "date": d.isoformat(),
            "all": f"{all_sum:.2f}",
            "manual": f"{manual_sum:.2f}",
            "web": f"{web_sum:.2f}",
        })

    # Top products by quantity sold (no price stored, so showing counts)
    top_items = (
        OrderItem.objects
        .values("variant__product__name")
        .annotate(total_qty=models.Sum("qty"))
        .order_by("-total_qty")[:8]
    )
    items = [
        {"name": r["variant__product__name"] or "Product", "rev": f"{r['total_qty']} sold", "sold": r["total_qty"]}
        for r in top_items
    ]

    # Stages with percentages and colors
    stage_colors = ["#3b82f6", "#10b981", "#f59e0b", "#6366f1"]
    raw_stages = [
        Order.STATUS_PENDING,
        Order.STATUS_CONFIRMED,
        Order.STATUS_IN_TRANSIT,
        Order.STATUS_DELIVERED,
    ]
    stage_counts = [Order.objects.filter(status=lbl).count() for lbl in raw_stages]
    total_stage = sum(stage_counts) or 1
    stages = []
    for idx, lbl in enumerate(raw_stages):
        count = stage_counts[idx]
        pct = round((count / total_stage) * 100, 1)
        stages.append(
            {
                "label": lbl.replace("_", " ").title(),
                "count": count,
                "pct": pct,
                "color": stage_colors[idx % len(stage_colors)],
            }
        )

    # Delivery types with percentages
    delivery = []
    orders_total = total_orders or 1
    products_total = OrderItem.objects.aggregate(s=models.Sum("qty"))["s"] or 1
    for lbl, val in Order.DELIVERY_CHOICES:
        orders_ct = Order.objects.filter(delivery_type=val).count()
        products_ct = OrderItem.objects.filter(order__delivery_type=val).aggregate(s=models.Sum("qty"))["s"] or 0
        delivery.append(
            {
                "label": lbl.title(),
                "orders": orders_ct,
                "orders_pct": round((orders_ct / orders_total) * 100, 1),
                "products": products_ct,
                "products_pct": round((products_ct / products_total) * 100, 1),
                "color": "#3b82f6" if val == Order.DELIVERY_DOOR else "#10b981",
            }
        )

    # Countries as "districts" (since no district data)
    districts = []
    countries = Order.objects.values("country__name").annotate(c=models.Count("id")).order_by("-c")[:5]
    for c in countries:
        districts.append({"name": c["country__name"], "orders": c["c"], "products": "", "opts": ""})

    context = {
        "kpis": [
            {"label": "Total Orders", "value": f"{total_orders:,}", "sub": "Updated just now", "icon": "🛍️"},
            {"label": "Total Products", "value": f"{total_products:,}", "sub": "Updated just now", "icon": "📦"},
            {"label": "Total Revenue", "value": f"BDT {total_revenue:,.0f}", "sub": "Including delivery charges", "icon": "💰"},
            {"label": "Shipping Charge", "value": f"BDT {shipping_sum:,.0f}", "sub": "From orders.shipping_bdt", "icon": "🚚"},
        ],
        "daily_rows": daily_rows,
        "items": items,
        "stages": stages,
        "delivery": delivery,
        "types": [
            {"label": "Manual Orders", "count": manual_orders_count, "pct": round((manual_orders_count / total_orders) * 100, 1) if total_orders else 0, "color": "#f59e0b"},
            {"label": "Website Orders", "count": website_orders_count, "pct": round((website_orders_count / total_orders) * 100, 1) if total_orders else 0, "color": "#3b82f6"},
        ],
        "districts": districts,
    }
    return TemplateResponse(request, "admin/dashboard.html", context)
