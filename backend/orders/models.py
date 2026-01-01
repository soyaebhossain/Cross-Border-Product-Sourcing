from django.db import models
from django.conf import settings
from catalog.models import ProductVariant
from sourcing.models import Country, Seller, SellerOffer


class Order(models.Model):
    STATUS_PENDING = "PENDING"      # created, waiting payment verify
    STATUS_CONFIRMED = "CONFIRMED"  # advance ok
    STATUS_PURCHASED = "PURCHASED"
    STATUS_IN_TRANSIT = "IN_TRANSIT"
    STATUS_CUSTOMS = "CUSTOMS"
    STATUS_LOCAL_DISPATCH = "LOCAL_DISPATCH"
    STATUS_DELIVERED = "DELIVERED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PURCHASED, "Purchased"),
        (STATUS_IN_TRANSIT, "In Transit"),
        (STATUS_CUSTOMS, "Customs"),
        (STATUS_LOCAL_DISPATCH, "Local Dispatch"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    MODE_LOCAL = "LOCAL"
    MODE_BULK = "BULK"
    MODE_CHOICES = [(MODE_LOCAL, "Local"), (MODE_BULK, "Bulk")]

    DELIVERY_DOOR = "DOOR"
    DELIVERY_PICKUP = "PICKUP"
    DELIVERY_CHOICES = [(DELIVERY_DOOR, "Door"), (DELIVERY_PICKUP, "Pickup")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    country = models.ForeignKey(Country, on_delete=models.PROTECT)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    delivery_type = models.CharField(max_length=10, choices=DELIVERY_CHOICES)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    total_bdt = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    shipping_bdt = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    advance_bdt = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    remaining_bdt = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT)
    qty = models.IntegerField(default=1)
    offer = models.ForeignKey(SellerOffer, on_delete=models.PROTECT, null=True, blank=True)

class ManualPaymentProof(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="manual_payment", null=True, blank=True)
    channel = models.CharField(max_length=20, default="bKash")  # bKash/Nagad/Rocket
    trx_id = models.CharField(max_length=80)
    screenshot_url = models.URLField(blank=True, null=True)  # later: upload system
    verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)

class PaymentIntent(models.Model):
    CHANNEL_BKASH = "bKash"
    CHANNEL_SSL = "SSLCommerz"

    STATUS_CREATED = "CREATED"
    STATUS_PENDING = "PENDING"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payment_intents")
    channel = models.CharField(max_length=20, default=CHANNEL_SSL)
    amount_bdt = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CREATED)
    gateway_payment_id = models.CharField(max_length=120, blank=True, null=True)
    gateway_session = models.CharField(max_length=120, blank=True, null=True)
    payload = models.JSONField(blank=True, null=True)  # store gateway response
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="history")
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SavedQuote(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_quotes")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT)
    country = models.ForeignKey(Country, on_delete=models.PROTECT)
    mode = models.CharField(max_length=10, choices=Order.MODE_CHOICES)
    delivery_type = models.CharField(max_length=10, choices=Order.DELIVERY_CHOICES)
    qty = models.IntegerField(default=1)
    response = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
