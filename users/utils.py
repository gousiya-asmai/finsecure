import re
import base64
import json
import logging
import os
import numpy as np
import joblib
import pandas as pd
import random
from datetime import timedelta

from django.conf import settings
from email.utils import parsedate_to_datetime
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth.models import User

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from users.models import GmailCredential, GmailTransaction, OTPVerification
from transactions.models import Transaction
from assistance.models import SmartSuggestion
logger = logging.getLogger(__name__)

# -------------------------------
# ⚙️ CONFIG
# -------------------------------
MODEL_PATH = os.path.join(settings.BASE_DIR, 'backend', 'models', 'fraud_model.pkl')
SCALER_PATH = os.path.join(settings.BASE_DIR, 'backend', 'models', 'feature_scaler.pkl')

EXPECTED_FEATURES = [
    'amount_log',
    'category_payment', 'category_purchase', 'category_withdrawal',
    'category_transfer', 'category_uncategorized',
    'transaction_type_credit', 'transaction_type_debit', 'transaction_type_uncategorized'
]

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# -------------------------------
# 🔑 GET GMAIL CREDENTIALS
# -------------------------------
def get_gmail_credentials(user):
    try:
        cred_obj = GmailCredential.objects.get(user=user)

        token_data = {
            "token": cred_obj.access_token,
            "refresh_token": cred_obj.refresh_token,
            "token_uri": cred_obj.token_uri,
            "client_id": cred_obj.client_id,
            "client_secret": cred_obj.client_secret,
            "scopes": (
                json.loads(cred_obj.scopes)
                if isinstance(cred_obj.scopes, str)
                else cred_obj.scopes
            ),
        }

        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

        if not creds.valid or creds.expired:
            if creds.refresh_token:
                creds.refresh(Request())
                expiry = creds.expiry
                if expiry and timezone.is_naive(expiry):
                    expiry = timezone.make_aware(expiry)

                cred_obj.access_token = creds.token
                cred_obj.expiry = expiry
                cred_obj.save(update_fields=["access_token", "expiry"])
                logger.info(f"🔄 Refreshed Gmail token for user {user.username}.")
            else:
                logger.warning(f"⚠️ No refresh token found for {user.username}.")
                return None

        return creds

    except GmailCredential.DoesNotExist:
        logger.warning(f"⚠️ No Gmail credentials found for {user.username}.")
        return None
    except Exception as e:
        logger.error(f"❌ Error loading Gmail credentials: {e}", exc_info=True)
        return None


# -------------------------------
# 💾 SAVE GMAIL CREDENTIALS
# -------------------------------
def save_gmail_credentials(user, creds):
    try:
        expiry = creds.expiry
        if expiry and timezone.is_naive(expiry):
            expiry = timezone.make_aware(expiry)

        scopes_json = json.dumps(list(creds.scopes)) if creds.scopes else "[]"

        GmailCredential.objects.update_or_create(
            user=user,
            defaults={
                "access_token": creds.token,
                "refresh_token": getattr(creds, "refresh_token", None),
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": scopes_json,
                "expiry": expiry,
            },
        )
        logger.info(f"✅ Saved Gmail credentials for {user.username}.")
    except Exception as e:
        logger.error(f"❌ Failed to save Gmail credentials for {user.username}: {e}", exc_info=True)


# -------------------------------
# 📧 FETCH LATEST EMAILS
# -------------------------------
def fetch_latest_emails(user, max_results=5):
    try:
        creds = get_gmail_credentials(user)
        if not creds:
            return []

        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(userId="me", maxResults=max_results).execute()
        messages = results.get("messages", [])
        emails = []

        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
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
                "snippet": snippet,
            })

        logger.info(f"✅ Fetched {len(emails)} latest email(s) for {user.username}.")
        return emails

    except Exception as e:
        logger.error(f"❌ Error fetching latest emails: {e}")
        return []


# -------------------------------
# 💰 FETCH RECENT TRANSACTIONS
# -----------------------------

from email.utils import parsedate_to_datetime
from django.utils import timezone
import re, base64, html, logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .models import GmailTransaction
from users.utils import get_gmail_credentials  # adjust if needed


import re
from bs4 import BeautifulSoup

def extract_amount_from_text(raw_text: str):
    """Extract numeric amount from Gmail body (handles text + HTML)."""
    if not raw_text:
        return 0.0

    # Step 1️⃣ — Remove HTML safely
    try:
        soup = BeautifulSoup(raw_text, "html.parser")
        text = soup.get_text(separator=" ")
    except Exception:
        text = raw_text

    # Step 2️⃣ — Normalize text
    text = text.replace(",", "").replace("₹", "").replace("Rs.", "").replace("INR", "")
    text = text.strip().lower()

    # Step 3️⃣ — Look for amount pattern
    patterns = [
        r"amount[:\s₹]*([\d]+\.?\d*)",
        r"rs[:\s₹]*([\d]+\.?\d*)",
        r"inr[:\s₹]*([\d]+\.?\d*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue

    return 0.0

import base64
import html
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.utils import timezone
from users.models import GmailTransaction
from users.utils import get_gmail_credentials
from users.utils import extract_amount_from_text  # or wherever your amount extraction lives


# ✅ Optional helper: simple auto-category detection
def detect_category(text, subject):
    """Simple keyword-based transaction categorization."""
    combined = f"{subject} {text}".lower()

    if any(k in combined for k in ["atm", "withdraw", "cash"]):
        return "withdrawal"
    elif any(k in combined for k in ["deposit", "credited", "salary"]):
        return "income"
    elif any(k in combined for k in ["bill", "payment", "electricity", "recharge", "upi", "sent to"]):
        return "bill payment"
    elif any(k in combined for k in ["transfer", "neft", "imps"]):
        return "transfer"
    elif any(k in combined for k in ["refund", "reversal"]):
        return "refund"
    else:
        return "general"


def fetch_recent_transactions(user, max_results=10):
    """Fetch latest Gmail transaction-related emails for the user."""
    logger = logging.getLogger(__name__)

    try:
        creds = get_gmail_credentials(user)
        if not creds:
            logger.warning(f"⚠️ No Gmail credentials for {user.username}.")
            return []

        service = build("gmail", "v1", credentials=creds)
        query = "subject:(transaction OR payment OR debited OR credited OR transfer OR purchase)"
        results = service.users().messages().list(
            userId="me", maxResults=max_results, q=query
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            logger.info(f"📭 No Gmail messages found for {user.username}.")
            return []

        new_transactions = []
        seen_ids = set(
            GmailTransaction.objects.filter(user=user).values_list("message_id", flat=True)
        )

        for msg in messages:
            msg_id = msg.get("id")
            if not msg_id or msg_id in seen_ids:
                continue  # skip duplicates or invalid

            try:
                message = service.users().messages().get(
                    userId="me", id=msg_id, format="full"
                ).execute()

                payload = message.get("payload", {})
                headers = payload.get("headers", [])

                subject = next(
                    (h["value"] for h in headers if h["name"].lower() == "subject"),
                    "(No Subject)",
                )
                sender = next(
                    (h["value"] for h in headers if h["name"].lower() == "from"),
                    "(Unknown Sender)",
                )
                date_raw = next(
                    (h["value"] for h in headers if h["name"].lower() == "date"), ""
                )
                snippet = message.get("snippet", "")

                # ⛔ Skip OTP/fraud/security alerts
                if re.search(
                    r"fraud|alert|security|otp|unauthorized|blocked|suspicious",
                    subject,
                    re.I,
                ):
                    continue

                # Decode email body
                body_text = snippet
                for part in payload.get("parts", []):
                    data = part.get("body", {}).get("data")
                    if data:
                        try:
                            decoded = base64.urlsafe_b64decode(data).decode(
                                "utf-8", errors="ignore"
                            )
                            body_text += " " + html.unescape(decoded)
                        except Exception:
                            pass

                # Extract amount safely
                amount = extract_amount_from_text(body_text or subject or snippet)
                if not amount:
                    amount = 0.0

                logger.debug(
                    f"[{user.username}] {subject} → ₹{amount} | snippet: {(body_text or snippet)[:100]}"
                )

                # Parse email date
                try:
                    parsed_date = parsedate_to_datetime(date_raw)
                    if parsed_date.tzinfo is None:
                        parsed_date = timezone.make_aware(parsed_date)
                except Exception:
                    parsed_date = timezone.now()

                # Determine type
                txn_type = (
                    "credit"
                    if re.search(r"\bcredited|received|deposit", body_text, re.I)
                    else "debit"
                )

                txn = {
                    "subject": subject,
                    "snippet": snippet,
                    "sender": sender,
                    "amount": amount,
                    "currency": "₹",
                    "transaction_type": txn_type,
                    "category": detect_category(body_text, subject),
                    "date": parsed_date,
                    "message_id": msg_id,
                    "gmail_link": f"https://mail.google.com/mail/u/0/#inbox/{msg_id}",
                }

                new_transactions.append(txn)

            except Exception as inner_e:
                logger.warning(
                    f"⚠️ Error parsing email {msg_id}: {inner_e}", exc_info=True
                )
                continue

        logger.info(
            f"✅ Parsed {len(new_transactions)} Gmail transactions for {user.username}."
        )
        return new_transactions[:max_results]

    except HttpError as e:
        logger.error(f"❌ Gmail API error for {user.username}: {e}")
        return []

    except Exception as e:
        logger.error(
            f"❌ fetch_recent_transactions error for {user.username}: {e}",
            exc_info=True,
        )
        return []

# 💾 SAVE TRANSACTIONS TO DB
# -------------------------------
# 💾 SAVE TRANSACTIONS TO DB
# -------------------------------
from users.models import GmailTransaction
import logging

def save_transactions_to_db(user, transactions):
    """
    Safely save fetched Gmail transactions to the database.
    - Skips duplicates (based on message_id)
    - Ignores unsupported fields (like 'snippet')
    - Returns count of new transactions saved
    """
    import logging
    from users.models import GmailTransaction

    logger = logging.getLogger(__name__)
    if not transactions:
        logger.info(f"⚠️ No transactions to save for {user.username}")
        return 0

    saved_count = 0
    existing_ids = set(
        GmailTransaction.objects.filter(user=user).values_list("message_id", flat=True)
    )

    for txn in transactions:
        msg_id = txn.get("message_id")
        if not msg_id or msg_id in existing_ids:
            continue  # skip invalid or duplicate

        try:
            # Some transactions may include extra keys (e.g., snippet)
            # We build only valid model fields here
            txn_data = {
                "user": user,
                "subject": txn.get("subject", "(No Subject)"),
                "sender": txn.get("sender", "(Unknown Sender)"),
                "amount": float(txn.get("amount") or 0.0),
                "currency": txn.get("currency", "₹"),
                "transaction_type": txn.get("transaction_type", "debit"),
                "category": txn.get("category", "general"),
                "date": txn.get("date"),
                "message_id": msg_id,
                "gmail_link": txn.get("gmail_link", ""),
            }

            GmailTransaction.objects.create(**txn_data)
            saved_count += 1
            existing_ids.add(msg_id)

        except Exception as e:
            logger.error(
                f"❌ Failed to save GmailTransaction for {user.username}: {e}",
                exc_info=True
            )
            continue

    logger.info(f"💾 Saved {saved_count} new transactions for {user.username}.")
    return saved_count

from django.core.mail import send_mail
from django.conf import settings

import re
import logging
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from users.models import GmailTransaction, FraudAlert  # adjust import if needed


def detect_and_alert_fraud(user):
    """
    Check user's Gmail transactions for suspicious or fraudulent patterns.
    Creates FraudAlert records and emails the user if any are found.
    """
    logger = logging.getLogger(__name__)
    suspicious_count = 0

    try:
        transactions = GmailTransaction.objects.filter(user=user).order_by("-date")[:20]

        if not transactions.exists():
            logger.info(f"📭 No Gmail transactions found for {user.username}")
            return 0

        for tx in transactions:
            reasons = []

            # --- Simple fraud rules (extend these anytime) ---
            if tx.amount and tx.amount > 100000:
                reasons.append(f"High transaction amount ₹{tx.amount:,.2f}")

            if re.search(r"fraud|unauthorized|suspicious|alert", tx.subject or "", re.I):
                reasons.append(f"Suspicious subject: {tx.subject}")

            if tx.sender and not re.search(r"bank|upi|transaction|noreply|alert", tx.sender, re.I):
                reasons.append(f"Unverified sender: {tx.sender}")

            # --- If any suspicious indicator detected ---
            if reasons:
                reason_text = "; ".join(reasons)
                message = (
                    f"A transaction appears suspicious:\n\n"
                    f"Subject: {tx.subject}\n"
                    f"Amount: ₹{tx.amount:,.2f}\n"
                    f"Sender: {tx.sender}\n\n"
                    f"Reason(s): {reason_text}"
                )

                # Prevent duplicate alerts for same transaction
                if not FraudAlert.objects.filter(
                    user=user,
                    message__icontains=tx.subject,
                    created_at__gte=timezone.now() - timezone.timedelta(days=1),
                ).exists():
                    FraudAlert.objects.create(
                        user=user,
                        title="🚨 Suspicious Transaction Detected",
                        message=message,
                        created_at=timezone.now(),
                    )

                    suspicious_count += 1

                    # Send HTML + plain-text fraud alert email
                    if user.email:
                        try:
                            html_content = render_to_string(
                                "emails/fraud_alert_email.html",
                                {
                                    "user": user,
                                    "subject": tx.subject,
                                    "amount": f"{tx.amount:,.2f}",
                                    "sender": tx.sender,
                                    "reason": reason_text,
                                    "gmail_link": tx.gmail_link,
                                },
                            )

                            email = EmailMultiAlternatives(
                                subject="🚨 Fraud Alert - Suspicious Transaction Detected",
                                body=message,
                                from_email="noreply@finsecure.com",
                                to=[user.email],
                            )
                            email.attach_alternative(html_content, "text/html")
                            email.send(fail_silently=True)

                            logger.warning(f"📨 Fraud alert email sent to {user.email}")

                        except Exception as e:
                            logger.error(f"❌ Failed to send fraud email for {user.username}: {e}")
                    else:
                        logger.warning(f"⚠️ No email address found for {user.username}, alert not sent.")

        if suspicious_count:
            logger.warning(f"⚠️ {suspicious_count} fraud alerts generated for {user.username}")
        else:
            logger.info(f"✅ No suspicious activity detected for {user.username}")

        return suspicious_count

    except Exception as e:
        logger.error(f"❌ Fraud detection failed for {user.username}: {e}", exc_info=True)
        return 0

# -------------------------------
# 🧠 FRAUD DETECTION
# -------------------------------
def check_and_flag_fraud(user, tx, source="gmail"):
    try:
        if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
            logger.warning("⚠️ Fraud model or scaler not found, skipping ML-based checks.")
            return (False, 0.0)

        fraud_model = joblib.load(MODEL_PATH)
        scaler = joblib.load(SCALER_PATH)

        amount = float(tx.amount or 0)
        category = (tx.description or 'uncategorized').lower()
        transaction_type = 'uncategorized'

        features = {
            'amount_log': np.log1p(amount),
            'category_payment': 0, 'category_purchase': 0, 'category_withdrawal': 0,
            'category_transfer': 0, 'category_uncategorized': 0,
            'transaction_type_credit': 0, 'transaction_type_debit': 0, 'transaction_type_uncategorized': 0,
        }

        cat_key = f"category_{category}"
        if cat_key in features:
            features[cat_key] = 1
        else:
            features['category_uncategorized'] = 1

        X = pd.DataFrame([features])[EXPECTED_FEATURES]
        X[['amount_log']] = scaler.transform(X[['amount_log']])

        prob = fraud_model.predict_proba(X)[0][1]
        if prob > 0.6:
            tx.is_fraud = True
            tx.save(update_fields=['is_fraud'])
            logger.warning(f"🚨 Fraud detected for {user.username}, TX {tx.id}, prob={prob:.2f}")
        return (prob > 0.6, prob)
    except Exception as e:
        logger.error(f"❌ Fraud detection failed: {e}")
        return (False, 0.0)


# -------------------------------
# 📧 GET GMAIL PROFILE
# -------------------------------
def get_gmail_profile(user):
    try:
        creds = get_gmail_credentials(user)
        if not creds:
            return None
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        return {
            "emailAddress": profile.get("emailAddress"),
            "messagesTotal": profile.get("messagesTotal"),
            "threadsTotal": profile.get("threadsTotal"),
        }
    except Exception as e:
        logger.error(f"❌ Error fetching Gmail profile: {e}")
        return None


# -------------------------------
# 🔐 OTP HANDLING
# -------------------------------
def generate_and_send_otp(email):
    otp_code = str(random.randint(100000, 999999))
    user = User.objects.get(email=email)
    OTPVerification.objects.filter(user=user).delete()
    OTPVerification.objects.create(user=user, otp_code=otp_code)

    send_mail(
        subject="Your OTP Code",
        message=f"Your OTP is {otp_code}. It is valid for 10 minutes.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
    logger.info(f"✅ OTP {otp_code} sent to {email}")


def verify_otp(email, entered_otp):
    try:
        user = User.objects.get(email=email)
        otp_obj = OTPVerification.objects.filter(user=user).order_by("-created_at").first()
        if not otp_obj:
            return False
        if timezone.now() - otp_obj.created_at > timedelta(minutes=10):
            otp_obj.delete()
            return False
        if otp_obj.otp_code == entered_otp:
            otp_obj.delete()
            return True
        return False
    except Exception as e:
        logger.error(f"⚠️ OTP verification failed for {email}: {e}")
        return False

# -------------------------------
# 💡 FINANCIAL SUGGESTIONS
# -------------------------------
def generate_suggestions(profile, transactions=None):
    # (same as your current version, unchanged)
    suggestions = []
    income = float(profile.get("income", 0))
    expenses = float(profile.get("expenses", 0))
    goal = float(profile.get("monthly_savings_goal", 0))
    debts = float(profile.get("debts", 0))
    risk = profile.get("risk_tolerance", "medium").lower()
    available = income - expenses

    if expenses > income:
        suggestions.append("⚠️ Your expenses exceed your income. Reduce non-essential spending.")
    else:
        suggestions.append("✅ Your spending is under control relative to your income.")

    if available < goal:
        suggestions.append(f"⚠️ You’re saving ₹{available:,.2f}, below your goal of ₹{goal:,.2f}.")
    else:
        suggestions.append(f"✅ You can save ₹{available:,.2f} this month.")

    if debts > 0:
        suggestions.append(f"⚠️ You have debts of ₹{debts:,.2f}. Focus on high-interest ones first.")
    else:
        suggestions.append("✅ You’re debt-free. Great job!")

    if available > 0:
        if risk == "low":
            suggestions.append(f"💡 Invest ₹{available:,.2f} in fixed deposits or bonds.")
        elif risk == "medium":
            suggestions.append(f"💡 Diversify: ₹{available*0.5:,.2f} in mutual funds, ₹{available*0.5:,.2f} in safe assets.")
        elif risk == "high":
            suggestions.append(f"💡 Aggressive: ₹{available*0.7:,.2f} in equities, ₹{available*0.3:,.2f} in stable funds.")

    if transactions:
        seen_expenses = set()
        for txn in transactions:
            amt = txn.get("amount", 0)
            cat = txn.get("category", "Uncategorized")
            if amt > 100000 and (cat, amt) not in seen_expenses:
                suggestions.append(f"⚠️ Large transaction detected: ₹{amt:,.2f} — {cat}. Review if necessary.")
                seen_expenses.add((cat, amt))
            elif 20000 < amt <= 100000 and (cat, amt) not in seen_expenses:
                suggestions.append(f"💡 Notable expense: ₹{amt:,.2f} in {cat}. Check your budget.")
                seen_expenses.add((cat, amt))
    else:
        suggestions.append("💡 No unusual transactions detected recently.")

    suggestions.append("💡 Review your finances monthly and rebalance investments.")
    return suggestions


# -------------------------------
# 📧 GET GMAIL PROFILE
# -------------------------------

# ===============================
# 🤖 AUTO FRAUD SCAN + ALERT
# ===============================
from django.core.mail import send_mail
from django.conf import settings

def analyze_and_notify_fraud(user):
    """
    Fetch Gmail transactions, detect fraud, and send user an email summary.
    Runs automatically both locally and on Render.
    """
    from users.utils import fetch_recent_transactions, check_and_flag_fraud
    from users.models import GmailTransaction

    transactions = fetch_recent_transactions(user, max_results=10)
    if not transactions:
        return f"No transactions found for {user.username}"

    frauds, safe = [], []
    for tx in transactions:
        is_fraud, prob = check_and_flag_fraud(user, tx)
        if is_fraud:
            frauds.append((tx, prob))
        else:
            safe.append((tx, prob))

    # 📨 Prepare email report
    subject = "🔍 Transaction Fraud Report"
    body = [f"Hi {user.username},", "", "Here’s the latest analysis of your Gmail transactions:"]

    if frauds:
        body.append("\n🚨 Potential Fraudulent Transactions:")
        for tx, prob in frauds:
            body.append(f"• {tx.description} — ₹{tx.amount:,.2f} ({prob*100:.1f}% fraud probability)")
            if getattr(tx, 'gmail_link', None):
                body.append(f"  Link: {tx.gmail_link}")
    else:
        body.append("\n✅ No fraudulent transactions detected. All look safe!")

    if safe:
        body.append("\n💰 Safe Transactions:")
        for tx, prob in safe[:5]:
            body.append(f"• {tx.description} — ₹{tx.amount:,.2f} ({(1-prob)*100:.1f}% safe confidence)")

    body.append("\nBest regards,\nYour Financial Security Assistant 🤖")

    message = "\n".join(body)

    # ✉️ Send email to user
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception as e:
        print(f"❌ Failed to send fraud report email for {user.username}: {e}")

    print(f"✅ Fraud scan complete for {user.username}: {len(frauds)} flagged, {len(safe)} safe.")
    return f"{len(frauds)} fraud(s), {len(safe)} safe."


from users.models import GmailTransaction
import base64
from bs4 import BeautifulSoup

def refresh_existing_gmail_transactions(user):
    """
    Re-scan GmailTransaction records for a given user.
    - Updates missing amounts using the actual Gmail message body.
    - Generates Gmail web links.
    - Runs fraud detection on every transaction.
    """
    service = get_gmail_service(user)
    updated = 0
    transactions = GmailTransaction.objects.filter(user=user)

    for txn in transactions:
        # Skip if we already have amount and fraud status
        if txn.amount and txn.amount != 0 and txn.gmail_link:
            continue  

        if not txn.message_id:
            print(f"⚠️ Skipping {txn.subject} (no message_id)")
            continue  

        try:
            # ✅ Fetch the email message from Gmail API
            msg = service.users().messages().get(
                userId="me",
                id=txn.message_id,
                format="full"
            ).execute()

            # ✅ Decode body (handles multipart emails)
            body = ""
            parts = msg["payload"].get("parts", [])
            if not parts:
                data = msg["payload"]["body"].get("data")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            else:
                for part in parts:
                    data = part.get("body", {}).get("data")
                    if data:
                        text = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        body += text

            # ✅ Clean HTML to plain text
            soup = BeautifulSoup(body, "html.parser")
            clean_text = soup.get_text(separator=" ")

            # ✅ Extract amount
            new_amount = extract_amount_from_text(clean_text)

            # ✅ Generate Gmail web link
            gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{txn.message_id}"

            # ✅ Update transaction record
            if not txn.amount or txn.amount == 0:
                txn.amount = new_amount
            if not txn.gmail_link:
                txn.gmail_link = gmail_link

            txn.save(update_fields=["amount", "gmail_link"])

            # ✅ Run fraud detection (new addition)
            detect_fraudulent_transaction(txn)

            updated += 1
            print(f"✅ Updated '{txn.subject}' → ₹{txn.amount}")

        except Exception as e:
            print(f"⚠️ Error fetching message {txn.message_id}: {e}")
            continue

    print(f"✅ Updated {updated} Gmail transactions for {user.username}.")

import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from users.models import GmailCredential  # ✅ use GmailCredential instead of GmailToken

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service(user):
    """Return authenticated Gmail service for a user."""
    try:
        creds_obj = GmailCredential.objects.get(user=user)

        creds = Credentials(
            token=creds_obj.access_token,
            refresh_token=creds_obj.refresh_token,
            token_uri=creds_obj.token_uri,
            client_id=creds_obj.client_id,
            client_secret=creds_obj.client_secret,
            scopes=SCOPES,
        )

        # Refresh the token if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        service = build("gmail", "v1", credentials=creds)
        return service

    except GmailCredential.DoesNotExist:
        raise Exception("⚠ No Gmail credentials found. Please reconnect Gmail.")


# users/utils.py
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings

def detect_fraudulent_transaction(txn):
    """
    Advanced fraud detection logic for Gmail transactions.
    Evaluates sender domain, amount, keywords, time, and duplicates.
    If marked as fraud, it sends an alert email and logs a FraudAlert entry.
    """
    from users.models import GmailTransaction, FraudAlert  # ✅ ensure both models are imported here
    reasons = []

    try:
        # --- Rule 1: Amount checks ---
        if txn.amount is not None:
            if txn.amount == 0:
                reasons.append("Transaction with ₹0 amount")
            elif txn.amount > 1_000_000:
                reasons.append(f"Unusually high amount: ₹{txn.amount:,.2f}")
        else:
            reasons.append("Missing transaction amount")

        # --- Rule 2: Suspicious or unverified sender domain ---
        trusted_domains = (
            "@hdfcbank.com", "@icicibank.com", "@sbi.co.in",
            "@axisbank.com", "@kotak.com", "@yesbank.in",
            "@bankofbaroda.com", "@canarabank.com", "@indusind.com",
            "@idfcfirstbank.com", "@unionbankofindia.com"
        )
        if txn.sender:
            sender_lower = txn.sender.lower()
            if not sender_lower.endswith(trusted_domains):
                reasons.append(f"Unverified or suspicious sender: {txn.sender}")
        else:
            reasons.append("Missing sender information")

        # --- Rule 3: Invalid transaction type ---
        valid_types = ["credit", "debit"]
        if not txn.transaction_type or txn.transaction_type.lower() not in valid_types:
            reasons.append("Invalid or missing transaction type")

        # --- Rule 4: Suspicious subject keywords ---
        suspicious_keywords = [
            "lottery", "urgent", "refund", "verification", "password",
            "alert", "click", "prize", "reward", "verify account",
            "suspended", "win", "gift", "money transfer", "limited time"
        ]
        if txn.subject:
            subject_lower = txn.subject.lower()
            for keyword in suspicious_keywords:
                if keyword in subject_lower:
                    reasons.append(f"Suspicious keyword found: '{keyword}'")
                    break
        else:
            reasons.append("Missing email subject")

        # --- Rule 5: Odd transaction timing ---
        if txn.date:
            local_dt = txn.date.astimezone(timezone.get_current_timezone())
            hour = local_dt.hour
            if hour < 6 or hour > 23:
                reasons.append(f"Transaction at odd hour ({hour}:00)")
        else:
            reasons.append("Missing transaction date")

        # --- Rule 6: Duplicate transaction ---
        if GmailTransaction.objects.filter(
            user=txn.user,
            amount=txn.amount,
            sender=txn.sender
        ).exclude(id=txn.id).exists():
            reasons.append("Duplicate transaction detected with same sender and amount")

        # --- Final Decision ---
        txn.is_fraud = bool(reasons)
        txn.fraud_reason = "; ".join(reasons) if reasons else None

        with transaction.atomic():
            txn.save(update_fields=["is_fraud", "fraud_reason"])

        # --- If fraud detected ---
        if txn.is_fraud:
            # 🚨 1. Send email alert
            email_subject = "⚠️ Fraud Alert: Suspicious Transaction Detected"
            email_message = (
                f"Dear {txn.user.username},\n\n"
                f"A potentially fraudulent transaction has been detected:\n\n"
                f"Subject: {txn.subject}\n"
                f"Amount: ₹{txn.amount:,.2f}\n"
                f"Sender: {txn.sender}\n\n"
                f"Reason(s): {txn.fraud_reason}\n\n"
                f"You can review it here:\n"
                f"{txn.gmail_link or 'Gmail link unavailable'}\n\n"
                f"If this transaction was not made by you, please contact your bank immediately.\n\n"
                f"Stay safe,\nYour Financial Security Assistant 🤖"
            )

            send_mail(
                subject=email_subject,
                message=email_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[txn.user.email],
                fail_silently=True,
            )

            # 💾 2. Log to FraudAlert model for dashboard
            FraudAlert.objects.create(
                user=txn.user,
                transaction=txn,
                title="Suspicious Transaction Detected",
                message=(
                    f"A transaction appears suspicious:\n\n"
                    f"Subject: {txn.subject}\n"
                    f"Amount: ₹{txn.amount:,.2f}\n"
                    f"Sender: {txn.sender}\n\n"
                    f"Reason(s): {txn.fraud_reason}\n"
                )
            )

            print(f"🚨 Fraud alert email + dashboard alert logged for '{txn.subject}' ({txn.user.username})")

        else:
            print(f"✅ Transaction '{txn.subject}' looks safe.")

        return txn.is_fraud

    except Exception as e:
        print(f"⚠️ Error during fraud detection for '{getattr(txn, 'subject', 'Unknown')}': {e}")
        return False

# ✅ keep this earlier in the file
def fraud_detect_transaction(transaction):
    suspicious_keywords = [
        "lottery", "urgent", "refund", "verification", "password",
        "alert", "click", "prize", "reward", "verify account",
        "suspended", "win", "gift", "money transfer", "limited time"
    ]
    text = (transaction.subject + " " + transaction.snippet).lower()
    return any(word in text for word in suspicious_keywords)



import logging

logger = logging.getLogger(__name__)
def run_auto_gmail_and_fraud_cycle():
    """
    Automatically fetches Gmail transactions for all users with valid Gmail credentials,
    saves new transactions, and runs fraud detection + email alerts.
    Designed to be run by Django Q scheduler (qcluster).
    """
    import traceback
    from django.contrib.auth import get_user_model
    from users.models import GmailCredential
    from users.utils import (
        get_gmail_service,
        fetch_recent_transactions,
        save_transactions_to_db,
        detect_and_alert_fraud,
    )

    print("⏳ Starting Gmail + fraud auto-detection cycle...")

    User = get_user_model()
    users = User.objects.all()

    for user in users:
        print(f"🔍 Processing user: {user.username}")

        try:
            # ✅ Skip users without Gmail credentials
            if not GmailCredential.objects.filter(user=user).exists():
                print(f"⚠ Skipping {user.username} — no Gmail credentials found.")
                continue

            # ✅ Fetch Gmail transactions
            print("📬 Fetching Gmail transactions...")
            transactions = fetch_recent_transactions(user, max_results=10)
            print(f"📦 Retrieved {len(transactions)} potential transaction emails.")

            if not transactions:
                print(f"📭 No new Gmail transaction emails for {user.username}.")
                continue

            # ✅ Save to DB (avoids duplicates)
            saved_count = save_transactions_to_db(user, transactions)
            print(f"💾 {saved_count} new transactions saved for {user.username}.")

            # ✅ Run fraud detection + alerting
            alerts = detect_and_alert_fraud(user)
            if alerts:
                print(f"🚨 {alerts} suspicious transactions found for {user.username}.")
            else:
                print(f"✅ No suspicious activity detected for {user.username}.")

        except Exception as e:
            print(f"❌ Error while processing {user.username}: {e}")
            traceback.print_exc()

    print("✅ Gmail + fraud detection cycle completed successfully.\n")
