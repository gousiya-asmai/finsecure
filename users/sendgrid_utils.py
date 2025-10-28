import sendgrid
import os
from sendgrid.helpers.mail import Mail

def send_otp_via_sendgrid(email, otp):
    """
    Send OTP email via SendGrid
    
    Args:
        email (str): recipient email address
        otp (str): one time password to send
    
    Returns:
        int: HTTP response status code from SendGrid API call
    """
    try:
        sg = sendgrid.SendGridAPIClient(api_key=os.environ.get("SENDGRID_API_KEY"))
        message = Mail(
            from_email=os.environ.get("DEFAULT_FROM_EMAIL", "finsecure7@gmail.com"),  # use verified sender email here
            to_emails=email,
            subject="Your OTP Code",
            plain_text_content=f"Your OTP is: {otp}"
        )
        response = sg.send(message)
        print(f"SendGrid response code: {response.status_code}")
        print(f"SendGrid response body: {response.body}")
        return response.status_code

    except Exception as e:
        print(f"Exception sending OTP via SendGrid: {e}")
        return None
