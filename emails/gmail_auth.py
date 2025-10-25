import os
import json
import pickle
import django
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from .models import GmailCredential

# Setup Django (for standalone Gmail script use)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finalyearproject.settings")
django.setup()

# Gmail API scope
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def gmail_authenticate(user=None):
    """
    Authenticate Gmail API — supports:
      - Per-user database storage (via GmailCredential)
      - Local token.pkl fallback (for testing)
    """
    creds = None

    # ✅ 1. Try to load from database if user is passed
    if user:
        try:
            cred_obj = GmailCredential.objects.get(user=user)
            creds = Credentials.from_authorized_user_info(json.loads(cred_obj.token), SCOPES)
        except GmailCredential.DoesNotExist:
            pass

    # ✅ 2. Try from local token.pkl (fallback)
    if not creds and os.path.exists("token.pkl"):
        with open("token.pkl", "rb") as token:
            creds = pickle.load(token)

    # ✅ 3. If creds invalid or missing → prompt login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("🌐 Opening browser for Google login...")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8080)

        # Save credentials
        if user:
            GmailCredential.objects.update_or_create(
                user=user,
                defaults={"token": creds.to_json()}
            )
            print(f"💾 Credentials saved in DB for {user.username}")
        else:
            with open("token.pkl", "wb") as token:
                pickle.dump(creds, token)

    # ✅ 4. Build Gmail API service
    service = build("gmail", "v1", credentials=creds)
    print("✅ Gmail API service created successfully.")
    return service


def get_latest_emails(service, max_results=5):
    """Fetch latest emails with metadata for dashboard"""
    emails = []
    results = service.users().messages().list(userId="me", maxResults=max_results).execute()
    messages = results.get("messages", [])

    if not messages:
        print("📭 No messages found.")
        return emails

    for msg in messages:
        msg_data = service.users().messages().get(
            userId="me", id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()

        headers = msg_data.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "(Unknown Sender)")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "")
        snippet = msg_data.get("snippet", "")

        emails.append({
            "subject": subject,
            "from": sender,
            "date": date,
            "snippet": snippet
        })

    return emails


def get_transaction_emails(service, max_results=10):
    """Fetch recent Gmail emails related to financial transactions"""
    query = "subject:(transaction OR payment OR receipt OR debit OR credit OR deposit)"
    results = service.users().messages().list(userId="me", maxResults=max_results, q=query).execute()
    messages = results.get("messages", [])
    transactions = []

    if not messages:
        print("💸 No transaction emails found.")
        return transactions

    for msg in messages:
        msg_data = service.users().messages().get(
            userId="me", id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"]
        ).execute()
        headers = msg_data.get("payload", {}).get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "")
        snippet = msg_data.get("snippet", "")

        transactions.append({
            "description": subject or snippet[:50],
            "date": date,
            "amount": "N/A",
            "currency": "INR"
        })

    return transactions
