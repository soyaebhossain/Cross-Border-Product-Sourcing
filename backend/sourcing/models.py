from django.db import models
from catalog.models import ProductVariant

class Country(models.Model):
    code = models.CharField(max_length=2, unique=True)  # CN, SG, TH
    name = models.CharField(max_length=80)

    def __str__(self):
        return self.name

class Seller(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="sellers")
    name = models.CharField(max_length=120)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    note = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.country.code})"

class SellerOffer(models.Model):
    MODE_LOCAL = "LOCAL"
    MODE_BULK = "BULK"
    MODE_CHOICES = [(MODE_LOCAL, "Local"), (MODE_BULK, "Bulk")]

    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="offers")
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name="offers")

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default=MODE_LOCAL)
    price_origin = models.DecimalField(max_digits=12, decimal_places=2)  # in origin currency
    currency = models.CharField(max_length=10, default="USD")

    stock = models.IntegerField(default=0)
    moq = models.IntegerField(default=1)  # bulk can have moq > 1
    valid_until = models.DateTimeField(blank=True, null=True)
    source_url = models.URLField(blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)
