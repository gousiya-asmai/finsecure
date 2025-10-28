import os
import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.http import HttpResponse

from .forms import FinancialProfileForm
from .models import FinancialProfile, AssistanceResult, SmartSuggestion, GmailCredential
from users.models import UserProfile
from users.utils import fetch_recent_transactions, generate_suggestions

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from assistance.utils import train_model, predict_assistance, generate_recommendations, is_gmail_connected


# Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# -------------------------------------------------------------------
# Gmail OAuth Flow
# -------------------------------------------------------------------
@login_required
def connect_gmail(request):
    """Redirect user to Gmail OAuth consent screen."""
    flow = Flow.from_client_secrets_file(
        os.path.join(settings.BASE_DIR, "credentials.json"),
        scopes=SCOPES,
        redirect_uri=request.build_absolute_uri("/assistance/oauth2callback/"),
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # ensures refresh_token is returned
    )
    request.session["state"] = state
    return redirect(authorization_url)


@login_required
def oauth2callback(request):
    """Handle Gmail OAuth2 callback and save credentials in DB."""
    state = request.session.get("state")
    if not state:
        messages.error(request, "Invalid OAuth state. Please try again.")
        return redirect("dashboard")

    flow = Flow.from_client_secrets_file(
        os.path.join(settings.BASE_DIR, "credentials.json"),
        scopes=SCOPES,
        state=state,
        redirect_uri=request.build_absolute_uri("/assistance/oauth2callback/"),
    )

    try:
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        creds = flow.credentials

        # ✅ Save token in DB
        GmailCredential.objects.update_or_create(
            user=request.user,
            defaults={"token": creds.to_json()},
        )

        messages.success(request, "✅ Gmail connected successfully!")
    except Exception as e:
        print("OAuth2 Error:", e)
        messages.error(request, "❌ Gmail connection failed. Please try again.")

    return redirect("dashboard")


@login_required
def disconnect_gmail(request):
    """Remove Gmail connection for current user."""
    GmailCredential.objects.filter(user=request.user).delete()
    messages.info(request, "🔌 Gmail disconnected.")
    return redirect("dashboard")


# -------------------------------------------------------------------
# Gmail Emails Preview (Optional)
# -------------------------------------------------------------------
def get_latest_emails(user):
    """Fetch the 5 most recent emails using Gmail API for a specific user."""
    try:
        gmail_cred = GmailCredential.objects.get(user=user)
        creds = Credentials.from_authorized_user_info(json.loads(gmail_cred.token), SCOPES)
        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(userId="me", maxResults=5).execute()
        messages_data = results.get("messages", [])
        emails = []

        for msg in messages_data:
            msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
            headers = msg_data["payload"]["headers"]
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "(Unknown Sender)")
            snippet = msg_data.get("snippet", "")
            emails.append({"subject": subject, "from": sender, "snippet": snippet})

        return emails
    except GmailCredential.DoesNotExist:
        return []
    except Exception as e:
        print("Error fetching Gmail emails:", e)
        return []


# -------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------
@login_required
def dashboard(request):
    """User dashboard showing profile, Gmail connection, latest suggestions, and Gmail transactions."""
    user = request.user

    # ✅ Gmail connection status
    gmail_connected = is_gmail_connected(user)

    # ✅ Get profile safely
    profile_data = {}
    try:
        user_profile = UserProfile.objects.get(user=user)
        profile_data = {
            "income": getattr(user_profile, "income", 0),
            "occupation": getattr(user_profile, "occupation", ""),
            "phone": getattr(user_profile, "phone", ""),
        }
    except UserProfile.DoesNotExist:
        messages.warning(request, "⚠️ Please complete your profile to get better suggestions.")

    # ✅ Fetch last 5 suggestions
    suggestions = SmartSuggestion.objects.filter(user=user).order_by("-created_at")[:5]

    # ✅ Fetch last 5 Gmail transactions
    transactions = []
    if gmail_connected:
        try:
            all_txns = fetch_recent_transactions(user)  # returns list of dicts
            transactions = all_txns[:5] if all_txns else []
        except Exception as e:
            print("Error fetching Gmail transactions for dashboard:", e)
            transactions = []

    return render(request, "users/dashboard.html", {
        "profile": profile_data,
        "suggestions": suggestions,
        "gmail_connected": gmail_connected,
        "transactions": transactions,
    })

# -------------------------------------------------------------------
# Assistance Engine
# -------------------------------------------------------------------
# ---------------- Assistance ----------------
@login_required
def assist_home(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        income = user_profile.income or 0
    except UserProfile.DoesNotExist:
        user_profile = None
        income = 0
    
    if request.method == "POST":
        form = FinancialProfileForm(request.POST)
        if form.is_valid():
            profile, created = FinancialProfile.objects.get_or_create(user=request.user)
            for field, value in form.cleaned_data.items():
                setattr(profile, field, value)
            profile.income = income

            suggestion_messages = []
            net_savings = income - profile.expenses
            
            # Basic heuristic suggestions no change
            if net_savings > 10000:
                suggestion_messages.append("💡 Your savings are healthy. You can invest more.")
            else:
                suggestion_messages.append("⚠️ Consider reducing expenses to improve savings.")
            
            # Further heuristic suggestions for speed
            # ...
            
            gmail_suggestions = []  # Skip fetching Gmail for speed
            
            ml_recommendations = []  # Skip ML
            
            all_suggestions = suggestion_messages + gmail_suggestions + ml_recommendations
            profile.suggestion = "\n".join(all_suggestions)
            profile.save()

            # Save Assistance result
            if user_profile:
                AssistanceResult.objects.create(
                    user=user_profile,
                    assistance_required=False,
                    suggestion=profile.suggestion,
                    submitted_at=timezone.now(),
                )

            # Save each suggestion individually
            for s in all_suggestions:
                SmartSuggestion.objects.create(
                    user=request.user,
                    suggestion=s,
                    is_alert=s.startswith("⚠️"),
                )

            # Skip email sending completely for speed
            
            return render(request, "assistance/result.html", {
                "profile": profile,
                "income": income,
                "suggestions": suggestion_messages,
                "gmail_suggestions": gmail_suggestions,
                "transactions": [],
                "ml_recommendations": ml_recommendations,
                "ml_assistance_required": False,
            })

        return render(request, "assistance/home.html", {"form": form, "income": income})

    form = FinancialProfileForm()
    return render(request, "assistance/home.html", {"form": form, "income": income})


# -------------------------------------------------------------------
# All Suggestions
# -------------------------------------------------------------------
@login_required
def all_suggestions(request):
    """View full suggestion history for a user."""
    suggestions = SmartSuggestion.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "assistance/all_suggestions.html", {"suggestions": suggestions})
