from django.contrib import admin
from .models import Category, Product, ProductVariant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "model", "category")
    search_fields = ("name", "slug", "model")
    list_filter = ("category",)
    fields = ("name", "slug", "model", "category", "description", "image")


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ("product", "variant_name", "sku", "weight_kg")
    search_fields = ("variant_name", "sku", "product__name")
    list_filter = ("product",)
