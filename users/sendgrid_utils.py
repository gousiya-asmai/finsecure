from django.core.mail import send_mail
import logging
import os

def send_otp_via_sendgrid(to_email, otp):
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
        return True  # Success
    except Exception as e:
        logging.error(f"SendGrid email send failed: {e}", exc_info=True)
        return False  # Failure
