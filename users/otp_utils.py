import os
import logging
import random
import threading
from datetime import datetime, timedelta
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

logger = logging.getLogger(__name__)

OTP_EXPIRY_SECONDS = 600  # 10 minutes


# -------------------- Helper: Generate OTP --------------------
def _generate_otp():
    """Generate a random 6-digit OTP."""
    return str(random.randint(100000, 999999))


# -------------------- Helper: Send Email via SendGrid --------------------
def _send_email_via_sendgrid(to_email, subject, html_message):
    """Send email using SendGrid REST API (fast + reliable)."""
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        raise ValueError("SENDGRID_API_KEY missing")

    from_email = os.getenv("DEFAULT_FROM_EMAIL", "finsecure7@gmail.com")
    mail = Mail(from_email=from_email, to_emails=to_email, subject=subject, html_content=html_message)

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(mail)
        logger.info(f"✅ [SendGrid] Email sent to {to_email}, status {response.status_code}")
        return response.status_code
    except Exception as e:
        logger.exception(f"❌ [SendGrid] send failed: {e}")
        return None


# -------------------- Background Email Thread --------------------
def _send_email_background(func, *args):
    """Run email sending in a separate thread to avoid blocking."""
    thread = threading.Thread(target=func, args=args, daemon=True)
    thread.start()


# -------------------- Generate & Send OTP --------------------
def generate_and_send_otp(email):
    """Generate OTP, store it, and send email asynchronously."""
    otp = _generate_otp()
    expiry = datetime.now() + timedelta(seconds=OTP_EXPIRY_SECONDS)

    # Save OTP in cache (fast)
    cache.set(f"otp_{email}", {"otp": otp, "expiry": expiry}, timeout=OTP_EXPIRY_SECONDS)

    subject = "🔐 Your FinSecure OTP Code"
    html_message = f"""
    <div style='font-family:Arial,sans-serif;background:#f8f9fa;padding:20px;border-radius:8px'>
        <h2 style='color:#007BFF;'>FinSecure Verification</h2>
        <p>Your One-Time Password (OTP) is:</p>
        <h1 style='color:#28a745;font-size:32px'>{otp}</h1>
        <p>This OTP is valid for <b>10 minutes</b>.</p>
        <p style='font-size:12px;color:gray'>If you didn’t request this, you can safely ignore this email.</p>
    </div>
    """

    # 🔄 Send mail in background thread for instant response
    def send_otp_email():
        try:
            if settings.DEBUG:
                send_mail(
                    subject,
                    f"Your FinSecure OTP is {otp}. Valid for 10 minutes.",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                logger.info(f"✅ [Local/Gmail] OTP sent to {email}")
            else:
                _send_email_via_sendgrid(email, subject, html_message)
        except Exception as e:
            logger.error(f"❌ Email send failed for {email}: {e}", exc_info=True)

    _send_email_background(send_otp_email)
    logger.info(f"📨 OTP thread started for {email}")

    return otp


# -------------------- Verify OTP --------------------
def verify_otp(email, entered_otp):
    """Instant OTP verification from cache."""
    data = cache.get(f"otp_{email}")
    if not data:
        logger.warning(f"⚠️ OTP expired or not found for {email}")
        return False

    cached_otp = data.get("otp")
    expiry = data.get("expiry")

    if datetime.now() > expiry:
        cache.delete(f"otp_{email}")
        logger.warning(f"⚠️ OTP expired for {email}")
        return False

    if str(entered_otp).strip() == str(cached_otp).strip():
        cache.delete(f"otp_{email}")  # one-time use
        logger.info(f"✅ OTP verified successfully for {email}")
        return True

    logger.warning(f"❌ Invalid OTP attempt for {email}")
    return False
