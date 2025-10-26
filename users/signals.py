from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.contrib.auth.signals import user_logged_in
from django.contrib import messages
import logging

from .models import UserProfile


@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """Ensure every User has a related UserProfile."""
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


@receiver(user_logged_in)
def check_profile_completeness(sender, request, user, **kwargs):
    """Check if profile is incomplete and show warning message."""
    try:
        profile = user.profile
        if not profile.is_complete():
            messages.warning(
                request,
                "⚠️ Your profile is incomplete. Please complete your profile for full access."
            )
            logging.info(f"Profile incomplete warning for: {user.username}")
    except UserProfile.DoesNotExist:
        try:
            UserProfile.objects.create(user=user, name=user.username, email=user.email)
        except Exception as e:
            logging.error(f"Profile creation failed: {e}")
