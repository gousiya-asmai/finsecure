import imaplib
import email
import re
from email.header import decode_header

# Use the correct import — adjust 'transactions' to your app name as needed!
from transactions.models import Transaction

CATEGORIES = {
    "Food": ["swiggy", "zomato", "dominos", "pizza", "ubereats"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio"],
    "Travel": ["uber", "ola", "rapido", "makemytrip"],
    "Bills": ["electricity", "gas", "recharge", "airtel", "jio", "vodafone"],
    "Bank": ["sbi", "hdfc", "icici", "axis", "kotak"],
}

TRANSACTION_KEYWORDS = ["debited", "credited", "transaction", "spent", "purchase", "payment", "bill", "paid"]

def categorize_transaction(text):
    text = text.lower()
    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "Others"

def fetch_and_save_transactions(user, user_email, app_password):
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user_email, app_password)
        mail.select("inbox")

        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split()[-50:]  # last 50 emails

        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            raw_msg = msg_data[0][1]
            msg = email.message_from_bytes(raw_msg)

            subject, encoding = decode_header(msg.get("Subject", ""))[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else "utf-8")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="ignore")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="ignore")

            full_text = (subject or "") + " " + (body or "")

            if not any(keyword in full_text.lower() for keyword in TRANSACTION_KEYWORDS):
                continue

            # Extract amount (try both comma and dot notation)
            match = re.findall(r"(?:Rs\.?|INR|₹)\s?([\d,]+(?:\.\d{1,2})?)", full_text)
            for m in match:
                try:
                    amt = float(m.replace(",", ""))
                except Exception:
                    continue
                if amt > 50:
                    category = categorize_transaction(full_text)
                    Transaction.objects.create(
                        user=user,
                        subject=subject,
                        amount=amt,
                        category=category
                    )
        mail.logout()

    except Exception as e:
        print("Error fetching transactions:", str(e))
