from django.db import models
from sourcing.models import Country

class ShippingRateCard(models.Model):
    METHOD_AIR = "AIR"
    METHOD_SEA = "SEA"
    METHOD_CHOICES = [(METHOD_AIR, "Air"), (METHOD_SEA, "Sea")]

    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default=METHOD_AIR)

    min_kg = models.DecimalField(max_digits=8, decimal_places=3)
    max_kg = models.DecimalField(max_digits=8, decimal_places=3)
    cost_bdt = models.DecimalField(max_digits=12, decimal_places=2)

class ETARule(models.Model):
    MODE_LOCAL = "LOCAL"
    MODE_BULK = "BULK"
    MODE_CHOICES = [(MODE_LOCAL, "Local"), (MODE_BULK, "Bulk")]

    DELIVERY_DOOR = "DOOR"
    DELIVERY_PICKUP = "PICKUP"
    DELIVERY_CHOICES = [(DELIVERY_DOOR, "Door"), (DELIVERY_PICKUP, "Pickup")]

    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    delivery_type = models.CharField(max_length=10, choices=DELIVERY_CHOICES)

    min_days = models.IntegerField()
    max_days = models.IntegerField()
