from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, generics, status
from .serializers import QuoteRequestSerializer, OrderSerializer, SavedQuoteSerializer
from .services import generate_quote, record_status, recommend_routes
from .models import Order, OrderItem, ManualPaymentProof, SavedQuote, PaymentIntent
from sourcing.models import Country
from sourcing.models import SellerOffer
from logistics.models import Shipment, ShipmentEvent
from django.utils import timezone

class QuoteView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        ser = QuoteRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        out = generate_quote(
            variant_id=data["variant_id"],
            country_code=data["country"],
            mode=data["mode"],
            qty=data["qty"],
            delivery_type=data["delivery_type"],
        )
        return Response(out)

class MyOrdersView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related("items").order_by("-id")

class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer
    base_queryset = Order.objects.select_related("country").prefetch_related(
        "items__variant__product",
        "history",
        "shipment__events",
        "manual_payment",
    )

    def get_queryset(self):
        qs = self.base_queryset
        user = self.request.user
        if getattr(user, "role", None) in ["admin", "operator"]:
            return qs
        return qs.filter(user=user)

class CreateOrderWithManualAdvanceView(APIView):
    """
    Create order + store manual payment proof (advance).
    In MVP, we trust quote is done on frontend; later we will recalc server-side again.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payload = request.data

        variant_id = payload.get("variant_id")
        qty = int(payload.get("qty", 1))
        country_code = payload.get("country")
        mode = payload.get("mode")
        delivery_type = payload.get("delivery_type")
        offer_id = payload.get("offer_id")

        trx_id = payload.get("trx_id")
        channel = payload.get("channel", "bKash")
        screenshot_url = payload.get("screenshot_url")

        if not all([variant_id, country_code, mode, delivery_type, trx_id]):
            return Response({"detail": "Missing required fields"}, status=400)

        # Server recalculates totals (important)
        quote = generate_quote(variant_id, country_code, mode, qty, delivery_type)

        country = Country.objects.get(code=country_code.upper())
        order = Order.objects.create(
            user=request.user,
            country=country,
            mode=mode,
            delivery_type=delivery_type,
            status=Order.STATUS_PENDING,
            total_bdt=quote["breakdown"]["total_bdt"],
            shipping_bdt=quote["breakdown"].get("shipping_bdt", 0),
            advance_bdt=quote["breakdown"]["advance_bdt"],
            remaining_bdt=quote["breakdown"]["remaining_bdt"],
        )

        offer = SellerOffer.objects.filter(id=offer_id).first() if offer_id else None
        OrderItem.objects.create(order=order, variant_id=variant_id, qty=qty, offer=offer)

        ManualPaymentProof.objects.create(
            order=order,
            channel=channel,
            trx_id=trx_id,
            screenshot_url=screenshot_url,
            verified=False
        )

        record_status(order, Order.STATUS_PENDING, note="Order created, advance pending verification")
        Shipment.objects.get_or_create(order=order)

        return Response({"order_id": order.id, "status": order.status})


class OrderStatusUpdateView(APIView):
    """
    Admin/operator can move order through statuses and optionally attach shipment events.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if not request.user.role in ["admin", "operator"]:
            return Response({"detail": "Forbidden"}, status=403)

        new_status = request.data.get("status")
        note = request.data.get("note")
        tracking_number = request.data.get("tracking_number")
        shipment_note = request.data.get("shipment_note")

        valid_status = [c[0] for c in Order.STATUS_CHOICES]
        if new_status not in valid_status:
            return Response({"detail": "Invalid status"}, status=400)

        order = Order.objects.get(pk=pk)
        record_status(order, new_status, note=note)

        shipment, _ = Shipment.objects.get_or_create(order=order)
        if tracking_number:
            shipment.tracking_number = tracking_number
            shipment.save(update_fields=["tracking_number"])
        if shipment_note:
            ShipmentEvent.objects.create(shipment=shipment, status=new_status, note=shipment_note)

        return Response({"id": order.id, "status": order.status})


class QuoteRecommendationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        variant_id = request.data.get("variant_id")
        qty = int(request.data.get("qty", 1))
        delivery_type = request.data.get("delivery_type", Order.DELIVERY_DOOR)
        priority = request.data.get("priority", "balanced")

        if not variant_id:
            return Response({"detail": "variant_id required"}, status=400)

        routes = recommend_routes(variant_id, qty, delivery_type, priority)
        if not routes:
            return Response({"detail": "No routes available"}, status=404)
        return Response({"priority": priority, "routes": routes})


class SavedQuoteListView(generics.ListAPIView):
    serializer_class = SavedQuoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SavedQuote.objects.filter(user=self.request.user).select_related("variant__product").order_by("-created_at")


class SaveQuoteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        required = ["variant_id", "country", "mode", "qty", "delivery_type", "response"]
        if not all(k in request.data for k in required):
            return Response({"detail": "Missing required fields"}, status=400)

        sq = SavedQuote.objects.create(
            user=request.user,
            variant_id=request.data["variant_id"],
            country_id=request.data["country"],
            mode=request.data["mode"],
            qty=request.data["qty"],
            delivery_type=request.data["delivery_type"],
            response=request.data["response"],
        )
        return Response({"id": sq.id}, status=201)


class CreatePaymentIntentView(APIView):
    """
    Create a payment intent for advance payment. Channel-agnostic stub (plug SSL/bKash later).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        channel = request.data.get("channel", PaymentIntent.CHANNEL_SSL)
        amount_bdt = request.data.get("amount_bdt")

        if not all([order_id, amount_bdt]):
            return Response({"detail": "order_id and amount_bdt required"}, status=400)

        try:
            order = Order.objects.get(pk=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found"}, status=404)

        intent = PaymentIntent.objects.create(
            order=order,
            channel=channel,
            amount_bdt=amount_bdt,
            status=PaymentIntent.STATUS_CREATED,
        )

        # Placeholder gateway payload. Replace with real SSLCommerz/bKash session creation.
        gateway_payload = {
            "payment_url": "https://example.com/pay/" + str(intent.id),
            "session_key": f"stub-{intent.id}",
        }
        intent.payload = gateway_payload
        intent.gateway_session = gateway_payload["session_key"]
        intent.status = PaymentIntent.STATUS_PENDING
        intent.save(update_fields=["payload", "gateway_session", "status"])

        return Response(
            {
                "intent_id": intent.id,
                "payment_url": gateway_payload["payment_url"],
                "status": intent.status,
            },
            status=201,
        )


class PaymentWebhookView(APIView):
    """
    Receive gateway notification and mark intent/order paid.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request, channel):
        ref = request.data.get("ref") or request.data.get("payment_id")
        status_in = request.data.get("status", "").upper()
        amount = request.data.get("amount")
        order_id = request.data.get("order_id")

        # Match intent (stub: by order + last pending intent)
        intent = (
            PaymentIntent.objects.filter(order_id=order_id, status__in=[PaymentIntent.STATUS_PENDING, PaymentIntent.STATUS_CREATED])
            .order_by("-created_at")
            .first()
        )
        if not intent:
            return Response({"detail": "Intent not found"}, status=404)

        intent.gateway_payment_id = ref
        intent.payload = request.data

        if status_in in ["SUCCESS", "COMPLETED", "PAID"]:
            intent.status = PaymentIntent.STATUS_SUCCESS
            intent.save(update_fields=["gateway_payment_id", "payload", "status", "updated_at"])

            # Mark order advance paid
            order = intent.order
            order.status = Order.STATUS_CONFIRMED
            order.advance_bdt = amount or order.advance_bdt
            order.remaining_bdt = max(order.total_bdt - order.advance_bdt, 0)
            order.save(update_fields=["status", "advance_bdt", "remaining_bdt"])

            # record history
            record_status(order, Order.STATUS_CONFIRMED, note=f"Paid via {channel}")

            # mirror into ManualPaymentProof for now
            ManualPaymentProof.objects.update_or_create(
                order=order,
                defaults={
                    "channel": channel,
                    "trx_id": ref or f"{channel}-{intent.id}",
                    "verified": True,
                    "verified_at": timezone.now(),
                },
            )
        else:
            intent.status = PaymentIntent.STATUS_FAILED
            intent.save(update_fields=["gateway_payment_id", "payload", "status", "updated_at"])

        return Response({"status": intent.status})
