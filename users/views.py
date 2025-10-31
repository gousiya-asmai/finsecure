# users/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.utils import timezone
from django.db.models import Sum, Count
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from decimal import Decimal
from datetime import timedelta
import random
import logging

# Models
from transactions.models import Transaction
from assistance.models import SmartSuggestion
from users.models import UserProfile

# Utils
from users.utils import (
    fetch_latest_emails,
    fetch_recent_transactions,
    save_transactions_to_db,
    get_gmail_profile,
)
from users.otp_utils import send_otp_via_sendgrid

# Forms
from users.forms import UserUpdateForm, ProfileUpdateForm


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
                request.session["otp_expiry"] = (timezone.now() + timedelta(minutes=5)).isoformat()

                try:
                    response_code = send_otp_via_sendgrid(email, otp)
                    if response_code == 202:
                        messages.success(request, f"✅ OTP sent to {email}. Please verify.")
                    else:
                        messages.error(request, f"Failed to send OTP, status code: {response_code}")
                    return redirect("verify_otp")
                except Exception as e:
                    logging.error(f"OTP email send error: {e}", exc_info=True)
                    messages.error(request, f"Failed to send OTP: {str(e)}")
                    return redirect("login")
            else:
                messages.error(request, "❌ Email not registered")
                return redirect("login")

    return render(request, "users/login.html")


# ------------------- OTP Verification -------------------
def verify_otp_view(request):
    logging.info("verify_otp_view called - method: %s", request.method)

    if request.method == "POST":
        input_otp = request.POST.get("otp")
        session_otp = request.session.get("otp")
        user_id = request.session.get("user_id")
        otp_expiry = request.session.get("otp_expiry")

        logging.info(f"OTP Received: {input_otp}, Session OTP: {session_otp}, User ID: {user_id}, OTP Expiry: {otp_expiry}")

        if otp_expiry:
            otp_expiry_time = timezone.datetime.fromisoformat(otp_expiry)
            if timezone.now() > otp_expiry_time:
                messages.error(request, "⏳ OTP expired. Please request a new one.")
                return redirect("login")

        if session_otp and input_otp == session_otp:
            try:
                user = User.objects.get(id=user_id)
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                # Clear OTP-related session data
                for k in ["otp", "user_id", "otp_expiry"]:
                    request.session.pop(k, None)

                messages.success(request, "✅ OTP verified successfully!")
                return redirect("dashboard")
            except Exception as e:
                logging.error("OTP verification error: %s", e, exc_info=True)
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


# =========================================================
# DASHBOARD VIEW (Shows Gmail + Transactions + Suggestions)
# =========================================================
@login_required(login_url="login")
def dashboard_view(request):
    """
    Display the user dashboard with Gmail + transaction data.
    This version ensures emails fetched via connect_gmail()
    or live API call are correctly displayed.
    """
    try:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        if not profile.is_complete():
            messages.warning(request, "⚠ Your profile is incomplete. Please update it.")

        # ---------------- Gmail data load ----------------
        # First check if Gmail data already exists in session
        latest_emails = request.session.get("latest_emails", [])
        gmail_transactions = request.session.get("gmail_transactions", [])
        connected_gmail = request.session.get("connected_gmail")

        # If not available, fetch fresh data
        if not latest_emails:
            try:
                latest_emails = fetch_latest_emails(request.user, max_results=5)
            except Exception as e:
                logging.warning(f"Gmail fetch error (emails): {e}")
                latest_emails = []

        if not gmail_transactions:
            try:
                gmail_transactions = fetch_recent_transactions(request.user, max_results=25)
                if gmail_transactions:
                    save_transactions_to_db(request.user, gmail_transactions)
            except Exception as e:
                logging.warning(f"Gmail fetch error (transactions): {e}")
                gmail_transactions = []

        gmail_connected = bool(latest_emails or gmail_transactions or connected_gmail)

        # ---------------- Smart Suggestions ----------------
        suggestions_qs = SmartSuggestion.objects.filter(user=request.user).order_by("-created_at")[:5]
        suggestions = [
            {
                "suggestion": s.suggestion_text,
                "is_alert": getattr(s, "is_alert", False),
                "created_at": s.created_at,
            }
            for s in suggestions_qs
        ]

        # ---------------- Context ----------------
        context = {
            "profile": profile,
            "income": profile.income or 0.0,
            "gmail_connected": gmail_connected,
            "connected_gmail": connected_gmail,
            "latest_emails": latest_emails,
            "gmail_transactions": gmail_transactions,
            "suggestions": suggestions,
        }

        return render(request, "users/dashboard.html", context)

    except Exception as e:
        logging.error(f"❌ Dashboard error: {e}", exc_info=True)
        messages.error(request, f"Something went wrong loading your dashboard: {str(e)}")
        return redirect("home")


# =========================================================
# AJAX DASHBOARD DATA (for charts)
# =========================================================
@login_required
def get_dashboard_data(request):
    """
    Returns transaction summary data (income, spending, savings, fraud stats)
    as JSON for the dashboard graphs.
    """
    user = request.user
    period = request.GET.get("period", "all")
    transactions = Transaction.objects.filter(user=user)

    # --- Filter by period ---
    if period == "7":
        start_date = timezone.now() - timezone.timedelta(days=7)
        transactions = transactions.filter(timestamp__gte=start_date)
    elif period == "30":
        start_date = timezone.now() - timezone.timedelta(days=30)
        transactions = transactions.filter(timestamp__gte=start_date)

    # --- Totals ---
    total_income = transactions.filter(transaction_type="credit").aggregate(Sum("amount"))["amount__sum"] or Decimal("0.0")
    total_spending = transactions.filter(transaction_type="debit").aggregate(Sum("amount"))["amount__sum"] or Decimal("0.0")
    savings = total_income - total_spending

    # --- Alerts ---
    alerts = []
    if total_income > 0 and total_spending > Decimal("0.7") * total_income:
        alerts.append("⚠ High spending: over 70% of your income.")
    if savings < 0:
        alerts.append("⚠ Overspending: negative savings.")
    fraud_count = transactions.filter(is_fraud=True).count()
    if fraud_count:
        alerts.append(f"⚠ {fraud_count} fraud transactions detected!")

    # --- Category Spending (bar chart) ---
    category_spending = list(
        transactions.filter(transaction_type="debit")
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    # --- Fraud Stats (count chart) ---
    fraud_stats = list(
        transactions.values("is_fraud")
        .annotate(count=Count("id"))
        .order_by("-is_fraud")
    )

    # --- Time-Series (line chart) ---
    now = timezone.now()
    labels_7d, spending_7d = [], []
    labels_30d, spending_30d = [], []
    labels_all, spending_all = [], []

    for days in [7, 30, 90]:
        start = now - timezone.timedelta(days=days)
        qs = transactions.filter(timestamp__gte=start)
        daily_data = (
            qs.filter(transaction_type="debit")
            .extra(select={"day": "date(timestamp)"})
            .values("day")
            .annotate(total=Sum("amount"))
            .order_by("day")
        )

        labels_list = [d["day"].strftime("%b %d") for d in daily_data]
        values_list = [float(d["total"]) for d in daily_data]

        if days == 7:
            labels_7d, spending_7d = labels_list, values_list
        elif days == 30:
            labels_30d, spending_30d = labels_list, values_list
        else:
            labels_all, spending_all = labels_list, values_list

    # --- Fraud amount over time (line chart) ---
    fraud_qs = transactions.filter(is_fraud=True)
    fraud_daily = (
        fraud_qs.extra(select={"day": "date(timestamp)"})
        .values("day")
        .annotate(total=Sum("amount"))
        .order_by("day")
    )
    fraud_labels = [d["day"].strftime("%b %d") for d in fraud_daily]
    fraud_amount = [float(d["total"]) for d in fraud_daily]

    # --- Return JSON ---
    return JsonResponse({
        "income": float(total_income),
        "spending": float(total_spending),
        "savings": float(savings),
        "alerts": alerts,
        "category_spending": category_spending,
        "fraud_stats": fraud_stats,
        "labels_7d": labels_7d,
        "spending_7d": spending_7d,
        "labels_30d": labels_30d,
        "spending_30d": spending_30d,
        "labels_all": labels_all,
        "spending_all": spending_all,
        "fraud_labels": fraud_labels,
        "fraud_7d_amount": fraud_amount,
    })



# ------------------- Gmail Connection -------------------

@login_required
def connect_gmail(request):
    """Fetch Gmail data and ensure they appear on dashboard."""
    try:
        from users.utils import (
            fetch_latest_emails,
            fetch_recent_transactions,
            save_transactions_to_db,
            get_gmail_profile,
        )

        # Fetch Gmail data
        latest_emails = fetch_latest_emails(request.user, max_results=5)
        transactions = fetch_recent_transactions(request.user, max_results=10)

        # ✅ Get connected Gmail address (if available)
        connected_gmail = None
        try:
            gmail_profile = get_gmail_profile(request.user)
            connected_gmail = gmail_profile.get("emailAddress") if gmail_profile else None
        except Exception:
            pass

        # If profile fetch failed, fallback to extracting from first email
        if not connected_gmail and latest_emails:
            first_email = latest_emails[0]
            connected_gmail = first_email.get("to") or first_email.get("from")

        # ✅ Save transactions to DB
        if transactions:
            save_transactions_to_db(request.user, transactions)

        # ✅ Cache results to session (for dashboard fallback)
        request.session["gmail_connected"] = True
        request.session["latest_emails"] = latest_emails
        request.session["gmail_transactions"] = transactions
        request.session["connected_gmail"] = connected_gmail

        messages.success(request, "✅ Gmail connected and data fetched successfully!")

    except Exception as e:
        print("⚠ Gmail connection error:", e)
        messages.error(request, f"Error connecting Gmail: {str(e)}")

    return redirect("dashboard")


# ------------------- Dashboard Helper -------------------

def _get_cached_gmail_data(request):
    """Return Gmail data either from session cache or empty fallback."""
    return {
        "latest_emails": request.session.get("latest_emails", []),
        "gmail_transactions": request.session.get("gmail_transactions", []),
        "gmail_connected": request.session.get("gmail_connected", False),
        "connected_gmail": request.session.get("connected_gmail", None),
    }


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

    return render(
        request,
        "users/profile.html",
        {"u_form": u_form, "p_form": p_form, "profile": profile},
    )


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


# ------------------- Test Views -------------------

@login_required
def test_email_view(request):
    """Test email sending functionality"""
    try:
        result = send_mail(
            subject="🧪 Test Email from FinSecure",
            message="This is a test email to verify your configuration.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=False,
        )
        if result == 1:
            messages.success(request, f"✅ Test email sent successfully to {request.user.email}")
            return HttpResponse(f"✅ Email sent successfully to {request.user.email}! Check your inbox.")
        else:
            messages.error(request, "❌ Email sending failed (result = 0)")
            return HttpResponse("❌ Email failed to send (result = 0)")
    except Exception as e:
        messages.error(request, f"❌ Email error: {str(e)}")
        return HttpResponse(f"❌ Email sending failed: {str(e)}")


@login_required
def test_messages_view(request):
    """Test Django messages functionality"""
    messages.success(request, "✅ Success message test!")
    messages.info(request, "ℹ Info message test!")
    messages.warning(request, "⚠ Warning message test!")
    messages.error(request, "❌ Error message test!")
    return redirect("dashboard")

from django.core.management import call_command
def run_temp_superuser(request):
    call_command("create_or_reset_superuser")
    return HttpResponse("Superuser created or reset. Delete this view after use.")