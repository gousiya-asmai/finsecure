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
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth.models import User

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

from users.models import GmailCredential, GmailTransaction, OTPVerification
from transactions.models import Transaction

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
# ------------------------------

def fetch_recent_transactions(user, max_results=5):
    """
    Fetch the latest valid Gmail transaction emails (excluding fraud/alert/OTP).
    Stores them in GmailTransaction and returns the 5 most recent ones.
    """
    import re, base64, html, logging
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from .models import GmailTransaction  # adjust path if needed

    logger = logging.getLogger(__name__)

    try:
        creds = get_gmail_credentials(user)
        if not creds:
            logger.warning(f"⚠️ No Gmail credentials for {user.username}.")
            return []

        service = build("gmail", "v1", credentials=creds)

        # ✅ Fetch emails with likely transaction-related subjects
        query = "subject:(transaction OR payment OR debited OR credited OR transfer)"
        results = service.users().messages().list(userId="me", maxResults=max_results, q=query).execute()
        messages = results.get("messages", [])

        if not messages:
            logger.info(f"📭 No Gmail messages found for {user.username}.")
            return []

        new_transactions = []
        seen_ids = set(GmailTransaction.objects.filter(user=user).values_list("message_id", flat=True))

        for msg in messages:
            msg_id = msg["id"]
            if msg_id in seen_ids:
                continue  # skip duplicates

            message = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            payload = message.get("payload", {})
            headers = payload.get("headers", [])

            # Extract metadata
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "(No Subject)")
            sender = next((h["value"] for h in headers if h["name"].lower() == "from"), "(Unknown Sender)")
            date = next((h["value"] for h in headers if h["name"].lower() == "date"), "")
            snippet = message.get("snippet", "")

            # Skip fraud/alert/otp messages
            if re.search(r"fraud|alert|security|otp|unauthorized|blocked|suspicious", subject, re.I):
                logger.info(f"⚠️ Skipped non-transaction email: {subject}")
                continue

            # Extract text body
            body_text = snippet
            for part in payload.get("parts", []):
                data = part.get("body", {}).get("data")
                if data:
                    try:
                        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        if part.get("mimeType") == "text/html":
                            decoded = html.unescape(decoded)
                        body_text += " " + decoded
                    except Exception:
                        continue

            # Find transaction amount
            amt_match = re.search(r"(?:₹|INR|Rs\.?)\s?([\d,]+(?:\.\d{1,2})?)", body_text)
            amount = 0.0
            if amt_match:
                try:
                    amount = float(amt_match.group(1).replace(",", ""))
                except ValueError:
                    amount = 0.0

            # Detect transaction type
            txn_type = "credit" if re.search(r"\bcredited|received|deposit", subject, re.I) else "debit"

            # Create Gmail link
            gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{msg_id}"

            # Save transaction
            txn = GmailTransaction.objects.create(
                user=user,
                description=subject.strip(),
                amount=amount,
                currency="₹",
                transaction_type=txn_type,
                category="Deposit" if txn_type == "credit" else "Withdrawal",
                message_id=msg_id,
                gmail_link=gmail_link,
                sender=sender,
                date=date,
            )

            new_transactions.append(txn)

        logger.info(f"✅ {len(new_transactions)} Gmail transactions saved for {user.username}.")
        return new_transactions[:5]

    except HttpError as e:
        logger.error(f"❌ Gmail API error for {user.username}: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ fetch_recent_transactions error for {user.username}: {e}", exc_info=True)
        return []


# -------------------------------
# 💾 SAVE TRANSACTIONS TO DB
# -------------------------------
def save_transactions_to_db(user, transactions):
    """
    Save Gmail transactions into the database while avoiding duplicates.
    """
    saved_count = 0

    # ✅ Loop starts here — defines txn
    for txn in transactions:
        amount = txn.get("amount", 0.0)
        description = txn.get("description", "").strip() or "(No description)"
        category = txn.get("category", "Other").capitalize().strip()
        currency = txn.get("currency", "₹")
        txn_type = txn.get("transaction_type", "Unknown")
        message_id = txn.get("message_id")

        # ✅ Check for duplicates
        if GmailTransaction.objects.filter(
            user=user,
            amount=amount,
            description=description
        ).exists():
            continue

        # ✅ Save the transaction safely
        GmailTransaction.objects.create(
            user=user,
            description=description,
            amount=amount,
            currency=currency,
            category=category,
            transaction_type=txn_type,
            message_id=message_id
        )
        saved_count += 1

    # ✅ Loop ends here — txn no longer in scope
    logger.info(f"💾 Saved {saved_count} new Gmail transactions for {user.username}.")
    return saved_count




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
