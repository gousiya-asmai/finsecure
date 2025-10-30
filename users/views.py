# users/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Sum, Count
from django.http import JsonResponse
import random
import logging
# Models
from transactions.models import Transaction
from assistance.models import SmartSuggestion
from users.models import UserProfile
from django.shortcuts import render, redirect

from users.utils import fetch_latest_emails, fetch_recent_transactions, save_transactions_to_db
from users.otp_utils import send_otp_via_sendgrid


from django.conf import settings



# Utils (Removed gmail_authenticate)
from users.utils import (
    fetch_latest_emails,
    fetch_recent_transactions,
    save_transactions_to_db,
    get_gmail_profile,  # ✅ Make sure this returns Gmail account info (you can define it)
)

# Forms
from users.forms import UserUpdateForm, ProfileUpdateForm
from django.http import HttpResponse

# ------------------- Home -------------------
def home(request):
    return render(request, "users/home.html")


# ------------------- Signup -------------------
def signup_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            messages.error(request, "Passwords do not match ❌")
            return redirect("signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken ❌")
            return redirect("signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered ❌")
            return redirect("signup")

        try:
            user = User.objects.create_user(username=username, email=email, password=password1)
            UserProfile.objects.get_or_create(user=user, email=user.email, name=user.username)
            messages.success(request, "✅ Account created successfully. Please login.")
            return redirect("login")
        except Exception as e:
            messages.error(request, f"Error creating account: {str(e)}")
            return redirect("signup")

    return render(request, "users/signup.html")


# ------------------- Login (Username+Password or Email+OTP) -------------------
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        email = request.POST.get("email")

        # Username + password login
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                _check_profile_and_send_email(user)
                return redirect("dashboard")
            else:
                messages.error(request, "Incorrect username or password.")
                return redirect("login")

        # Email + OTP login
        elif email:
            user_qs = User.objects.filter(email=email)
            if user_qs.exists():
                user = user_qs.first()
                otp = random.randint(100000, 999999)
                request.session["otp"] = str(otp)
                request.session["user_id"] = user.id
                request.session["otp_expiry"] = (timezone.now() + timezone.timedelta(minutes=5)).isoformat()

                try:
                    response_code = send_otp_via_sendgrid(email, otp)
                    if response_code == 202:
                        messages.success(request, f"✅ OTP sent to {email}. Please verify.")
                    else:
                        messages.error(request, f"Failed to send OTP, status code: {response_code}")
                    return redirect("verify_otp")
                except Exception as e:
                    logging.error(f"OTP email send error: {e}", exc_info=True)
                    print(f"OTP email send error: {e}")
                    messages.error(request, f"Failed to send OTP: {str(e)}")
                    return redirect("login")
            else:
                messages.error(request, "❌ Email not registered")
                return redirect("login")

    return render(request, "users/login.html")
# ------------------- OTP Verification -------------------





def verify_otp_view(request):
    print("verify_otp_view called", request.method)  # Diagnostic print

    if request.method == "POST":
        input_otp = request.POST.get("otp")
        session_otp = request.session.get("otp")
        user_id = request.session.get("user_id")
        otp_expiry = request.session.get("otp_expiry")

        print("OTP Received:", input_otp)
        print("Session OTP:", session_otp)
        print("User ID:", user_id)
        print("OTP Expiry:", otp_expiry)

        if otp_expiry:
            otp_expiry_time = timezone.datetime.fromisoformat(otp_expiry)
            if timezone.now() > otp_expiry_time:
                messages.error(request, "⏳ OTP expired. Please request a new one.")
                return redirect("login")

        if session_otp and input_otp == session_otp:
            try:
                user = User.objects.get(id=user_id)
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                # Call this if profile/email notification needed
                # _check_profile_and_send_email(user)
                for k in ["otp", "user_id", "otp_expiry"]:
                    request.session.pop(k, None)
                print("OTP verified, redirecting to dashboard")
                return redirect("dashboard")
            except Exception as e:
                print("OTP verification error:", e)
                messages.error(request, "An error occurred. Please login again.")
                return redirect("login")

        messages.error(request, "❌ Invalid OTP. Try again.")
        return redirect("verify_otp")

    return render(request, "users/verify_otp.html")

# ------------------- Resend OTP -------------------
def resend_otp_view(request):
    user_id = request.session.get("user_id")
    if not user_id:
        messages.error(request, "Session expired. Please login again.")
        return redirect("login")

    try:
        user = User.objects.get(id=user_id)
        otp = random.randint(100000, 999999)
        request.session["otp"] = str(otp)
        request.session["otp_expiry"] = (timezone.now() + timezone.timedelta(minutes=5)).isoformat()

        send_mail(
            subject="Your Login OTP",
            message=f"Your OTP for login is: {otp}\n\n(Valid for 5 minutes)",
            from_email="finsecure7@gmail.com",
            recipient_list=[user.email],
            fail_silently=False,
        )
        messages.success(request, f"🔄 OTP resent to {user.email}. Please verify.")
    except User.DoesNotExist:
        messages.error(request, "User session expired. Please login again.")
        return redirect("login")

    return redirect("verify_otp")


# ------------------- Update Email -------------------
@login_required
def update_email_view(request):
    if request.method == "POST":
        new_email = request.POST.get("email")
        if new_email:
            request.user.email = new_email
            request.user.save()
            messages.success(request, "✅ Email updated successfully!")
            return redirect("profile")
        else:
            messages.error(request, "❌ Please provide a valid email.")
    return render(request, "users/update_email.html")


# ------------------- Dashboard -------------------


from decimal import Decimal
from django.db.models import Sum, Count
from django.utils import timezone
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect


from transactions.models import Transaction
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Sum, Count
from transactions.models import Transaction
from datetime import datetime, timedelta
from .models import UserProfile
from assistance.models import SmartSuggestion
from django.db import models



# ------------------- Dashboard Page -------------------

@login_required
def dashboard(request):
    user = request.user

    # Basic context for template
    transactions = Transaction.objects.filter(user=user)
    income = transactions.filter(type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    spending = transactions.filter(type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    savings = income - spending

    # Fraud stats (basic)
    fraud_stats = list(
        transactions.values('is_fraud')
        .annotate(count=Count('id'))
        .order_by('is_fraud')
    )

    context = {
        'income': income,
        'spending': spending,
        'savings': savings,
        'fraud_stats': fraud_stats,
    }
    return render(request, 'users/dashboard.html', context)


@login_required
def get_dashboard_data(request):
    user = request.user
    period = request.GET.get('period', 'all')

    today = datetime.today()
    if period == "7":
        start_date = today - timedelta(days=7)
    elif period == "30":
        start_date = today - timedelta(days=30)
    else:
        start_date = None

    # Filtered transactions
    txns = Transaction.objects.filter(user=user)
    if start_date:
        txns = txns.filter(date__gte=start_date)

    # Aggregate values
    income = txns.filter(type='income').aggregate(Sum('amount'))['amount__sum'] or 0
    spending = txns.filter(type='expense').aggregate(Sum('amount'))['amount__sum'] or 0
    savings = income - spending

    # Fraud detection
    fraud_txns = txns.filter(is_fraud=True)
    nonfraud_txns = txns.filter(is_fraud=False)

    # Group fraud amount by day for charts
    def fraud_amount_series(queryset, days):
        labels, values = [], []
        for i in range(days):
            day = today - timedelta(days=i)
            total = queryset.filter(date__date=day.date()).aggregate(Sum('amount'))['amount__sum'] or 0
            labels.append(day.strftime("%b %d"))
            values.append(float(total))
        labels.reverse()
        values.reverse()
        return labels, values

    # Fraud amount arrays for each period
    labels_7d, fraud_7d_amount = fraud_amount_series(fraud_txns, 7)
    labels_30d, fraud_30d_amount = fraud_amount_series(fraud_txns, 30)

    # All-time fraud data (category sum or by month)
    fraud_by_month = (
        fraud_txns
        .annotate(month=models.functions.TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
        .order_by('month')
    )
    labels_all = [d['month'].strftime("%b %Y") for d in fraud_by_month]
    fraud_all_amount = [float(d['total']) for d in fraud_by_month]

    # Fraud count summary
    fraud_stats = list(
        txns.values('is_fraud')
        .annotate(count=Count('id'))
        .order_by('is_fraud')
    )

    # Alerts
    alerts = []
    if spending > income * 0.8:
        alerts.append("High spending relative to income.")
    if fraud_txns.exists():
        alerts.append(f"{fraud_txns.count()} suspicious transactions detected.")

    # Category spending for fallback graph
    category_spending = list(
        txns.filter(type='expense')
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    data = {
        "income": float(income),
        "spending": float(spending),
        "savings": float(savings),
        "alerts": alerts,
        "fraud_stats": fraud_stats,
        "category_spending": category_spending,

        # Fraud amount chart data
        "labels_7d": labels_7d,
        "fraud_7d_amount": fraud_7d_amount,
        "labels_30d": labels_30d,
        "fraud_30d_amount": fraud_30d_amount,
        "labels_all": labels_all,
        "fraud_all_amount": fraud_all_amount,
    }

    return JsonResponse(data)

# ------------------- Connect Gmail -------------------
@login_required
def connect_gmail(request):
    """Fetch Gmail data using users.utils and capture Gmail account"""
    try:
        latest_emails = fetch_latest_emails(request.user, max_results=5)
        transactions = fetch_recent_transactions(request.user, max_results=10)

        # ✅ Optional: get Gmail profile (if your utils support it)
        try:
            gmail_profile = get_gmail_profile(request.user)
            connected_gmail = gmail_profile.get("emailAddress") if gmail_profile else None
        except Exception:
            connected_gmail = None

        if not connected_gmail and latest_emails:
            # Fallback: extract from emails
            first_email = latest_emails[0]
            connected_gmail = first_email.get("to") or first_email.get("from")

        if transactions:
            save_transactions_to_db(request.user, transactions)

        # ✅ Save to session
        request.session["gmail_connected"] = True
        request.session["latest_emails"] = latest_emails
        request.session["gmail_transactions"] = transactions
        request.session["connected_gmail"] = connected_gmail

        messages.success(request, "✅ Gmail connected and data fetched successfully!")
    except Exception as e:
        print("⚠️ Gmail connection error:", e)
        messages.error(request, f"Error connecting Gmail: {str(e)}")

    return redirect("dashboard")


# ------------------- Logout -------------------
@login_required
def logout_view(request):
    logout(request)
    messages.success(request, "✅ Logged out successfully.")
    return redirect("login")


# ------------------- Profile -------------------
@login_required
def profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={"email": request.user.email, "name": request.user.username},
    )

    if request.method == "POST":
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, "✅ Profile updated successfully!")
            return redirect("profile")
        else:
            messages.error(request, "❌ Please correct the errors below.")
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)

    return render(request, "users/profile.html", {"u_form": u_form, "p_form": p_form, "profile": profile})


# ------------------- Misc Pages -------------------
@login_required
def assistance_view(request):
    return redirect("assist_home")


@login_required
def fraud_check_view(request):
    return render(request, "fraud/fraud_check.html")


def fraud_alerts(request):
    return render(request, "users/fraud_alerts.html")


def reports(request):
    return render(request, "users/reports.html")


def settings(request):
    return render(request, "users/settings.html")


# ------------------- Helper -------------------
def _check_profile_and_send_email(user):
    try:
        profile = user.profile
        if not profile.is_complete():
            send_mail(
                subject="Complete Your Profile",
                message="Your profile is incomplete. Please update it.",
                from_email="noreply@financesystem.com",
                recipient_list=[user.email],
                fail_silently=True,
            )
    except UserProfile.DoesNotExist:
        pass




@login_required
def test_email_view(request):
    """Test email sending functionality"""
    try:
        result = send_mail(
            subject='🧪 Test Email from FinSecure',
            message='This is a test email to verify your SendGrid configuration is working correctly.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],  # Send to logged-in user
            fail_silently=False,
        )
        
        if result == 1:
            messages.success(request, f'✅ Test email sent successfully to {request.user.email}')
            return HttpResponse(f"✅ Email sent successfully to {request.user.email}! Check your inbox.")
        else:
            messages.error(request, '❌ Email sending failed - no exception but result was 0')
            return HttpResponse("❌ Email failed to send (result = 0)")
            
    except Exception as e:
        messages.error(request, f'❌ Email error: {str(e)}')
        return HttpResponse(f"❌ Email sending failed with error: {str(e)}")


@login_required
def test_messages_view(request):
    """Test Django messages functionality"""
    messages.success(request, '✅ Success message test!')
    messages.info(request, 'ℹ️ Info message test!')
    messages.warning(request, '⚠️ Warning message test!')
    messages.error(request, '❌ Error message test!')
    
    from django.shortcuts import redirect
    return redirect('dashboard')

from django.http import HttpResponse
from django.core.management import call_command

def run_temp_superuser(request):
    call_command('create_or_reset_superuser')  # your custom command
    return HttpResponse("Superuser created or reset. Delete this view after use.")
