from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions"
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Transaction amount (in currency units)."
    )
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPES,
        help_text="Type of transaction: Credit (income) or Debit (expense)."
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Category like Food, Rent, Salary, etc."
    )
    is_fraud = models.BooleanField(
        default=False,
        help_text="Flagged by fraud detection logic."
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="When this transaction occurred."
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional transaction note or description."
    )

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"

    def __str__(self):
        fraud_tag = "⚠️" if self.is_fraud else "✅"
        return f"{fraud_tag} {self.user.username} - {self.transaction_type.title()} {self.amount} ({self.category or 'Uncategorized'})"
