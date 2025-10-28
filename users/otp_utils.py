import os
import threading
import logging
import sendgrid
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)

def send_otp_via_sendgrid(email, otp):
    try:
        sg = sendgrid.SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
        message = Mail(
            from_email=os.environ.get("DEFAULT_FROM_EMAIL"),
            to_emails=email,
            subject="Your OTP Code",
            plain_text_content=f"Your OTP is: {otp}"
        )
        response = sg.send(message)
        logger.info(f"OTP sent to {email} with status {response.status_code}")
        return response.status_code
    except Exception as e:
        logger.error(f"Error sending OTP email: {e}")
        return None

def send_otp_email_async(email, otp):
    threading.Thread(target=send_otp_via_sendgrid, args=(email, otp)).start()