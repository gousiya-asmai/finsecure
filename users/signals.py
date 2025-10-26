from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.core.mail import send_mail
from django.conf import settings
import logging
import threading

from .models import UserProfile


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Ensure every User has a related UserProfile.
    """
    if created:
        UserProfile.objects.create(
            user=instance,
            name=instance.username,
            email=instance.email
        )
    else:
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={"name": instance.username, "email": instance.email}
        )


def send_profile_email_async(user_email, username):
    """
    Send profile completion email in background thread
    """
    try:
        send_mail(
            subject="⚠️ Complete Your Profile",
            message=(
                f"Hi {username},\n\n"
                "Your profile is incomplete. Please update your profile with your "
                "profile photo, occupation, income, and financial behavior details "
                "to enjoy full access to our services.\n\n"
                f"Login here to update: https://finsecure-jgzx.onrender.com/profile/\n\n"
                "Thank you!"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@financesystem.com"),
            recipient_list=[user_email],
            fail_silently=True,
            timeout=10,
        )
        logging.info(f"Profile completion email sent to {user_email}")
    except Exception as e:
        logging.error(f"Profile email send failed for {user_email}: {e}")


@receiver(user_logged_in)
def check_profile_completeness(sender, request, user, **kwargs):
    """
    After user logs in, check if profile is incomplete.
    If incomplete, send email in background thread (non-blocking).
    """
    try:
        profile = user.profile
        if not profile.is_complete():
            # Send email in background thread so it doesn't block login
            email_thread = threading.Thread(
                target=send_profile_email_async,
                args=(user.email, user.username)
            )
            email_thread.daemon = True  # Thread will die when main program exits
            email_thread.start()
            
    except UserProfile.DoesNotExist:
        try:
            UserProfile.objects.create(user=user, name=user.username, email=user.email)
        except Exception as e:
            logging.error(f"Profile creation failed for {user.username}: {e}")
