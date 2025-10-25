from django.db import models
from users.models import UserProfile

class Transaction(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    amount = models.FloatField()
    transaction_type = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    is_fraud = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.name} - ₹{self.amount} - Fraud: {self.is_fraud}"


# Create your models here.
