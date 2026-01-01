from rest_framework import serializers
from .models import Order, OrderItem, ManualPaymentProof, OrderStatusHistory, SavedQuote, PaymentIntent
from logistics.models import Shipment, ShipmentEvent
from catalog.models import ProductVariant


class QuoteRequestSerializer(serializers.Serializer):
    variant_id = serializers.IntegerField()
    country = serializers.CharField(max_length=2)     # CN/SG/TH
    mode = serializers.ChoiceField(choices=["LOCAL", "BULK"])
    qty = serializers.IntegerField(min_value=1)
    delivery_type = serializers.ChoiceField(choices=["DOOR", "PICKUP"])


class OrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    variant_name = serializers.SerializerMethodField()

    def get_product_name(self, obj):
        return obj.variant.product.name if obj.variant and obj.variant.product else None

    def get_variant_name(self, obj):
        if not obj.variant:
            return None
        return obj.variant.variant_name or obj.variant.sku

    class Meta:
        model = OrderItem
        fields = ["variant_id", "product_name", "variant_name", "qty", "offer_id"]


class ManualPaymentProofSerializer(serializers.ModelSerializer):
    class Meta:
        model = ManualPaymentProof
        fields = ["channel", "trx_id", "screenshot_url", "verified", "verified_at"]


class ShipmentEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShipmentEvent
        fields = ["status", "note", "created_at"]


class ShipmentSerializer(serializers.ModelSerializer):
    events = ShipmentEventSerializer(many=True)

    class Meta:
        model = Shipment
        fields = ["tracking_number", "events"]


class OrderStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ["status", "note", "created_at"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    manual_payment = ManualPaymentProofSerializer(read_only=True)
    shipment = ShipmentSerializer(read_only=True)
    history = OrderStatusHistorySerializer(many=True)
    payment_intents = serializers.SerializerMethodField()

    def get_payment_intents(self, obj):
        qs = getattr(obj, "payment_intents", None)
        if not qs:
            return []
        return [
            {
                "id": p.id,
                "channel": p.channel,
                "amount_bdt": p.amount_bdt,
                "status": p.status,
                "gateway_payment_id": p.gateway_payment_id,
            }
            for p in qs.order_by("-created_at")[:5]
        ]

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "country_id",
            "mode",
            "delivery_type",
            "total_bdt",
            "advance_bdt",
            "remaining_bdt",
            "items",
            "manual_payment",
            "shipment",
            "history",
            "payment_intents",
            "created_at",
        ]


class SavedQuoteSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()
    variant_name = serializers.SerializerMethodField()

    def get_product_name(self, obj):
        return obj.variant.product.name if obj.variant and obj.variant.product else None

    def get_variant_name(self, obj):
        return obj.variant.variant_name or obj.variant.sku if obj.variant else None

    class Meta:
        model = SavedQuote
        fields = [
            "id",
            "variant_id",
            "product_name",
            "variant_name",
            "country_id",
            "mode",
            "delivery_type",
            "qty",
            "response",
            "created_at",
        ]
