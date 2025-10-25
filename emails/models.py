from django.conf import settings
from django.db import models

class GmailCredential(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='emails_gmail_credential'  # Unique reverse name here
    )
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_uri = models.CharField(max_length=200)
    client_id = models.CharField(max_length=200)
    client_secret = models.CharField(max_length=200)
    scopes = models.TextField()
    expiry = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Gmail Credentials for {self.user.email}"
