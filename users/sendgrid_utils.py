import os
import sendgrid
from sendgrid.helpers.mail import Mail

def send_otp_via_sendgrid(email, otp):
    sg = sendgrid.SendGridAPIClient(api_key=os.getenv("SENDGRID_API_KEY"))
    message = Mail(
        from_email="finsecure7@gmail.com",  # Your verified SendGrid sender email
        to_emails=email,
        subject="Your Login OTP",
        plain_text_content=f"Your OTP for login is: {otp}\n\n(Valid for 5 minutes)",
    )
    response = sg.send(message)
    return response.status_code  # 202 means email accepted by SendGrid
