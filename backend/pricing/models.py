from django.db import models
from sourcing.models import Country

class CurrencyRate(models.Model):
    # 1 unit of currency => BDT
    currency = models.CharField(max_length=10, unique=True)  # USD, CNY, THB, SGD
    rate_to_bdt = models.DecimalField(max_digits=12, decimal_places=4)
    updated_at = models.DateTimeField(auto_now=True)

class ServiceFeeRule(models.Model):
    MODE_LOCAL = "LOCAL"
    MODE_BULK = "BULK"
    MODE_CHOICES = [(MODE_LOCAL, "Local"), (MODE_BULK, "Bulk")]

    mode = models.CharField(max_length=10, choices=MODE_CHOICES)
    fee_bdt = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    # optional: percent
    percent = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)
