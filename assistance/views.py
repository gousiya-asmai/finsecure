import os
import json
import logging
from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from assistance.forms import FinancialProfileForm
from assistance.models import FinancialProfile, AssistanceResult, SmartSuggestion

# ✅ Gmail credentials model is now in users.models
from users.models import GmailCredential, UserProfile
from users.utils import fetch_recent_transactions, generate_suggestions
from assistance.utils import (
    train_model,
    predict_assistance,
    generate_recommendations,
    is_gmail_connected,
)
from assistance.assistance_utils import send_assistance_email_async
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from users.models import GmailTransaction, UserProfile
from assistance.models import SmartSuggestion
from users.utils import fetch_recent_transactions, fetch_latest_emails, save_transactions_to_db
import logging
import socket

socket.setdefaulttimeout(30)

logger = logging.getLogger(__name__)
User = get_user_model()

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# -------------------------------------------------------------------
# Gmail OAuth Flow
# -------------------------------------------------------------------
@login_required
def connect_gmail(request):
    """Redirect user to Gmail OAuth consent screen."""
    try:
        flow = Flow.from_client_secrets_file(
            os.path.join(settings.BASE_DIR, "credentials.json"),
            scopes=SCOPES,
            redirect_uri=request.build_absolute_uri("/assistance/oauth2callback/"),
        )

        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )

        request.session["state"] = state
        return redirect(authorization_url)

    except Exception as e:
        logger.error(f"Gmail OAuth flow error: {e}", exc_info=True)
        messages.error(request, "❌ Unable to initiate Gmail connection. Please try again.")
        return redirect("dashboard")

@login_required
def oauth2callback(request):
    """Handle Gmail OAuth2 callback and save credentials."""
    state = request.session.get("state")
    if not state:
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect("dashboard")

    try:
        flow = Flow.from_client_secrets_file(
            os.path.join(settings.BASE_DIR, "credentials.json"),
            scopes=SCOPES,
            state=state,
            redirect_uri=request.build_absolute_uri("/assistance/oauth2callback/"),
        )

        flow.fetch_token(authorization_response=request.build_absolute_uri())
        creds = flow.credentials

        # ✅ Save credentials properly in individual fields
        GmailCredential.objects.update_or_create(
            user=request.user,
            defaults={
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": json.dumps(creds.scopes),
                "expiry": creds.expiry,
            },
        )

        messages.success(request, "✅ Gmail connected successfully!")

    except Exception as e:
        logger.error(f"OAuth2 Error: {e}", exc_info=True)
        messages.error(request, "❌ Gmail connection failed. Please try again.")

    return redirect("dashboard")

@login_required
def disconnect_gmail(request):
    """Disconnect Gmail for current user."""
    GmailCredential.objects.filter(user=request.user).delete()
    messages.info(request, "🔌 Gmail disconnected successfully.")
    return redirect("dashboard")


# -------------------------------------------------------------------
# Gmail Email Fetcher
# -------------------------------------------------------------------
def get_latest_emails(user):
    """Fetch 5 most recent Gmail emails for a user."""
    try:
        gmail_cred = GmailCredential.objects.get(user=user)
        token_data = {
    "token": gmail_cred.access_token,
    "refresh_token": gmail_cred.refresh_token,
    "token_uri": gmail_cred.token_uri,
    "client_id": gmail_cred.client_id,
    "client_secret": gmail_cred.client_secret,
    "scopes": eval(gmail_cred.scopes or "[]"),
}

        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(userId="me", maxResults=5).execute()
        message_list = results.get("messages", [])
        emails = []

        for msg in message_list:
            msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
            headers = msg_data["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "(Unknown Sender)")
            snippet = msg_data.get("snippet", "")
            emails.append({"subject": subject, "from": sender, "snippet": snippet})

        return emails

    except GmailCredential.DoesNotExist:
        logger.warning(f"No Gmail credentials found for user {user}")
        return []
    except Exception as e:
        logger.error(f"Error fetching Gmail emails: {e}", exc_info=True)
        return []


# -------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------



@login_required(login_url="login")
def dashboard_view(request):
    """
    Unified user dashboard — shows Gmail + profile + suggestions.
    Only displays 'Transaction done' related Gmail messages (excludes fraud/alerts/OTPs).
    """
    try:
        # ---------------- User Profile ----------------
        profile, _ = UserProfile.objects.get_or_create(user=request.user)

        if not profile.is_complete():
            messages.warning(request, "⚠ Your profile is incomplete. Please update it.")

        # ---------------- Gmail Transactions ----------------
        gmail_transactions = list(
            GmailTransaction.objects.filter(user=request.user)
            .filter(description__icontains="transaction done")  # only “Transaction done” emails
            .exclude(description__iregex=r"fraud|alert|security|otp|unauthorized|blocked|suspicious")
            .order_by("-created_at")[:5]  # show latest 5
            .values(
                "description",
                "amount",
                "currency",
                "created_at",
                "transaction_type",
                "category",
                "message_id"
            )
        )

        # Add Gmail link for each transaction
        for txn in gmail_transactions:
            msg_id = txn.get("message_id")
            txn["gmail_link"] = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}" if msg_id else None
            # Simplify description to subject line only
            txn["description"] = txn["description"].split("\n")[0][:80] if txn["description"] else "(No Subject)"

        # ---------------- Gmail Connection Data ----------------
        latest_emails = request.session.get("latest_emails", [])
        connected_gmail = request.session.get("connected_gmail")

        # ---------------- Fetch New Transactions if Empty ----------------
        if not gmail_transactions:
            try:
                fetched = fetch_recent_transactions(request.user, max_results=5)
                if fetched:
                    gmail_transactions = fetched[:5]
            except Exception as e:
                logger.warning(f"Gmail fetch error (transactions): {e}")
                gmail_transactions = []

        # ---------------- Fetch Latest Emails ----------------
        if not latest_emails:
            try:
                latest_emails = fetch_latest_emails(request.user, max_results=5)
            except Exception as e:
                logger.warning(f"Gmail fetch error (emails): {e}")
                latest_emails = []

        # ---------------- Gmail Connection Status ----------------
        gmail_connected = bool(latest_emails or gmail_transactions or connected_gmail)

        # ---------------- Smart Suggestions ----------------
        suggestions_qs = SmartSuggestion.objects.filter(user=request.user).order_by("-created_at")[:5]
        suggestions = [
            {"suggestion": s.suggestion, "is_alert": s.is_alert, "created_at": s.created_at}
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
        logger.error(f"❌ Dashboard error: {e}", exc_info=True)
        messages.error(request, f"Something went wrong loading your dashboard: {str(e)}")
        return redirect("home")




# -------------------------------------------------------------------
# Assistance Engine
# -------------------------------------------------------------------
@login_required
def assist_home(request):
    """Main AI financial assistance logic."""
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        income = user_profile.income or 0
    except UserProfile.DoesNotExist:
        user_profile = None
        income = 0

    if request.method == "POST":
        form = FinancialProfileForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Please correct the errors below.")
            return render(request, "assistance/home.html", {"form": form, "income": income})

        profile, _ = FinancialProfile.objects.get_or_create(user=request.user)
        for field, value in form.cleaned_data.items():
            setattr(profile, field, value)
        profile.income = income

        # --- Rule-based suggestions ---
        suggestion_messages = []
        net_savings = income - profile.expenses

        suggestion_messages.append(
            "💡 Your savings are healthy. You can invest more."
            if net_savings > 10000 else
            "⚠️ Consider reducing expenses to improve savings."
        )

        if profile.credit_score >= 750:
            suggestion_messages.append("✅ Excellent credit score. Eligible for premium loans or credit cards.")
        elif 650 <= profile.credit_score < 750:
            suggestion_messages.append("⚠️ Average credit score. Improve your credit for better options.")
        else:
            suggestion_messages.append("⚠️ Low credit score. Work on repayments to improve your score.")

        if getattr(profile, "debts", 0) > 0:
            suggestion_messages.append(f"⚠️ You have outstanding debts of ₹{profile.debts}. Try reducing them.")
        else:
            suggestion_messages.append("✅ No debts. Keep up good financial health.")

        if getattr(profile, "monthly_investment", 0) > 0:
            suggestion_messages.append("💡 Your current investments are on track.")
        else:
            suggestion_messages.append("💡 Consider starting small investments based on your risk tolerance.")

        risk = getattr(profile, "risk_tolerance", "Medium").lower()
        if risk == "high":
            suggestion_messages.append("⚠️ High risk tolerance. Diversify your investments.")
        elif risk == "low":
            suggestion_messages.append("✅ Low risk tolerance. Prefer safer investments.")

        if getattr(profile, "monthly_savings_goal", 0) > net_savings:
            suggestion_messages.append("⚠️ Your savings goal is higher than your current net savings. Adjust your budget.")

        if getattr(profile, "financial_goals", ""):
            suggestion_messages.append(f"💡 Your financial goal: {profile.financial_goals}")

        # --- Gmail-based suggestions ---
        gmail_suggestions, transactions = [], []
        try:
            transactions = fetch_recent_transactions(request.user)
            if transactions:
                gmail_suggestions = generate_suggestions(profile.__dict__, transactions)
            else:
                gmail_suggestions.append("💡 No recent Gmail transactions found.")
        except Exception as e:
            logger.error(f"Gmail transaction fetch failed: {e}", exc_info=True)
            gmail_suggestions.append("⚠️ Could not fetch Gmail transactions. Please reconnect Gmail.")

        # --- ML-based recommendations ---
        assistance_required = predict_assistance(profile)
        if assistance_required is None:
            assistance_required = net_savings <= 10000 or profile.credit_score < 700

        ml_recommendations = generate_recommendations(profile, assistance_required)

        # --- Save suggestions ---
        all_suggestions = suggestion_messages + gmail_suggestions + ml_recommendations
        profile.suggestion = "\n".join(all_suggestions)
        profile.save()

        if user_profile:
            AssistanceResult.objects.create(
                user=user_profile,
                assistance_required=assistance_required,
                suggestion=profile.suggestion,
                submitted_at=timezone.now(),
            )

        for s in all_suggestions:
            SmartSuggestion.objects.create(
                user=request.user,
                suggestion=s,
                is_alert=s.startswith("⚠️"),
            )

        # --- Send report email asynchronously ---
        email_subject = "Your Financial Assistance Report"
        email_message = f"""
Dear {request.user.get_full_name() or request.user.username},

Here are your personalized financial suggestions:

{profile.suggestion}

Thank you for using FinSecure.
"""
        send_assistance_email_async(email_subject, email_message, request.user.email)

        return render(request, "assistance/result.html", {
            "profile": profile,
            "income": income,
            "suggestions": suggestion_messages,
            "gmail_suggestions": gmail_suggestions,
            "transactions": transactions,
            "ml_recommendations": ml_recommendations,
            "ml_assistance_required": assistance_required,
        })

    # GET: render empty form
    form = FinancialProfileForm()
    return render(request, "assistance/home.html", {"form": form, "income": income})


# -------------------------------------------------------------------
# Other Pages
# -------------------------------------------------------------------
@login_required
def all_suggestions(request):
    """View all suggestions for a user."""
    suggestions = SmartSuggestion.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "assistance/all_suggestions.html", {"suggestions": suggestions})


def privacy_policy(request):
    return render(request, "privacy_policy.html")


def terms_of_service(request):
    return render(request, "terms_of_service.html")
