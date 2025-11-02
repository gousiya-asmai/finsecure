from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_fraud_alert_email(user_email, transaction_info, user_name=None):
    """
    Send fraud alert email using Django's SMTP backend (Gmail)
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

For assistance, visit: http://127.0.0.1:8080/assistance/dashboard/

Stay Safe,  
FinSecure Security Team
"""

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )
        logger.info(f"✅ Fraud alert email sent successfully to {user_email}")
        return True

    except Exception as e:
        logger.error(f"❌ Email sending failed: {str(e)}", exc_info=True)
        return False
