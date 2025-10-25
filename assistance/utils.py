# users/utils.py (bottom of file)

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from assistance.models import GmailCredential  # adjust path if your model is in assistance

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def is_gmail_connected(user):
    """Check if Gmail is connected for a given user."""
    try:
        cred_obj = GmailCredential.objects.get(user=user)
        creds = Credentials.from_authorized_user_info(eval(cred_obj.token), SCOPES)
        service = build('gmail', 'v1', credentials=creds)
        service.users().labels().list(userId='me').execute()  # test API call
        return True
    except GmailCredential.DoesNotExist:
        return False
    except Exception as e:
        print("Gmail not connected:", e)
        return False

# assistance/utils.py

def train_model(profiles):
    """
    Placeholder: Train ML model on FinancialProfile data.
    Right now this does nothing.
    """
    return None


def predict_assistance(profile):
    """
    Placeholder: Predict whether assistance is required.
    For now, return True if income - expenses < 10000 or credit score < 700.
    """
    try:
        net_savings = profile.income - profile.expenses
        if net_savings <= 10000 or profile.credit_score < 700:
            return True
        return False
    except Exception:
        return None


def generate_recommendations(profile, assistance_required):
    """
    Placeholder: Generate recommendations based on rule-based logic.
    """
    recommendations = []

    if assistance_required:
        recommendations.append("⚠️ You may need financial assistance. Review your spending habits.")
    else:
        recommendations.append("✅ Your financial status looks stable. Keep up the good work!")

    if profile.risk_tolerance.lower() == "high":
        recommendations.append("💡 Diversify your portfolio to balance risks.")
    elif profile.risk_tolerance.lower() == "low":
        recommendations.append("💡 Focus on safer investments like FDs or bonds.")

    return recommendations
