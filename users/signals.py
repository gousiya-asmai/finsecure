from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.contrib import messages
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
    Show a warning message on dashboard instead of sending email.
    """
    try:
        profile = user.profile
        if not profile.is_complete():
            # Show warning message on dashboard
            messages.warning(
                request,
                "⚠️ Your profile is incomplete. Please update your profile with "
                "photo, occupation, and income details to enjoy full features."
            )
            logging.info(f"Profile incomplete warning shown for user: {user.username}")
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        try:
            UserProfile.objects.create(user=user, name=user.username, email=user.email)
            logging.info(f"Created profile for user: {user.username}")
        except Exception as e:
            logging.error(f"Profile creation failed for {user.username}: {e}")
