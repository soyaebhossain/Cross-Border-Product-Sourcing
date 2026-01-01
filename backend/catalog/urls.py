from django.urls import path
from .views import ProductListView, ProductBySlugView, CategoryListView

urlpatterns = [
    path("categories/", CategoryListView.as_view()),
    path("products/", ProductListView.as_view()),
    path("products/<slug:slug>/", ProductBySlugView.as_view()),
]
