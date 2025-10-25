import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scope (read-only)
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def gmail_authenticate():
    """Authenticate Gmail API using local token.json (standalone, no Django)"""
    creds = None

    # If token.json exists → load it
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If no valid creds → refresh or login again
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired token...")
            creds.refresh(Request())
        else:
            print("🌐 Opening browser for Google login...")
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8080)

        # Save the creds for next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
            print("💾 New token.json saved!")

    return build("gmail", "v1", credentials=creds)


def fetch_latest_emails(max_results=5):
    """Fetch latest email subjects"""
    service = gmail_authenticate()
    results = service.users().messages().list(userId="me", maxResults=max_results).execute()
    messages = results.get("messages", [])
    email_subjects = []

    if not messages:
        print("📭 No messages found.")
    else:
        print(f"📩 Latest {len(messages)} emails:")
        for msg in messages:
            msg_data = service.users().messages().get(userId="me", id=msg["id"]).execute()
            headers = msg_data.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            print(f"   ➡ {subject}")
            email_subjects.append(subject)

    return email_subjects


if __name__ == "__main__":
    fetch_latest_emails()
