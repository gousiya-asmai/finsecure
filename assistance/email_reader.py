import os
import sys
import django
import imaplib
import email
from email.header import decode_header

# Setup Django environment
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')  # ✅ Match your inner project folder name

django.setup()

from assistance.models import PurchaseAlert

EMAIL = "finsecure7@gmail.com"
APP_PASSWORD = "wgnw gmrv uute hfmc"

imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(EMAIL, APP_PASSWORD)
imap.select("inbox")

status, messages = imap.search(None, 'FROM "googleplay-noreply@google.com"')
email_ids = messages[0].split()

for email_id in email_ids[-5:]:
    res, msg_data = imap.fetch(email_id, "(RFC822)")
    for response in msg_data:
        if isinstance(response, tuple):
            msg = email.message_from_bytes(response[1])
            subject, encoding = decode_header(msg["Subject"])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding or "utf-8")

            sender = msg.get("From")

            if not PurchaseAlert.objects.filter(sender=sender, subject=subject).exists():
                alert = PurchaseAlert(sender=sender, subject=subject)
                alert.save()
                print(f"✅ Saved alert: {subject}")
            else:
                print(f"⚠️ Already exists: {subject}")

imap.logout()
