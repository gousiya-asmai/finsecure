from django.db import models
from django.contrib.auth.models import User

class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=(('credit','Credit'),('debit','Debit')))
    category = models.CharField(max_length=50, blank=True, null=True)
    is_fraud = models.BooleanField(default=False)  # set by your fraud detection logic
    timestamp = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.user}: {self.amount} - {self.category} - Fraud: {self.is_fraud}"

