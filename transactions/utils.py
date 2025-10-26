from django.core.mail import send_mail
from django.conf import settings
import threading
import logging


def send_fraud_alert_email(user_email, transaction_info):
    """
    Send fraud alert email asynchronously to prevent blocking
    """
    def _send_email():
        subject = 'Urgent: Fraud Alert on Your Account'
        message = (
            f"Dear Customer,\n\n"
            f"We detected a suspicious transaction on your account:\n\n"
            f"{transaction_info}\n\n"
            f"If this was not authorized by you, please contact our support immediately.\n\n"
            f"Best regards,\nYour Bank Security Team"
        )
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user_email]
        
        try:
            send_mail(
                subject, 
                message, 
                from_email, 
                recipient_list, 
                fail_silently=True,
                timeout=10  # Prevent hanging
            )
            logging.info(f"Fraud alert email sent to {user_email}")
        except Exception as e:
            logging.error(f"Fraud email failed for {user_email}: {e}")
    
    # Send email in background thread
    email_thread = threading.Thread(target=_send_email)
    email_thread.daemon = True
    email_thread.start()
