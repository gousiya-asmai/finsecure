# users/models.py

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings


class UserProfile(models.Model):
    """Extended profile for each User"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        null=True,
        blank=True
    )
    # Basic info
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True, blank=True)
    phone = models.CharField(max_length=15, blank=True)

    # New fields
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True)
    income = models.FloatField(default=0.0, blank=True, null=True)

    # Keep in DB, but we won’t expose in forms/templates
    financial_behavior = models.TextField(blank=True, null=True)

    # Extra details
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


class UserGoogleToken(models.Model):
    """Store Google OAuth2 token details"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="google_token")
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_uri = models.CharField(max_length=200)
    client_id = models.CharField(max_length=200)
    client_secret = models.CharField(max_length=200)
    scopes = models.TextField()

    def __str__(self):
        return f"Google Token for {self.user.username}"


class GmailCredential(models.Model):
    """Store Gmail API credentials for a user"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="users_gmail_credential"  # Different unique related_name
    )
    # Add Gmail API fields if needed later (e.g., access tokens, etc.)

    def __str__(self):
        return f"Gmail Credentials for {self.user.email}"
