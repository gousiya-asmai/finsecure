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
from users.sendgrid_utils import send_otp_via_sendgrid


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
    if request.method == "POST":
        input_otp = request.POST.get("otp")
        session_otp = request.session.get("otp")
        user_id = request.session.get("user_id")
        otp_expiry = request.session.get("otp_expiry")

        # Expiry check
        if otp_expiry and timezone.now() > timezone.datetime.fromisoformat(otp_expiry):
            messages.error(request, "⏳ OTP expired. Please request a new one.")
            return redirect("login")  # Don't clear session here

        # OTP match
        if session_otp and input_otp == session_otp:
            try:
                user = User.objects.get(id=user_id)
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                _check_profile_and_send_email(user)
                # ONLY clear session after login is successful and you are about to redirect!
                for k in ["otp", "user_id", "otp_expiry"]:
                    request.session.pop(k, None)
                return redirect("dashboard")
            except User.DoesNotExist:
                messages.error(request, "User not found. Please login again.")
                return redirect("login")
        else:
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


@login_required(login_url="login")
def dashboard_view(request):
    """
    Display the user dashboard with profile info, Gmail connection status,
    latest emails, transactions, and smart suggestions.
    """
    try:
        # Ensure profile exists
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        # Check profile completeness
        if not profile.is_complete():
            messages.warning(request, "⚠️ Your profile is incomplete. Please update it.")

        # Load session-based Gmail data
        gmail_connected = request.session.get("gmail_connected", False)
        connected_gmail = request.session.get("connected_gmail")
        latest_emails = request.session.get("latest_emails", [])
        gmail_transactions = request.session.get("gmail_transactions", [])

        # Fetch stored smart suggestions (if available)
        suggestions_qs = SmartSuggestion.objects.filter(user=request.user).order_by("-created_at")[:5]
        suggestions = [s.suggestion_text for s in suggestions_qs] if suggestions_qs.exists() else []

        # Optionally, you could generate fresh suggestions from profile + transactions
        # from users.utils import generate_suggestions
        # suggestions = generate_suggestions(profile.__dict__, gmail_transactions)

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
        print("❌ Dashboard error:", e)
        messages.error(request, f"Something went wrong loading your dashboard: {str(e)}")
        return redirect("error_page") if "error_page" in [u.name for u in request.resolver_match.app_names] else redirect("home")

# ------------------- Dashboard Data (AJAX) -------------------
@login_required
def get_dashboard_data(request):
    user = request.user
    transactions = Transaction.objects.filter(user=user)

    period = request.GET.get("period", "all")
    if period == "7":
        start_date = timezone.now() - timezone.timedelta(days=7)
        transactions = transactions.filter(timestamp__gte=start_date)
    elif period == "30":
        start_date = timezone.now() - timezone.timedelta(days=30)
        transactions = transactions.filter(timestamp__gte=start_date)

    total_spending = transactions.filter(transaction_type="debit").aggregate(Sum("amount"))["amount__sum"] or 0
    total_income = transactions.filter(transaction_type="credit").aggregate(Sum("amount"))["amount__sum"] or 0
    savings = total_income - total_spending

    alerts = []
    if total_income > 0 and total_spending > 0.7 * total_income:
        alerts.append("⚠️ High spending: over 70% of your income.")
    if savings < 0:
        alerts.append("⚠️ Overspending: savings are negative.")
    fraud_count = transactions.filter(is_fraud=True).count()
    if fraud_count:
        alerts.append(f"⚠️ {fraud_count} fraud transactions detected!")

    category_spending = list(
        transactions.filter(transaction_type="debit").values("category").annotate(total=Sum("amount"))
    )

    fraud_stats = list(transactions.values("is_fraud").annotate(count=Count("id")))

    return JsonResponse({
        "income": total_income,
        "spending": total_spending,
        "savings": savings,
        "alerts": alerts,
        "category_spending": category_spending,
        "fraud_stats": fraud_stats,
    })


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
