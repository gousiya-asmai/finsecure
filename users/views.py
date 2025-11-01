# users/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from decimal import Decimal
import logging
from users.models import GmailTransaction, GmailCredential
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
import os
import google.auth
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# Models
from transactions.models import Transaction
from assistance.models import SmartSuggestion
from users.models import UserProfile
from google_auth_oauthlib.flow import InstalledAppFlow
# Utils
from users.utils import (
    fetch_latest_emails,
    fetch_recent_transactions,
    save_transactions_to_db,
    get_gmail_profile,
)
from users.otp_utils import generate_and_send_otp, verify_otp

# Forms
from users.forms import UserUpdateForm, ProfileUpdateForm
from datetime import datetime
from users.utils import fetch_latest_emails, fetch_recent_transactions, get_gmail_profile



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
            if not user_qs.exists():
                messages.error(request, "❌ Email not registered")
                return redirect("login")

            user = user_qs.first()
            try:
                generate_and_send_otp(email)
                request.session["otp_email"] = email
                request.session["user_id"] = user.id
                messages.success(request, f"✅ OTP sent to {email}. Please verify within 10 minutes.")
                return redirect("verify_otp")
            except Exception as e:
                logging.error(f"OTP sending failed: {e}", exc_info=True)
                messages.error(request, "❌ Failed to send OTP. Please try again later.")
                return redirect("login")

    return render(request, "users/login.html")


# ------------------- OTP Verification -------------------
def verify_otp_view(request):
    if request.method == "POST":
        entered_otp = request.POST.get("otp")
        email = request.session.get("otp_email")
        user_id = request.session.get("user_id")

        if not email or not user_id:
            messages.error(request, "Session expired. Please login again.")
            return redirect("login")

        if verify_otp(email, entered_otp):
            try:
                user = User.objects.get(id=user_id)
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

                # Clear session
                for k in ["otp_email", "user_id"]:
                    request.session.pop(k, None)

                messages.success(request, "✅ OTP verified successfully!")
                return redirect("dashboard")
            except User.DoesNotExist:
                messages.error(request, "User not found. Please login again.")
                return redirect("login")
        else:
            messages.error(request, "❌ Invalid or expired OTP. Please try again.")
            return redirect("verify_otp")

    return render(request, "users/verify_otp.html")


# ------------------- Resend OTP -------------------
def resend_otp_view(request):
    email = request.session.get("otp_email")
    if not email:
        messages.error(request, "Session expired. Please login again.")
        return redirect("login")

    try:
        generate_and_send_otp(email)
        messages.success(request, f"🔄 New OTP sent to {email}. Please verify within 10 minutes.")
    except Exception as e:
        logging.error(f"Error resending OTP: {e}", exc_info=True)
        messages.error(request, "❌ Failed to resend OTP. Try again later.")
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
# ========================================================

# =========================================================
# DASHBOARD VIEW
# =========================================================

@login_required(login_url="login")
def dashboard_view(request):
    try:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        # Warn if profile incomplete
        if not profile.is_complete():
            messages.warning(request, "⚠ Your profile is incomplete. Please update it.")

        # ✅ Get Gmail data from session
        latest_emails = request.session.get("latest_emails")
        gmail_transactions = request.session.get("gmail_transactions")
        connected_gmail = request.session.get("connected_gmail")
        gmail_connected = request.session.get("gmail_connected", False)

        # ✅ If not in session, try to load from DB
        if not gmail_transactions:
            try:
                gmail_transactions = list(
                    GmailTransaction.objects.filter(user=request.user)
                    .order_by("-created_at")
                    .values("description", "amount", "currency", "message_id")[:10]
                )
            except Exception as e:
                logging.warning(f"Failed to load Gmail transactions from DB: {e}")
                gmail_transactions = []

        # ✅ If no latest emails, try fetching directly
        if not latest_emails and gmail_connected:
            try:
                latest_emails = fetch_latest_emails(request.user, max_results=5)
            except Exception as e:
                logging.warning(f"Error fetching latest Gmail emails: {e}")
                latest_emails = []

        # ✅ Smart Suggestions
        suggestions_qs = SmartSuggestion.objects.filter(user=request.user).order_by("-created_at")[:5]
        suggestions = [
            {
                "suggestion": s.suggestion_text,
                "is_alert": getattr(s, "is_alert", False),
                "created_at": s.created_at,
            }
            for s in suggestions_qs
        ]

        # ✅ Context for template
        context = {
            "profile": profile,
            "income": profile.income if profile else 0.0,
            "gmail_connected": gmail_connected,
            "connected_gmail": connected_gmail,
            "latest_emails": latest_emails or [],
            "gmail_transactions": gmail_transactions or [],
            "suggestions": suggestions,
        }

        return render(request, "users/dashboard.html", context)

    except Exception as e:
        logging.error(f"❌ Dashboard load error: {e}", exc_info=True)
        messages.error(request, "Something went wrong loading your dashboard.")
        return redirect("home")


# =========================================================
# AJAX DASHBOARD DATA (for charts)
# =========================================================
# =========================================================
# AJAX DASHBOARD DATA (for charts)
# =========================================================
@login_required
def get_dashboard_data(request):
    from users.models import UserProfile  # ensure imported
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

    # --- Fetch profile income ---
    profile = UserProfile.objects.filter(user=user).first()
    profile_income = Decimal(str(profile.income)) if profile and profile.income else Decimal("0.0")

    # --- Calculate totals ---
    total_income = (
        transactions.filter(transaction_type="credit").aggregate(Sum("amount"))["amount__sum"]
        or profile_income
    )
    total_spending = (
        transactions.filter(transaction_type="debit").aggregate(Sum("amount"))["amount__sum"]
        or Decimal("0.0")
    )
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

    # --- Category Spending ---
    category_spending = list(
        transactions.filter(transaction_type="debit")
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    # --- Fraud Stats ---
    fraud_stats = list(
        transactions.values("is_fraud")
        .annotate(count=Count("id"))
        .order_by("-is_fraud")
    )

    # --- Spending Graphs ---
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

        labels_list, values_list = [], []
        for d in daily_data:
            try:
                date_obj = (
                    d["day"] if isinstance(d["day"], datetime)
                    else datetime.strptime(str(d["day"]), "%Y-%m-%d")
                )
                labels_list.append(date_obj.strftime("%b %d"))
            except Exception:
                labels_list.append(str(d["day"]))
            values_list.append(float(d["total"]))

        if days == 7:
            labels_7d, spending_7d = labels_list, values_list
        elif days == 30:
            labels_30d, spending_30d = labels_list, values_list
        else:
            labels_all, spending_all = labels_list, values_list

    # --- Fraud Graphs ---
    fraud_qs = transactions.filter(is_fraud=True)
    fraud_daily = (
        fraud_qs.extra(select={"day": "date(timestamp)"})
        .values("day")
        .annotate(total=Sum("amount"))
        .order_by("day")
    )

    fraud_labels, fraud_amount = [], []
    for d in fraud_daily:
        try:
            date_obj = (
                d["day"] if isinstance(d["day"], datetime)
                else datetime.strptime(str(d["day"]), "%Y-%m-%d")
            )
            fraud_labels.append(date_obj.strftime("%b %d"))
        except Exception:
            fraud_labels.append(str(d["day"]))
        fraud_amount.append(float(d["total"]))

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



# =========================================================
# GMAIL CONNECTION HANDLER
# =========================================================

@login_required
def connect_gmail(request):
    """
    Connect Gmail using OAuth2, save tokens per user,
    fetch latest emails and transactions, and update session + DB.
    """
    user = request.user
    try:
        # ✅ Ensure token directory exists
        TOKENS_DIR = os.path.join(settings.BASE_DIR, "tokens")
        os.makedirs(TOKENS_DIR, exist_ok=True)

        token_path = os.path.join(TOKENS_DIR, f"token_{user.id}.json")
        creds = None

        # ✅ Load credentials if already saved
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path)
            logging.info(f"🔑 Loaded existing Gmail token for {user.username}")

        # ✅ If no valid creds, run OAuth flow
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join(settings.BASE_DIR, "credentials.json"),
                scopes=[
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/userinfo.email",
                    "openid",
                ],
            )

            # For local dev, open a browser; on Render, redirect via host domain
            creds = flow.run_local_server(port=0)

            # ✅ Save user-specific token
            with open(token_path, "w") as token_file:
                token_file.write(creds.to_json())
            logging.info(f"✅ Saved Gmail token for {user.username} → {token_path}")

        # ✅ Get Gmail profile
        gmail_profile = get_gmail_profile(user)
        connected_gmail = gmail_profile.get("emailAddress", "Unknown")

        # ✅ Fetch recent Gmail data
        latest_emails = fetch_latest_emails(user, max_results=5)
        transactions = fetch_recent_transactions(user, max_results=10)

        # ✅ Save to session
        request.session["gmail_connected"] = True
        request.session["connected_gmail"] = connected_gmail
        request.session["latest_emails"] = latest_emails
        request.session["gmail_transactions"] = transactions

        # ✅ Persist transactions in DB
        if transactions:
            save_transactions_to_db(user, transactions)
            logging.info(f"💾 Saved {len(transactions)} Gmail transactions for {user.username}")

        messages.success(request, f"✅ Gmail connected successfully as {connected_gmail}!")

    except Exception as e:
        logging.error(f"❌ Gmail connection failed for {user.username}: {e}", exc_info=True)
        messages.error(request, f"⚠ Gmail connection failed: {str(e)}")

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
            from django.core.mail import send_mail
            send_mail(
                subject="Complete Your Profile",
                message="Your profile is incomplete. Please update it.",
                from_email="noreply@financesystem.com",
                recipient_list=[user.email],
                fail_silently=True,
            )
    except UserProfile.DoesNotExist:
        pass

@login_required(login_url='login')
def update_profile_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        profile.phone = request.POST.get("phone")
        profile.occupation = request.POST.get("occupation")
        income_value = request.POST.get("income")
        profile.income = float(income_value) if income_value else 0.0
        profile.save()
        messages.success(request, "✅ Profile updated successfully!")
        return redirect("dashboard")
    return render(request, "users/update_profile.html", {"profile": profile})

# ------------------- Test Views -------------------
@login_required
def test_email_view(request):
    try:
        from django.core.mail import send_mail
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
    messages.success(request, "✅ Success message test!")
    messages.info(request, "ℹ Info message test!")
    messages.warning(request, "⚠ Warning message test!")
    messages.error(request, "❌ Error message test!")
    return redirect("dashboard")


from django.core.management import call_command
def run_temp_superuser(request):
    call_command("create_or_reset_superuser")
    return HttpResponse("Superuser created or reset. Delete this view after use.")
