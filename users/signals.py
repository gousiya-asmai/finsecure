from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.core.mail import send_mail
from django.conf import settings
import logging

from .models import UserProfile


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Ensure every User has a related UserProfile.
    """
    if created:
        # Create profile for new user
        UserProfile.objects.create(
            user=instance,
            name=instance.username,
            email=instance.email
        )
    else:
        # Ensure profile exists (get_or_create)
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={"name": instance.username, "email": instance.email}
        )


@receiver(user_logged_in)
def check_profile_completeness(sender, request, user, **kwargs):
    """
    After user logs in, check if profile is incomplete.
    If incomplete, send an email reminder (non-blocking).
    """
    try:
        profile = user.profile  # thanks to related_name="profile"
        if not profile.is_complete():
            # Non-blocking email send with timeout
            try:
                send_mail(
                    subject="⚠️ Complete Your Profile",
                    message=(
                        f"Hi {user.username},\n\n"
                        "Your profile is incomplete. Please update your profile with your "
                        "profile photo, occupation, income, and financial behavior details "
                        "to enjoy full access to our services.\n\n"
                        f"Login here to update: https://finsecure-jgzx.onrender.com/profile/\n\n"
                        "Thank you!"
                    ),
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@financesystem.com"),
                    recipient_list=[user.email],
                    fail_silently=True,  # Don't crash on email errors
                    timeout=5,  # 5 second timeout to prevent hanging
                )
            except Exception as e:
                # Log error but don't block login
                logging.error(f"Profile email send failed for {user.email}: {e}")
    except UserProfile.DoesNotExist:
        # In rare case profile wasn't created
        try:
            UserProfile.objects.create(user=user, name=user.username, email=user.email)
        except Exception as e:
            logging.error(f"Profile creation failed for {user.username}: {e}")
