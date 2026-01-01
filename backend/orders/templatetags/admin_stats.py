from django import template
from django.db.models import Count
from orders.models import Order, SavedQuote
from catalog.models import Product
from sourcing.models import SellerOffer

register = template.Library()


@register.inclusion_tag("admin/_stats_panel.html", takes_context=False)
def admin_stats_panel():
    orders_total = Order.objects.count()
    orders_pending = Order.objects.filter(status=Order.STATUS_PENDING).count()
    orders_in_transit = Order.objects.filter(status=Order.STATUS_IN_TRANSIT).count()
    saved_quotes = SavedQuote.objects.count()
    products = Product.objects.count()
    offers = SellerOffer.objects.count()

    return {
        "orders_total": orders_total,
        "orders_pending": orders_pending,
        "orders_in_transit": orders_in_transit,
        "saved_quotes": saved_quotes,
        "products": products,
        "offers": offers,
    }
