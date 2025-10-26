from django.core.mail import send_mail
import logging
import os

def send_otp_via_sendgrid(to_email, otp):
    """
    Sends OTP email via SendGrid SMTP.
    Returns True on success, False on failure.
    """
    subject = "Your Login OTP Code"
    message = f"Your OTP code is {otp}. It is valid for 5 minutes."
    from_email = os.getenv('DEFAULT_FROM_EMAIL', 'finsecure7@gmail.com')

    try:
        send_mail(
            subject,
            message,
            from_email,
            [to_email],
            fail_silently=False,
        )
        logging.info(f"OTP sent successfully to {to_email}")
        return True
    except Exception as e:
        logging.error(f"Failed to send OTP to {to_email}: {e}", exc_info=True)
        return False
