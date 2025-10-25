import os
import sys
import django

# Add outer backend folder to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set correct Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

# Setup Django
django.setup()

from emails.gmail_auth import gmail_authenticate

# 3️⃣ Your Gmail code
service = gmail_authenticate()

results = service.users().messages().list(userId='me', maxResults=5).execute()
messages = results.get('messages', [])

if not messages:
    print("No messages found.")
else:
    print("Recent Emails:")
    for msg in messages:
        print(msg)
