from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    model = models.CharField(max_length=120, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=80, blank=True, null=True)
    variant_name = models.CharField(max_length=120, blank=True, null=True)

    weight_kg = models.DecimalField(max_digits=8, decimal_places=3, default=0.0)
    length_cm = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    width_cm  = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    height_cm = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)

    def __str__(self):
        return f"{self.product.name} - {self.variant_name or 'default'}"
