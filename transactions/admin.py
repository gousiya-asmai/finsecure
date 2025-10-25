# transactions/admin.py
from django.contrib import admin
from .models import Transaction

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'category', 'transaction_type', 'timestamp', 'is_fraud')
    list_filter = ('is_fraud', 'transaction_type', 'category')
    search_fields = ('user__username',)
    ordering = ('-timestamp',)
