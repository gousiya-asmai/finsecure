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

    @property
    def token(self):
        """Backward-compatible alias for access_token."""
        return self.access_token




# transactions/models.py
# models.py
# users/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class GmailTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255, unique=True)
    subject = models.TextField()
    snippet = models.TextField(blank=True, null=True)
    sender = models.EmailField()
    amount = models.FloatField(default=0.0)
    currency = models.CharField(max_length=10, default='₹')
    transaction_type = models.CharField(max_length=20, default='debit')
    category = models.CharField(max_length=100, default='N/A')
    gmail_link = models.URLField(max_length=500, null=True, blank=True)
    date = models.DateTimeField()

    # 🆕 Fraud detection flag
    is_fraud = models.BooleanField(default=False)
    fraud_reason = models.TextField(null=True, blank=True)


    def __str__(self):
        return f"{self.user.username} - {self.subject}"

# users/models.py

from django.db import models
from django.contrib.auth.models import User

class FraudAlert(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, default="🚨 Suspicious Transaction Detected")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Fraud Alert for {self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


    




    def __str__(self):
        return f"{self.user.username} | {self.subject[:50]}"


class GmailEmail(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=255)
    sender = models.CharField(max_length=255)
    snippet = models.TextField()
    message_id = models.CharField(max_length=255, unique=True)
    received_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject} ({self.sender})"

class OTPVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"OTP for {self.user.username} ({self.otp_code})"
    
    from django.db import models
from django.contrib.auth.models import User

class GmailToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField()
    client_id = models.TextField()
    client_secret = models.TextField()
    token_expiry = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"GmailToken for {self.user.username}"