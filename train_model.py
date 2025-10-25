import os
import django
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE
import joblib

# Initialize Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from transactions.models import Transaction

# Define directory and paths to save model and scaler
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, 'fraud_detection_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, 'feature_scaler.pkl')

def main():
    # Fetch transaction data from DB
    qs = Transaction.objects.all().values('amount', 'category', 'transaction_type', 'is_fraud')
    df = pd.DataFrame(list(qs))

    if df.empty:
        raise ValueError("No transaction data found. Cannot train model.")

    # Normalize column names and fill missing categorical data with 'uncategorized'
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

    # One-hot encode categorical columns (no drop_first)
    df_encoded = pd.get_dummies(df, columns=['category', 'transaction_type'], drop_first=False)

    # Define expected features as amount_log + all category_ and transaction_type_ columns
    EXPECTED_FEATURES = ['amount_log',
                     'category_payment', 'category_purchase', 'category_withdrawal', 'category_transfer', 'category_uncategorized',
                     'transaction_type_credit', 'transaction_type_debit', 'transaction_type_uncategorized']
    for col in EXPECTED_FEATURES:
                    if col not in df_encoded.columns:
                        df_encoded[col] = 0

# Keep columns in this exact order

    X = df_encoded[EXPECTED_FEATURES]
    y = df_encoded['is_fraud']

    print("Class distribution BEFORE SMOTE:")
    print(y.value_counts())

    # Scale amount_log feature
    scaler = StandardScaler()
    X.loc[:, ['amount_log']] = scaler.fit_transform(X[['amount_log']])

    joblib.dump(scaler, SCALER_PATH)

    # Balance classes using SMOTE
    smote = SMOTE(random_state=42)
    X_resampled, y_resampled = smote.fit_resample(X, y)

    print("Class distribution AFTER SMOTE:")
    print(pd.Series(y_resampled).value_counts())

    # Stratified train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X_resampled, y_resampled, test_size=0.2, stratify=y_resampled, random_state=42
    )

    # Train Random Forest Classifier
    clf = RandomForestClassifier(random_state=42)
    clf.fit(X_train, y_train)

    # Save the trained model
    joblib.dump(clf, MODEL_PATH)

    print("Model training complete.")
    print(f"Test Accuracy: {clf.score(X_test, y_test):.4f}")

if __name__ == '__main__':
    main()
