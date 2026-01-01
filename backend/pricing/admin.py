from django.contrib import admin
from .models import CurrencyRate, ServiceFeeRule


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = ("currency", "rate_to_bdt", "updated_at")
    search_fields = ("currency",)


@admin.register(ServiceFeeRule)
class ServiceFeeRuleAdmin(admin.ModelAdmin):
    list_display = ("mode", "fee_bdt", "percent")
    list_filter = ("mode",)
