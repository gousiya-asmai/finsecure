# transactions/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
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
import logging

from .forms import TransactionForm
from .models import Transaction
from .ml_utils import predict_fraud
from .utils import send_fraud_alert_email

logger = logging.getLogger(__name__)

@login_required
def add_transaction(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.user = request.user

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
                logger.info(f"✅ Fraud prediction completed for transaction {transaction.id}: is_fraud={transaction.is_fraud}, probability={transaction.fraud_probability}")
            except Exception as e:
                logger.error(f"⚠️ Fraud prediction error for transaction {transaction.id}: {str(e)}", exc_info=True)

            # Improved Fraud email alert with logging and user feedback
            if transaction.is_fraud:
                try:
                    logger.warning(f"🚨 FRAUD DETECTED for transaction {transaction.id} - Sending email alert")
                    transaction_info = f"""
Amount:         ₹{transaction.amount:,.2f}
Category:       {transaction.category or 'N/A'}
Type:           {transaction.transaction_type}
Date:           {transaction.timestamp.strftime('%B %d, %Y at %I:%M %p')}
Description:    {transaction.description or 'N/A'}
Transaction ID: #{transaction.id}
Fraud Score:    {transaction.fraud_probability * 100:.1f}%
"""
                    send_fraud_alert_email(
                        user_email=transaction.user.email,
                        transaction_info=transaction_info,
                        user_name=transaction.user.get_full_name() or transaction.user.username
                    )
                    logger.info(f"✅ Fraud alert email triggered for {transaction.user.email}")
                    messages.warning(
                        request, f'⚠️ FRAUD ALERT: Suspicious transaction detected! A security alert has been sent to {transaction.user.email}'
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to send fraud email for transaction {transaction.id}: {str(e)}", exc_info=True)
                    messages.error(request, '⚠️ Fraud detected but email notification failed. Please check your email settings.')
            else:
                messages.success(request, '✅ Transaction added successfully!')
                logger.info(f"✅ Transaction {transaction.id} added (not fraud)")

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "success": True,
                    "is_fraud": transaction.is_fraud,
                    "fraud_probability": transaction.fraud_probability
                })
            return redirect('dashboard')

        else:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"success": False, "errors": form.errors}, status=400)
            messages.error(request, 'Please correct the errors in the form.')
    else:
        form = TransactionForm()
    return render(request, 'transactions/add_transaction.html', {'form': form})

@login_required
def test_fraud_email(request):
    """Test fraud email functionality"""
    try:
        test_transaction_info = f"""
Amount:         ₹25,000.00
Category:       Shopping
Type:           Debit
Date:           {timezone.now().strftime('%B %d, %Y at %I:%M %p')}
Description:    TEST - Suspicious online purchase
Transaction ID: #TEST-{timezone.now().timestamp()}
Fraud Score:    95.3%
"""
        send_fraud_alert_email(
            user_email=request.user.email,
            transaction_info=test_transaction_info,
            user_name=request.user.username
        )
        logger.info(f"✅ Test fraud email sent to {request.user.email}")
        messages.success(request, f'✅ Test fraud email sent to {request.user.email}! Check your inbox and spam folder.')
        return redirect('dashboard')
    except Exception as e:
        logger.error(f"❌ Test fraud email failed: {str(e)}", exc_info=True)
        messages.error(request, f'❌ Test email failed: {str(e)}')
        return redirect('dashboard')

@csrf_exempt
def predict_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            result = predict_fraud(data)
            return JsonResponse(result)
        except Exception as e:
            logger.error(f"Prediction API error: {str(e)}")
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'POST requests only'}, status=405)

@login_required
def list_transactions(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'transactions/list_transactions.html', {'transactions': transactions})

@login_required
def dashboard_data(request):
    user = request.user
    qs = Transaction.objects.filter(user=user)
    now = timezone.now()

    income = float(qs.filter(transaction_type__iexact="credit").aggregate(total=Sum("amount"))["total"] or 0)
    spending = float(qs.filter(transaction_type__iexact="debit").aggregate(total=Sum("amount"))["total"] or 0)
    savings = income - spending

    alerts = []
    if income > 0 and spending > 0.7 * income:
        alerts.append("High spending: over 70% of your income.")
    fraud_count = qs.filter(is_fraud=True).count()
    if fraud_count:
        alerts.append(f"{fraud_count} fraud transactions detected!")
    if savings < 0:
        alerts.append("Overspending: savings are negative.")

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

    def get_chart_data(qs_filter, days=None):
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

    labels_all, spending_all, fraud_all_amount, fraud_all_count = get_chart_data(qs)
    labels_7d, spending_7d, fraud_7d_amount, fraud_7d_count = get_chart_data(qs.filter(timestamp__gte=now - timedelta(days=7)), days=7)
    labels_30d, spending_30d, fraud_30d_amount, fraud_30d_count = get_chart_data(qs.filter(timestamp__gte=now - timedelta(days=30)), days=30)
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

class TransactionCreateView(CreateView):
    model = Transaction
    fields = ['amount', 'description', 'transaction_type', 'timestamp']
    template_name = 'transactions/transaction_form.html'
    success_url = reverse_lazy('transactions:list')

class TransactionListView(ListView):
    model = Transaction
    template_name = 'transactions/list_transactions.html'
