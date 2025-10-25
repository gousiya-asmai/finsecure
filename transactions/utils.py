from django.core.mail import send_mail
from django.conf import settings

def send_fraud_alert_email(user_email, transaction_info):
    subject = 'Urgent: Fraud Alert on Your Account'
    message = (
        f"Dear Customer,\n\n"
        f"We detected a suspicious transaction on your account:\n\n"
        f"{transaction_info}\n\n"
        f"If this was not authorized by you, please contact our support immediately.\n\n"
        f"Best regards,\nYour Bank Security Team"
    )
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user_email]
    send_mail(subject, message, from_email, recipient_list, fail_silently=False)
