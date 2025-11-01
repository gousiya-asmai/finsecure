from django.conf import settings
import logging
import requests

logger = logging.getLogger(__name__)

def send_fraud_alert_email(user_email, transaction_info, user_name=None):
    """
    Send fraud alert email using SendGrid HTTP API (not SMTP)
    """
    try:
        subject = '🚨 URGENT: Fraud Alert on Your Account - FinSecure'
        
        message = f"""
Dear {user_name or 'Customer'},

⚠️ FRAUD ALERT - IMMEDIATE ATTENTION REQUIRED ⚠️

We have detected a suspicious transaction on your FinSecure account:

═══════════════════════════════════════════════════
{transaction_info}
═══════════════════════════════════════════════════

🔒 WHAT YOU SHOULD DO NOW:

1. ✅ If you recognize this transaction - No action needed
2. ❌ If you DO NOT recognize this transaction:
   • Log in to your FinSecure account immediately
   • Review the transaction details
   • Report it as fraudulent
   • Contact your bank to block your card

═══════════════════════════════════════════════════

For assistance, visit: https://finsecure-jgzx.onrender.com/assistance/dashboard/

Stay Safe,  
FinSecure Security Team
"""
        # ✅ Try SENDGRID_API_KEY first, fallback to EMAIL_HOST_PASSWORD
        api_key = getattr(settings, "SENDGRID_API_KEY", None) or getattr(settings, "EMAIL_HOST_PASSWORD", None)
        from_email = settings.DEFAULT_FROM_EMAIL

        if not api_key:
            logger.error("❌ SendGrid API key not found in settings!")
            return False

        logger.info(f"📧 Sending email via SendGrid API to {user_email}")
        url = "https://api.sendgrid.com/v3/mail/send"

        payload = {
            "personalizations": [{
                "to": [{"email": user_email}],
                "subject": subject
            }],
            "from": {"email": from_email},
            "content": [{"type": "text/plain", "value": message}],
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code == 202:
            logger.info(f"✅ Email sent successfully to {user_email} via SendGrid API")
            return True
        else:
            logger.error(f"❌ SendGrid API error {response.status_code}: {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ Email sending failed: {str(e)}", exc_info=True)
        return False
