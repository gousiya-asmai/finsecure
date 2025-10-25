# assistance/admin.py
from django.contrib import admin
from .models import AssistanceResult, FinancialProfile, PurchaseAlert


@admin.register(PurchaseAlert)
class PurchaseAlertAdmin(admin.ModelAdmin):
    list_display = ("sender", "subject", "timestamp")
    search_fields = ("sender", "subject")
    ordering = ("-timestamp",)


@admin.register(AssistanceResult)
class AssistanceResultAdmin(admin.ModelAdmin):
    list_display = ("user", "assistance_required", "suggestion", "created_at")
    list_filter = ("assistance_required", "created_at")
    search_fields = ("user__username", "suggestion")
    ordering = ("-created_at",)


@admin.register(FinancialProfile)
class FinancialProfileAdmin(admin.ModelAdmin):
    # Display user and actual model fields
    list_display = (
        "user",
        "expenses",
        "credit_score",
        "monthly_savings_goal",
        "risk_tolerance",
        "monthly_investments",
        "financial_goals",
        "submitted_at",
    )
    search_fields = ("user__username", "financial_goals")
    ordering = ("user__username", "-submitted_at")
