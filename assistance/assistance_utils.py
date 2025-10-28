import threading
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

def send_assistance_email(subject, message, to_email):
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
        logger.info(f"Assistance email sent to {to_email}")
    except Exception as e:
        logger.error(f"Error sending assistance email: {e}")

def send_assistance_email_async(subject, message, to_email):
    threading.Thread(target=send_assistance_email, args=(subject, message, to_email)).start()
