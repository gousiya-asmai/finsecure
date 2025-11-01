from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

from django.utils import timezone
class UserProfile(models.Model):
    """Extended profile for each User"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True)
    income = models.FloatField(default=0.0, blank=True, null=True)
    financial_behavior = models.TextField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[
            ("Male", "Male"),
            ("Female", "Female"),
            ("Other", "Other"),
        ],
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def is_complete(self):
        """Check if essential profile fields are filled"""
        return all([
            self.profile_photo,
            self.occupation,
            self.income and self.income > 0,
            self.phone,
            self.name,
        ])

    def __str__(self):
        return f"Profile: {self.user.username if self.user else self.name}"


# ✅ Remove `UserGoogleToken` (it’s redundant)
# ✅ Use this single model for Gm

# users/models.py

from django.db import models
from django.conf import settings

class GmailCredential(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gmail_credential'
    )
    access_token = models.TextField(blank=True, null=True, default='')
    refresh_token = models.TextField(blank=True, null=True, default='')
    token_uri = models.CharField(max_length=200, blank=True, null=True, default='')
    client_id = models.CharField(max_length=200, blank=True, null=True, default='')
    client_secret = models.CharField(max_length=200, blank=True, null=True, default='')
    scopes = models.TextField(blank=True, null=True, default='[]')
    expiry = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Gmail Credentials for {self.user.username}"


class GmailTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.CharField(max_length=255)
    amount = models.FloatField(default=0.0)
    currency = models.CharField(max_length=10, default="INR")
    message_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.description} ({self.amount})"
