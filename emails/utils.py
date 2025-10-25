import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from .models import GmailCredential

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def gmail_authenticate(user):
    creds = None

    # Try to load from DB
    try:
        cred_obj = GmailCredential.objects.get(user=user)
        creds = Credentials.from_authorized_user_info(json.loads(cred_obj.token), SCOPES)
    except GmailCredential.DoesNotExist:
        pass

    # If no creds or expired, refresh or ask login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=8080)

        # Save token in DB for this user
        token_json = creds.to_json()
        GmailCredential.objects.update_or_create(user=user, defaults={"token": token_json})

    return build("gmail", "v1", credentials=creds)
