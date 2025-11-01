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
        token_data = json.loads(gmail_cred.token)
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
@login_required
def dashboard(request):
    """User dashboard showing profile, Gmail connection, and suggestions."""
    user = request.user
    gmail_connected = is_gmail_connected(user)

    try:
        user_profile = UserProfile.objects.get(user=user)
        profile_data = {
            "income": getattr(user_profile, "income", 0),
            "occupation": getattr(user_profile, "occupation", ""),
            "phone": getattr(user_profile, "phone", ""),
        }
    except UserProfile.DoesNotExist:
        user_profile = None
        profile_data = {}
        messages.warning(request, "⚠️ Please complete your profile to get better suggestions.")

    suggestions = SmartSuggestion.objects.filter(user=user).order_by("-created_at")[:5]

    transactions = []
    if gmail_connected:
        try:
            transactions = fetch_recent_transactions(user)[:5]
        except Exception as e:
            logger.error(f"Error fetching Gmail transactions for dashboard: {e}", exc_info=True)

    return render(request, "users/dashboard.html", {
        "profile": profile_data,
        "suggestions": suggestions,
        "gmail_connected": gmail_connected,
        "transactions": transactions,
    })


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
