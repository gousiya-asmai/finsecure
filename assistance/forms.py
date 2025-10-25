from django import forms
from .models import FinancialProfile


class FinancialProfileForm(forms.ModelForm):
    """
    Financial Profile Form.
    Excludes income (taken from UserProfile).
    Includes: expenses, credit score, savings goal,
    risk tolerance, monthly investments, financial goals.
    """

    # Choices for risk tolerance
    RISK_CHOICES = [
        ("Low", "Low"),
        ("Medium", "Medium"),
        ("High", "High"),
    ]

    expenses = forms.FloatField(
        label="Monthly Expenses (₹)",
        required=True,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Monthly Expenses in ₹",
                "min": 0,
            }
        ),
    )

    credit_score = forms.IntegerField(
        label="Credit Score (300-900)",
        required=True,
        help_text="Enter your credit score (e.g., 650-850).",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Credit Score (300-900)",
                "min": 300,
                "max": 900,
            }
        ),
    )

    monthly_savings_goal = forms.FloatField(
        label="Monthly Savings Goal (₹)",
        required=True,
        help_text="Amount you aim to save each month.",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Monthly Savings Goal in ₹",
                "min": 0,
            }
        ),
    )

    risk_tolerance = forms.ChoiceField(
        choices=RISK_CHOICES,
        label="Risk Tolerance",
        required=True,
        help_text="Select your risk tolerance for investments.",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    monthly_investments = forms.FloatField(
        label="Monthly Investments (₹)",
        required=False,
        help_text="Amount already invested monthly in mutual funds, stocks, etc.",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "placeholder": "Monthly Investments in ₹",
                "min": 0,
            }
        ),
    )

    financial_goals = forms.CharField(
        label="Financial Goals",
        required=False,
        help_text="Describe your short-term or long-term financial goals.",
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-control",
                "placeholder": "E.g., Buy a house, retirement planning",
            }
        ),
    )

    class Meta:
        model = FinancialProfile
        fields = [
            "expenses",
            "credit_score",
            "monthly_savings_goal",
            "risk_tolerance",
            "monthly_investments",
            "financial_goals",
        ]
