# assistance/ml_model.py

import joblib
import os
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from .models import FinancialProfile

# Model file path
MODEL_FILE = "assistance_ml_model.pkl"

# Global LabelEncoders (trained/saved with the model)
le_occupation = LabelEncoder()
le_risk = LabelEncoder()

def train_model(profiles=None):
    """
    Train ML model using historical FinancialProfile + UserProfile data.
    - income, occupation -> from UserProfile
    - financial details -> from FinancialProfile
    Saves the model along with LabelEncoders to disk.
    """
    if profiles is None:
        profiles = FinancialProfile.objects.all()
    
    if not profiles.exists():
        return None

    X, y = [], []
    occupations, risks = [], []

    # Prepare data
    for p in profiles:
        user_profile = getattr(p.user, "userprofile", None)

        income = user_profile.income if user_profile and user_profile.income else 0
        occupation = user_profile.occupation if user_profile and user_profile.occupation else "Unknown"

        occupations.append(occupation)
        risks.append(getattr(p, "risk_tolerance", "Medium"))

        X.append([
            income,
            p.expenses or 0.0,
            p.credit_score or 0.0,
            getattr(p, "debts", 0.0),
            getattr(p, "monthly_investment", 0.0),
        ])

        net_savings = income - (p.expenses or 0.0)
        y.append(1 if net_savings <= 10000 or (p.credit_score or 0) < 700 else 0)  # 1 = assistance required

    # Encode categorical features
    le_occupation.fit(occupations)
    le_risk.fit(risks)
    occ_encoded = le_occupation.transform(occupations)
    risk_encoded = le_risk.transform(risks)

    # Merge numeric + categorical features
    X = np.array(X)
    X = np.column_stack([X, occ_encoded, risk_encoded])
    y = np.array(y)

    # Train RandomForestClassifier
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)

    # Save model + encoders
    joblib.dump({
        "model": clf,
        "le_occupation": le_occupation,
        "le_risk": le_risk
    }, MODEL_FILE)

    return clf


def predict_assistance(profile):
    """
    Predict if assistance is required for a given FinancialProfile instance.
    Uses UserProfile for income and occupation.
    Returns True if assistance is needed, False otherwise.
    """
    if not os.path.exists(MODEL_FILE):
        return None  # Model not trained yet

    data = joblib.load(MODEL_FILE)
    clf = data["model"]
    le_occupation = data["le_occupation"]
    le_risk = data["le_risk"]

    user_profile = getattr(profile.user, "userprofile", None)

    income = user_profile.income if user_profile and user_profile.income else 0
    occupation = user_profile.occupation if user_profile and user_profile.occupation else "Unknown"
    risk = getattr(profile, "risk_tolerance", "Medium")

    # Handle unseen categories gracefully
    try:
        occ_encoded = le_occupation.transform([occupation])[0]
    except ValueError:
        occ_encoded = 0  # default index for unseen occupation

    try:
        risk_encoded = le_risk.transform([risk])[0]
    except ValueError:
        risk_encoded = 1  # default index for unseen risk

    # Prepare test features
    X_test = np.array([[
        income,
        profile.expenses or 0.0,
        profile.credit_score or 0.0,
        getattr(profile, "debts", 0.0),
        getattr(profile, "monthly_investment", 0.0),
        occ_encoded,
        risk_encoded
    ]])

    # Predict
    prediction = clf.predict(X_test)[0]
    return bool(prediction)


def generate_recommendations(profile, assistance_required):
    """
    Generate user-friendly recommendations based on profile and prediction.
    Returns a list of strings.
    """
    user_profile = getattr(profile.user, "userprofile", None)
    income = user_profile.income if user_profile and user_profile.income else 0
    expenses = profile.expenses or 0
    net_savings = income - expenses

    recommendations = []

    if assistance_required:
        if net_savings <= 10000:
            recommendations.append("⚠️ Your savings are quite low. Aim to reduce expenses by at least 10%.")
        if (profile.credit_score or 0) < 700:
            recommendations.append("⚠️ Work on improving your credit score — pay bills on time and reduce credit usage.")
        if getattr(profile, "debts", 0) > 0:
            recommendations.append("⚠️ You have outstanding debts. Create a repayment plan to lower interest burden.")
        if not getattr(profile, "monthly_investment", 0):
            recommendations.append("💡 Consider starting a small monthly SIP to build long-term wealth.")
    else:
        recommendations.append("✅ Your finances look stable. Keep monitoring your expenses.")
        if net_savings > 15000:
            recommendations.append("💡 Great savings! Consider diversifying into investments for higher returns.")
        if (profile.credit_score or 0) >= 750:
            recommendations.append("✅ Excellent credit score. You can explore premium credit cards or low-interest loans.")

    return recommendations
