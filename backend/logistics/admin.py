from django.contrib import admin
from .models import Shipment, ShipmentEvent


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("order", "tracking_number")
    search_fields = ("order__id", "tracking_number")


@admin.register(ShipmentEvent)
class ShipmentEventAdmin(admin.ModelAdmin):
    list_display = ("shipment", "status", "note", "created_at")
    list_filter = ("status",)
    search_fields = ("shipment__order__id", "note")
