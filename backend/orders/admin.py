from django.contrib import admin
from .models import Order, OrderItem, ManualPaymentProof, OrderStatusHistory, SavedQuote


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "country", "mode", "delivery_type", "status", "total_bdt", "created_at")
    list_filter = ("status", "mode", "delivery_type", "country")
    search_fields = ("id", "user__username", "user__email", "user__phone")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "variant", "qty", "offer")
    list_filter = ("offer",)
    search_fields = ("order__id", "variant__product__name")


@admin.register(ManualPaymentProof)
class ManualPaymentProofAdmin(admin.ModelAdmin):
    list_display = ("order", "channel", "trx_id", "verified")
    list_filter = ("channel", "verified")
    search_fields = ("order__id", "trx_id")


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("order", "status", "note", "created_at")
    list_filter = ("status",)
    search_fields = ("order__id", "note")


@admin.register(SavedQuote)
class SavedQuoteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "variant", "country", "mode", "qty", "created_at")
    list_filter = ("country", "mode")
    search_fields = ("user__username", "user__email", "variant__product__name")
