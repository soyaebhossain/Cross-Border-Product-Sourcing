from rest_framework import serializers
from .models import Category, Product, ProductVariant

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]

class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = ["id", "sku", "variant_name", "weight_kg", "length_cm", "width_cm", "height_cm"]

class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer()
    variants = ProductVariantSerializer(many=True)
    default_variant_id = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "model", "category", "description", "image", "variants", "default_variant_id"]

    def get_default_variant_id(self, obj):
        first = obj.variants.first()
        return first.id if first else None
