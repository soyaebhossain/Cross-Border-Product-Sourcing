from rest_framework import generics, permissions
from django.db.models import Q
from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer


class CategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer

    def get_queryset(self):
        return Category.objects.order_by("name")

class ProductListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer

    def get_queryset(self):
        q = self.request.query_params.get("q", "").strip()
        qs = Product.objects.select_related("category").prefetch_related("variants")
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(model__icontains=q)
                | Q(slug__icontains=q)
                | Q(category__slug__icontains=q)
                | Q(category__name__icontains=q)
            )
        return qs.order_by("name")

class ProductBySlugView(generics.RetrieveAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = ProductSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Product.objects.select_related("category").prefetch_related("variants")
