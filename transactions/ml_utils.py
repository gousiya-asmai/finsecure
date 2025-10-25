import os
import pandas as pd
import numpy as np
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # one level up from transactions/
MODEL_PATH = os.path.join(BASE_DIR, 'fraud_detection_model.pkl')
SCALER_PATH = os.path.join(BASE_DIR, 'feature_scaler.pkl')

# Load saved model and scaler if available
model = None
scaler = None
try:
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
except FileNotFoundError:
    pass

EXPECTED_FEATURES = [
    'amount_log',
    'category_payment',
    'category_purchase',
    'category_withdrawal',
    'category_transfer',
    'category_uncategorized',
    'transaction_type_credit',
    'transaction_type_debit',
    'transaction_type_uncategorized',
]
def preprocess_input(input_data):
    df = pd.DataFrame([input_data])
    
    df['category'] = df.get('category', 'uncategorized').fillna('uncategorized').str.lower()
    df['transaction_type'] = df.get('transaction_type', 'uncategorized').fillna('uncategorized').str.lower()

    df['amount'] = df['amount'].astype(float)
    df['amount_log'] = np.log1p(df['amount'])

    df = pd.get_dummies(df, columns=['category', 'transaction_type'], drop_first=False)

    # Use same EXPECTED_FEATURES list as training
    for col in EXPECTED_FEATURES:
        if col not in df.columns:
            df[col] = 0

    df = df[EXPECTED_FEATURES]

    # Apply scaler
    if scaler:
        df['amount_log'] = scaler.transform(df[['amount_log']])
    else:
        raise ValueError("Scaler not loaded. Train model first to generate scaler.")

    return df


def predict_fraud(input_data):
    if model is None:
        raise ValueError("Model not loaded. Train model first to generate model file.")

    X = preprocess_input(input_data)
    pred = model.predict(X)[0]

    proba = model.predict_proba(X)[0]
    fraud_index = list(model.classes_).index(1)  # index of fraud class
    probability = proba[fraud_index]

    return {'is_fraud': bool(pred), 'probability': float(probability)}

def train_fraud_model(df):
    from imblearn.over_sampling import SMOTE
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import classification_report
    from sklearn.preprocessing import StandardScaler

    # Prepare features and label
    X = df.drop("is_fraud", axis=1)
    y = df["is_fraud"]

    # Log-transform amount to amount_log, then drop original amount
    X['amount_log'] = np.log1p(X['amount'])
    X = X.drop(columns=['amount'])

    # One-hot encode categorical columns
    X = pd.get_dummies(X, columns=['category', 'transaction_type'], drop_first=False)

    # Add missing expected features with zeros
    for col in EXPECTED_FEATURES:
        if col not in X.columns:
            X[col] = 0
    # Keep only expected features in correct order
    X = X[EXPECTED_FEATURES]

    # Scale amount_log
    scaler_local = StandardScaler()
    X.loc[:, 'amount_log'] = scaler_local.fit_transform(X[['amount_log']])

    # Save scaler for prediction usage
    joblib.dump(scaler_local, SCALER_PATH)

    # Handle class imbalance with SMOTE
    sm = SMOTE(random_state=42)
    X_res, y_res = sm.fit_resample(X, y)

    X_train, X_test, y_train, y_test = train_test_split(
        X_res, y_res, test_size=0.2, random_state=42
    )

    model_local = RandomForestClassifier(random_state=42)
    model_local.fit(X_train, y_train)

    y_pred = model_local.predict(X_test)

    print(classification_report(y_test, y_pred))

    # Save trained model for prediction usage
    joblib.dump(model_local, MODEL_PATH)

    # Update global model and scaler variables
    global model, scaler
    model = model_local
    scaler = scaler_local

    return model_local
