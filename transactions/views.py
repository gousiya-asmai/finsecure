# transactions/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Sum, Q, Count
from django.db.models.functions import TruncDate
from datetime import timedelta
from django.views.generic.edit import CreateView
from django.views.generic import ListView
from django.urls import reverse_lazy
import json

from .forms import TransactionForm
from .models import Transaction
from .ml_utils import predict_fraud


# ✅ Add Transaction
@login_required
def add_transaction(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user

            # Ensure timestamp
            if not transaction.timestamp:
                transaction.timestamp = timezone.now()

            transaction.save()

            # Fraud prediction
            try:
                input_data = {
                    'amount': float(transaction.amount),
                    'category': transaction.category.lower() if transaction.category else 'uncategorized',
                    'transaction_type': transaction.transaction_type.lower() if transaction.transaction_type else 'uncategorized',
                }
                prediction = predict_fraud(input_data)
                transaction.is_fraud = prediction.get('is_fraud', False)
                transaction.fraud_probability = prediction.get('probability', 0.0)
                transaction.save()
            except Exception as e:
                print("⚠️ Fraud prediction error:", e)

            # Fraud email alert
            if transaction.is_fraud:
                try:
                    subject = 'ALERT: Fraudulent Transaction Detected on Your Account'
                    message = f'''Dear {transaction.user.get_full_name() or transaction.user.username},

We have detected a potentially fraudulent transaction with the following details:

Amount: {transaction.amount}
Category: {transaction.category}
Transaction Type: {transaction.transaction_type}
Date: {transaction.timestamp.strftime("%Y-%m-%d %H:%M:%S")}

If you did not authorize this transaction, please contact our support team immediately.

Regards,
Your Bank Security Team
'''
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [transaction.user.email],
                        fail_silently=True
                    )
                except Exception as e:
                    print("⚠️ Failed to send fraud email:", e)

            # AJAX request → return JSON
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": True})

            return redirect('dashboard')

        else:
            # Invalid form case for AJAX
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "errors": form.errors}, status=400)

    else:
        form = TransactionForm()

    return render(request, 'transactions/add_transaction.html', {'form': form})


# ✅ Fraud Prediction API
@csrf_exempt
def predict_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            result = predict_fraud(data)
            return JsonResponse(result)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'POST requests only'}, status=405)


# ✅ Transaction List
@login_required
def list_transactions(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'transactions/list_transactions.html', {'transactions': transactions})


# ✅ Dashboard Data API
@login_required
def dashboard_data(request):
    """
    Returns JSON for frontend AJAX with:
    - income, spending, savings
    - alerts, suggestions
    - transactions (latest 10, excluding frauds)
    - chart datasets for 7d, 30d, all-time
    """
    user = request.user
    qs = Transaction.objects.filter(user=user)
    now = timezone.now()

    # Aggregations (all-time totals)
    income = float(qs.filter(transaction_type__iexact="credit").aggregate(total=Sum("amount"))["total"] or 0)
    spending = float(qs.filter(transaction_type__iexact="debit").aggregate(total=Sum("amount"))["total"] or 0)
    savings = income - spending

    # Alerts
    alerts = []
    if income > 0 and spending > 0.7 * income:
        alerts.append("High spending: over 70% of your income.")
    fraud_count = qs.filter(is_fraud=True).count()
    if fraud_count:
        alerts.append(f"{fraud_count} fraud transactions detected!")
    if savings < 0:
        alerts.append("Overspending: savings are negative.")

    # Suggestions
    suggestions = []
    if spending > income:
        suggestions.append("Reduce expenses to improve savings.")
    if income > 0 and spending > 0.8 * income:
        suggestions.append("Spending is above 80% of income — cut down on variable costs.")
    if income > 0 and savings < 0.2 * income:
        suggestions.append("Increase savings — consider stricter budgeting.")
    if (qs.filter(category__iexact="entertainment").aggregate(total=Sum("amount"))["total"] or 0) > 0.3 * spending:
        suggestions.append("High entertainment spending — reduce non-essential costs.")
    if income > 0 and spending < 0.5 * income:
        suggestions.append("Great job keeping spending under control!")
    if savings > 0.5 * income:
        suggestions.append("Strong savings — consider investing for growth.")
    if income == 0:
        suggestions.append("No income recorded. Add income transactions to track savings.")

    # ✅ Helper: get continuous chart data
    def get_chart_data(qs_filter, days=None):
        # Aggregate actual data
        daily = (
            qs_filter.annotate(day=TruncDate('timestamp'))
            .values('day')
            .annotate(
                spending=Sum('amount', filter=Q(transaction_type__iexact='debit')),
                fraud_amount=Sum('amount', filter=Q(is_fraud=True)),
                fraud_count=Count('id', filter=Q(is_fraud=True)),
            )
        )
        daily_map = {d['day']: d for d in daily}

        # Build continuous date range
        if days:
            start_date = (now - timedelta(days=days - 1)).date()
        else:
            start_date = qs_filter.order_by('timestamp').first().timestamp.date() if qs_filter.exists() else now.date()
        end_date = now.date()

        labels, spending_arr, fraud_amount_arr, fraud_count_arr = [], [], [], []

        current = start_date
        while current <= end_date:
            labels.append(current.strftime("%Y-%m-%d"))
            record = daily_map.get(current, {})
            spending_arr.append(float(record.get('spending') or 0))
            fraud_amount_arr.append(float(record.get('fraud_amount') or 0))
            fraud_count_arr.append(int(record.get('fraud_count') or 0))
            current += timedelta(days=1)

        return labels, spending_arr, fraud_amount_arr, fraud_count_arr

    # Chart datasets
    labels_all, spending_all, fraud_all_amount, fraud_all_count = get_chart_data(qs)
    labels_7d, spending_7d, fraud_7d_amount, fraud_7d_count = get_chart_data(qs.filter(timestamp__gte=now - timedelta(days=7)), days=7)
    labels_30d, spending_30d, fraud_30d_amount, fraud_30d_count = get_chart_data(qs.filter(timestamp__gte=now - timedelta(days=30)), days=30)

    # ✅ Recent transactions (exclude frauds)
    latest = qs.filter(is_fraud=False).order_by('-timestamp')[:10]
    transactions_list = [
        {
            "description": getattr(t, "description", "") or getattr(t, "category", ""),
            "amount": float(t.amount),
            "timestamp": t.timestamp.strftime("%Y-%m-%d %H:%M") if t.timestamp else "",
        }
        for t in latest
    ]

    return JsonResponse({
        "income": income,
        "spending": spending,
        "savings": savings,
        "alerts": alerts,
        "suggestions": suggestions,
        "transactions": transactions_list,

        # Chart data
        "labels_all": labels_all,
        "spending_all": spending_all,
        "fraud_all_amount": fraud_all_amount,
        "fraud_all_count": fraud_all_count,

        "labels_7d": labels_7d,
        "spending_7d": spending_7d,
        "fraud_7d_amount": fraud_7d_amount,
        "fraud_7d_count": fraud_7d_count,

        "labels_30d": labels_30d,
        "spending_30d": spending_30d,
        "fraud_30d_amount": fraud_30d_amount,
        "fraud_30d_count": fraud_30d_count,
    })


# ✅ Class-based Views
class TransactionCreateView(CreateView):
    model = Transaction
    fields = ['amount', 'description', 'transaction_type', 'timestamp']
    template_name = 'transactions/transaction_form.html'
    success_url = reverse_lazy('transactions:list')


class TransactionListView(ListView):
    model = Transaction
    template_name = 'transactions/list_transactions.html'
