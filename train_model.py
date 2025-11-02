import os
import django
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import joblib

# ---------------- Django Setup ----------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from transactions.models import Transaction

# ---------------- Paths Configuration ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, 'backend', 'models')
os.makedirs(MODEL_DIR, exist_ok=True)

MODEL_PATH = os.path.join(MODEL_DIR, 'fraud_model.pkl')
SCALER_PATH = os.path.join(MODEL_DIR, 'feature_scaler.pkl')


def main():
    # ---------------- Load Transaction Data ----------------
    qs = Transaction.objects.all().values('amount', 'category', 'transaction_type', 'is_fraud')
    df = pd.DataFrame(list(qs))

    if df.empty:
        raise ValueError("No transaction data found. Cannot train model.")

    # Normalize and clean data
    df.columns = df.columns.str.strip().str.lower()
    for col in ['category', 'transaction_type']:
        if col in df.columns:
            df[col] = df[col].fillna('uncategorized').str.lower()
        else:
            df[col] = 'uncategorized'

    if 'amount' not in df.columns:
        raise KeyError("'amount' column not found in Transaction data.")

    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)
    df['amount_log'] = np.log1p(df['amount'])

    # One-hot encode categorical variables
    df_encoded = pd.get_dummies(df, columns=['category', 'transaction_type'], drop_first=False)

    # Define expected features
    EXPECTED_FEATURES = [
        'amount_log',
        'category_payment', 'category_purchase', 'category_withdrawal', 'category_transfer', 'category_uncategorized',
        'transaction_type_credit', 'transaction_type_debit', 'transaction_type_uncategorized'
    ]

    # Ensure all expected columns exist
    for col in EXPECTED_FEATURES:
        if col not in df_encoded.columns:
            df_encoded[col] = 0

    # Keep columns in consistent order
    X = df_encoded[EXPECTED_FEATURES]
    y = df_encoded['is_fraud']

    print("Class distribution BEFORE SMOTE:")
    print(y.value_counts())

    # ---------------- Feature Scaling ----------------
    scaler = StandardScaler()
    X.loc[:, ['amount_log']] = scaler.fit_transform(X[['amount_log']])

    # Save the scaler
    joblib.dump(scaler, SCALER_PATH)

    # ---------------- Handle Class Imbalance ----------------
    # Adjust SMOTE neighbors dynamically to avoid small sample errors
    minority_class_count = y.value_counts().min()
    k_neighbors = min(5, minority_class_count - 1) if minority_class_count > 1 else 1
    smote = SMOTE(random_state=42, k_neighbors=k_neighbors)

    X_resampled, y_resampled = smote.fit_resample(X, y)

    print("Class distribution AFTER SMOTE:")
    print(pd.Series(y_resampled).value_counts())

    # ---------------- Train/Test Split ----------------
    X_train, X_test, y_train, y_test = train_test_split(
        X_resampled, y_resampled, test_size=0.2, stratify=y_resampled, random_state=42
    )

    # ---------------- Train Model ----------------
    clf = RandomForestClassifier(random_state=42)
    clf.fit(X_train, y_train)

    # ---------------- Save Model ----------------
    joblib.dump(clf, MODEL_PATH)
    print("✅ Model training complete.")
    print(f"✅ Test Accuracy: {clf.score(X_test, y_test):.4f}")
    print(f"✅ Fraud model saved at: {MODEL_PATH}")
    print(f"✅ Scaler saved at: {SCALER_PATH}")


if __name__ == '__main__':
    main()
