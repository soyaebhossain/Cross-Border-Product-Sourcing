from django.urls import path
from .views import (
    QuoteView,
    MyOrdersView,
    OrderDetailView,
    CreateOrderWithManualAdvanceView,
    OrderStatusUpdateView,
    QuoteRecommendationView,
    SavedQuoteListView,
    SaveQuoteView,
    CreatePaymentIntentView,
    PaymentWebhookView,
)

urlpatterns = [
    path("quote/", QuoteView.as_view()),
    path("quote/recommend/", QuoteRecommendationView.as_view()),
    path("quote/save/", SaveQuoteView.as_view()),
    path("quote/saved/", SavedQuoteListView.as_view()),
    path("orders/me/", MyOrdersView.as_view()),
    path("orders/<int:pk>/", OrderDetailView.as_view()),
    path("orders/create-manual/", CreateOrderWithManualAdvanceView.as_view()),
    path("orders/<int:pk>/status/", OrderStatusUpdateView.as_view()),
    path("payments/intent/", CreatePaymentIntentView.as_view()),
    path("payments/webhook/<str:channel>/", PaymentWebhookView.as_view()),
]
