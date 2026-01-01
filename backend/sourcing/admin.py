from django.contrib import admin
from .models import Country, Seller, SellerOffer


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "rating")
    search_fields = ("name", "country__name", "country__code")
    list_filter = ("country",)


@admin.register(SellerOffer)
class SellerOfferAdmin(admin.ModelAdmin):
    list_display = ("variant", "country", "seller", "mode", "price_origin", "currency", "stock", "moq")
    search_fields = ("variant__product__name", "seller__name", "currency")
    list_filter = ("country", "mode", "currency")
