import sendgrid
from sendgrid.helpers.mail import Mail
import os

def send_otp_via_sendgrid(email, otp):
    sg = sendgrid.SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
    message = Mail(
        from_email="finsecure7@gmail.com",
        to_emails=email,
        subject="Your Login OTP",
        plain_text_content=f"Your OTP is: {otp}"
    )
    response = sg.send(message)
    return response
