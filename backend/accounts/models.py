from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CUSTOMER = "customer"
    ROLE_B2B = "b2b"
    ROLE_ADMIN = "admin"
    ROLE_OPERATOR = "operator"

    ROLE_CHOICES = [
        (ROLE_CUSTOMER, "Customer"),
        (ROLE_B2B, "B2B"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_OPERATOR, "Operator"),
    ]

    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)

    # optional: require email unique
    email = models.EmailField(unique=True, null=True, blank=True)

    def roles_list(self):
        # frontend expects array
        return [self.role] if self.role else []
