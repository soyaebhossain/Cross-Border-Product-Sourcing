from django.contrib import admin
from .models import ShippingRateCard, ETARule


@admin.register(ShippingRateCard)
class ShippingRateCardAdmin(admin.ModelAdmin):
    list_display = ("country", "method", "min_kg", "max_kg", "cost_bdt")
    list_filter = ("country", "method")


@admin.register(ETARule)
class ETARuleAdmin(admin.ModelAdmin):
    list_display = ("country", "mode", "delivery_type", "min_days", "max_days")
    list_filter = ("country", "mode", "delivery_type")
