import sendgrid
import os
from sendgrid.helpers.mail import Mail

def send_otp_via_sendgrid(email, otp):
    sg = sendgrid.SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
    message = Mail(
        from_email=os.environ.get("DEFAULT_FROM_EMAIL", "finsecure7@gmail.com"),  # Use your verified sender email here
        to_emails=email,
        subject="Your OTP Code",
        plain_text_content=f"Your OTP is: {otp}"
    )
    response = sg.send(message)
    print(response.status_code)
    print(response.body)
    return response.status_code
