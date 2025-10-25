# users/utils.py

import re
import base64
import json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from assistance.models import GmailCredential   # ✅ use the one that actually has the data

from transactions.models import Transaction


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


# -------------------------------
# 📧 FETCH LATEST EMAILS
# -------------------------------
def fetch_latest_emails(user, max_results=5):
    """
    Fetch the latest Gmail emails for a user (non-transactional).
    Returns a list of dicts with subject, from, date, and snippet.
    """
    try:
        cred_obj = GmailCredential.objects.get(user=user)
        token_data = cred_obj.token
        if isinstance(token_data, str):
            token_data = json.loads(token_data)

        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(
            userId="me", maxResults=max_results
        ).execute()

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

        return emails

    except GmailCredential.DoesNotExist:
        print("⚠️ No Gmail credentials found for user.")
        return []
    except Exception as e:
        print(f"❌ Error fetching latest emails: {e}")
        return []


# -------------------------------
# 💰 FETCH RECENT TRANSACTIONS
# -------------------------------
def fetch_recent_transactions(user, max_results=25):
    """
    Fetch recent Gmail transaction-like emails and extract structured transaction data.
    """
    try:
        cred_obj = GmailCredential.objects.get(user=user)
        token_data = cred_obj.token
        if isinstance(token_data, str):
            token_data = json.loads(token_data)

        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        service = build("gmail", "v1", credentials=creds)

        results = service.users().messages().list(
            userId="me",
            maxResults=max_results,
            q="transaction OR Amount OR debited OR credited",
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            print(f"⚠️ No transaction-like emails found for {user.username}.")
            return []

        transactions, seen_keys = [], set()

        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()

            payload = msg_data.get("payload", {})
            parts = payload.get("parts", [])
            body_text = msg_data.get("snippet", "")

            for part in parts:
                data = part.get("body", {}).get("data")
                if data:
                    try:
                        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        body_text += " " + decoded
                    except Exception:
                        continue

            text = re.sub(r"\s+", " ", body_text).strip()

            amt_match = re.search(r"Amount[:=\-]?\s*[₹$€]?\s?([\d,]+(?:\.\d{1,2})?)", text, re.I)
            cat_match = re.search(
                r"Category[:=\-]?\s*([A-Za-z ]+?)(?=\s*(?:Transaction\s*Type|Type|Date|Amount|₹|$))",
                text,
                re.I,
            )
            type_match = re.search(r"(?:Transaction\s*Type|Type)[:=\-]?\s*([A-Za-z]+)", text, re.I)
            date_match = re.search(r"Date[:=\-]?\s*([\d/\-\s:APMapm]+)", text, re.I)

            amount = float(amt_match.group(1).replace(",", "")) if amt_match else 0.0
            category = cat_match.group(1).strip() if cat_match else ""
            txn_type = type_match.group(1).strip().lower() if type_match else ""
            date = date_match.group(1).strip() if date_match else ""

            category = re.sub(r"(?i)\b(transaction\s*type|txn\s*type|trans\s*type|type)\b", "", category)
            category = category.replace("  ", " ").strip().capitalize()
            date = re.sub(r"(\d{4})-0+(\d{1,2})", r"\1-\2", date)

            # ✅ Infer missing category intelligently
            if not category or category.lower() in ["", "uncategorized", "transaction type"]:
                if re.search(r"\bcredited\b|\bdeposit(ed)?\b|\bincome\b", text, re.I):
                    category = "Deposit"
                    txn_type = txn_type or "credit"
                elif re.search(r"\bdebited\b|\bwithdraw(al|n)?\b|\bpayment\b|\bpurchase\b|\bsent\b", text, re.I):
                    category = "Withdrawal"
                    txn_type = txn_type or "debit"
                elif re.search(r"\btransfer\b|\bupi\b|\bimps\b|\bneft\b", text, re.I):
                    category = "Transfer"
                elif re.search(r"\brefund\b", text, re.I):
                    category = "Refund"
                else:
                    category = "Uncategorized"

            txn_key = f"{amount}-{category}-{date}"
            if txn_key in seen_keys or not amount:
                continue
            seen_keys.add(txn_key)

            transactions.append({
                "amount": amount,
                "category": category,
                "transaction_type": txn_type,
                "date": date,
                "currency": "₹",
            })

        print(f"✅ Parsed {len(transactions)} transaction(s) for {user.username}.")
        return transactions

    except GmailCredential.DoesNotExist:
        print("⚠️ No Gmail credentials found for user.")
        return []
    except Exception as e:
        print(f"❌ Error fetching transactions: {e}")
        return []


# -------------------------------
# 💾 SAVE TRANSACTIONS TO DB
# -------------------------------
def save_transactions_to_db(user, transactions):
    """
    Save fetched transactions into the database while avoiding duplicates.
    Automatically capitalizes category names.
    """
    saved_count = 0
    for txn in transactions:
        amount = txn.get("amount")
        category = txn.get("category", "").capitalize().strip()
        txn_type = txn.get("transaction_type", "").lower()
        date = txn.get("date")
        currency = txn.get("currency", "₹")

        if Transaction.objects.filter(user=user, amount=amount, category=category, timestamp__date=date).exists():
            continue

        Transaction.objects.create(
            user=user,
            amount=amount,
            category=category,
            transaction_type=txn_type,
            description=f"{category} transaction ({txn_type}) of {currency}{amount}",
        )
        saved_count += 1

    print(f"💾 Saved {saved_count} new transactions for {user.username}.")
    return saved_count


# -------------------------------
# 💡 FINANCIAL SUGGESTIONS
# -------------------------------
def generate_suggestions(profile, transactions=None):
    """
    Generate personalized financial suggestions.
    """
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
            suggestions.append(f"💡 Aggressive strategy: ₹{available*0.7:,.2f} in equities, ₹{available*0.3:,.2f} in stable funds.")

    if transactions:
        seen_expenses = set()
        for txn in transactions:
            amt = txn.get("amount", 0)
            cat = txn.get("category", "Uncategorized")
            if amt > 100000 and (cat, amt) not in seen_expenses:
                suggestions.append(f"⚠️ Large transaction detected: ₹{amt:,.2f} — {cat}. Review if necessary.")
                seen_expenses.add((cat, amt))
            elif 20000 < amt <= 100000 and (cat, amt) not in seen_expenses:
                suggestions.append(f"💡 Notable expense: ₹{amt:,.2f} in {cat}. Check if it fits your budget.")
                seen_expenses.add((cat, amt))
    else:
        suggestions.append("💡 No unusual transactions detected recently.")

    suggestions.append("💡 Review your finances monthly and rebalance investments.")
    return suggestions

# -------------------------------
# 📧 GET GMAIL PROFILE
# -------------------------------
def get_gmail_profile(user):
    """
    Return Gmail profile information (like the connected Gmail address)
    for the given user based on their stored credentials.
    """

    try:
        cred_obj = GmailCredential.objects.get(user=user)
        token_data = cred_obj.token
        if isinstance(token_data, str):
            token_data = json.loads(token_data)

        creds = Credentials.from_authorized_user_info(token_data, SCOPES)
        service = build("gmail", "v1", credentials=creds)

        profile = service.users().getProfile(userId="me").execute()
        return {
            "emailAddress": profile.get("emailAddress"),
            "messagesTotal": profile.get("messagesTotal"),
            "threadsTotal": profile.get("threadsTotal"),
        }

    except GmailCredential.DoesNotExist:
        print("⚠️ No Gmail credentials found for user.")
        return None
    except Exception as e:
        print(f"❌ Error fetching Gmail profile: {e}")
        return None
