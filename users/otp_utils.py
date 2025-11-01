import os
import logging
import threading
import random
import time
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from django.core.cache import cache

logger = logging.getLogger(__name__)

# OTP validity period (in seconds)
OTP_EXPIRY_SECONDS = 600  # 10 minutes


# -------------------- Helper: Generate OTP --------------------
def _generate_otp():
    """Generate a random 6-digit OTP."""
    return str(random.randint(100000, 999999))


# -------------------- Helper: Send Email via SendGrid REST API --------------------
def _send_email_via_sendgrid(to_email, subject, message):
    """Send email directly using SendGrid REST API for speed."""
    api_key = os.getenv("SENDGRID_API_KEY")
    if not api_key:
        logger.error("❌ SENDGRID_API_KEY not found in environment.")
        raise ValueError("SENDGRID_API_KEY missing")

    from_email = os.getenv("DEFAULT_FROM_EMAIL", "finsecure7@gmail.com")
    mail = Mail(from_email=from_email, to_emails=to_email, subject=subject, html_content=message)

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(mail)
        logger.info(f"✅ Email sent to {to_email}, status code: {response.status_code}")
        return response.status_code
    except Exception as e:
        logger.exception(f"❌ SendGrid send failed: {e}")
        raise


# -------------------- Generate & Send OTP --------------------
def generate_and_send_otp(email):
    """Generate an OTP, store it with expiry, and send it via SendGrid."""
    otp = _generate_otp()
    expiry = datetime.now() + timedelta(seconds=OTP_EXPIRY_SECONDS)

    # Store OTP and expiry in cache (keyed by email)
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

    # Send asynchronously
    threading.Thread(target=_send_email_via_sendgrid, args=(email, subject, html_message)).start()
    logger.info(f"📧 OTP {otp} generated and email thread started for {email}")

    return otp


# -------------------- Verify OTP --------------------
def verify_otp(email, entered_otp):
    """Check if the entered OTP matches the cached one and is not expired."""
    data = cache.get(f"otp_{email}")
    if not data:
        logger.warning(f"⚠ OTP expired or not found for {email}")
        return False

    cached_otp = data.get("otp")
    expiry = data.get("expiry")

    if datetime.now() > expiry:
        logger.warning(f"⚠ OTP expired for {email}")
        cache.delete(f"otp_{email}")
        return False

    if entered_otp == cached_otp:
        logger.info(f"✅ OTP verified successfully for {email}")
        cache.delete(f"otp_{email}")  # Delete OTP after use
        return True

    logger.warning(f"❌ Invalid OTP attempt for {email}")
    return False
