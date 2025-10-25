# transactions/forms.py

from django import forms
from .models import Transaction

class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['amount', 'category', 'transaction_type']
        exclude = ['is_fraud', 'fraud_probability', 'user', 'timestamp']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'category': forms.TextInput(attrs={'placeholder': 'e.g., payment'}),
            'transaction_type': forms.Select(choices=[('debit', 'Debit'), ('credit', 'Credit')]),
        }
