from django.core.mail import send_mail
import logging

def send_otp_via_sendgrid(to_email, otp):
    subject = "Your Login OTP Code"
    message = f"Your OTP code is {otp}. It is valid for 5 minutes."
    from_email = 'your_verified_sendgrid_email@example.com'  # Same as above

    try:
        send_mail(
            subject,
            message,
            from_email,
            [to_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        logging.error(f"SendGrid email failed: {e}", exc_info=True)
        return False
