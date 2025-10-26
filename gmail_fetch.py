import imaplib
import email
from email.header import decode_header
import re

USER_EMAIL = "finsecure7@gmail.com"
APP_PASSWORD = "ogza uwde pikq mvzr"

CATEGORIES = {
    "Food": ["swiggy", "zomato", "dominos", "pizza", "ubereats"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio"],
    "Travel": ["uber", "ola", "rapido", "makemytrip"],
    "Bills": ["electricity", "gas", "recharge", "airtel", "jio", "vodafone"],
    "Bank": ["sbi", "hdfc", "icici", "axis", "kotak"],
}

# only check mails with these words
TRANSACTION_KEYWORDS = ["debited", "credited", "transaction", "spent", "purchase", "payment", "bill", "paid"]

def categorize_transaction(text):
    text = text.lower()
    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "Others"

def fetch_transactions():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(USER_EMAIL, APP_PASSWORD)
        mail.select("inbox")

        status, messages = mail.search(None, "ALL")
        email_ids = messages[0].split()[-50:]  # check last 50 mails

        transactions = []

        for e_id in email_ids:
            _, msg_data = mail.fetch(e_id, "(RFC822)")
            raw_msg = msg_data[0][1]
            msg = email.message_from_bytes(raw_msg)

            subject, encoding = decode_header(msg["Subject"])[0]
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

            full_text = subject + " " + body
            if not any(keyword in full_text.lower() for keyword in TRANSACTION_KEYWORDS):
                continue  # skip non-transaction mails

            match = re.findall(r"(?:Rs\.?|INR|₹)\s?([0-9,]+)", full_text)
            amounts = []
            for m in match:
                amt = int(m.replace(",", ""))
                if amt > 50:  # filter out junk like Rs 3, Rs 6
                    amounts.append(amt)

            if not amounts:
                continue

            category = categorize_transaction(full_text)
            transactions.append({
                "subject": subject,
                "amounts": amounts,
                "category": category
            })

        mail.logout()
        return transactions

    except Exception as e:
        print("Error:", str(e))
        return []

if __name__ == "__main__":
    txns = fetch_transactions()
    if not txns:
        print("No recent transactions found.")
    else:
        print("\n--- Recent Transactions ---")
        summary = {}
        for t in txns:
            print(f"📩 {t['subject']} → {t['amounts']} | Category: {t['category']}")
            total = sum(t["amounts"])
            summary[t["category"]] = summary.get(t["category"], 0) + total

        print("\n--- Spending Summary ---")
        for cat, amt in summary.items():
            print(f"{cat}: ₹{amt}")
