from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# --- Model 1: Assistance Results linked to UserProfile ---
class AssistanceResult(models.Model):
    user = models.ForeignKey(
        'users.UserProfile',  # linked to UserProfile
        on_delete=models.CASCADE,
        related_name="assistance_results"
    )
    assistance_required = models.BooleanField()
    suggestion = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        status = "Required" if self.assistance_required else "Not Required"
        return f"Assistance for {self.user.user.username} ({status}) on {self.created_at.strftime('%Y-%m-%d %H:%M')}"


# --- Model 2: Financial Profile (One record per user per month) ---
class FinancialProfile(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # many submissions over time
    income = models.FloatField(default=0.0)
    expenses = models.FloatField(default=0.0)
    credit_score = models.IntegerField(default=0)
    monthly_savings_goal = models.FloatField(default=0.0)
    risk_tolerance = models.CharField(
        max_length=20,
        choices=[('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High')],
        default="Medium"
    )
    monthly_investments = models.FloatField(default=0.0)
    financial_goals = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)  # track submission time
    suggestion = models.TextField(blank=True, null=True)  # store auto-generated suggestions

    class Meta:
        ordering = ['-submitted_at']  # latest first
        unique_together = ('user', 'submitted_at')  # prevents duplicate same-time entries

    def __str__(self):
        return f"{self.user.username} | {self.submitted_at.strftime('%B %Y')}"


# --- Model 3: Purchase Alerts from Gmail ---
class PurchaseAlert(models.Model):
    sender = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    snippet = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Purchase Alert: {self.subject} ({self.sender})"


# --- Model 4: Smart Suggestions (Stored history for dashboard) ---
class SmartSuggestion(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="smart_suggestions"
    )
    suggestion = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_alert = models.BooleanField(default=False)  # ⚠️ Flag for risky suggestions

    class Meta:
        ordering = ["-created_at"]  # latest first

    def __str__(self):
        tag = "⚠️" if self.is_alert else "💡"
        return f"{tag} {self.user.username} - {self.suggestion[:50]}"


# --- ✅ Model 5: Gmail Credentials per User ---
class GmailCredential(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="gmail_credential"
    )
    token = models.JSONField()  # store full Gmail OAuth token as JSON
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Gmail credentials for {self.user.username}"
