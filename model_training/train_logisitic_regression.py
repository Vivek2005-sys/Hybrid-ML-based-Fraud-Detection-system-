import sys
import os

# Add project root directory to Python's search path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import joblib
from sqlalchemy import text
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
)

from app.database import engine

print("Fetching training_features dataset from PostgreSQL...", flush=True)

# 1. Define feature columns and target
feature_cols = [
    'amount', 
    'is_active_vpn', 
    'is_international',
    'minutes_since_last_txn_clean', 
    'txn_count_30m', 
    'total_amount_30m',
    'gap_volatility_5tx_clean', 
    'amount_z_score', 
    'merchant_diversity_7d',
    'hour_of_day', 
    'is_weekend', 
    'is_night_txn', 
    'is_high_risk_category',
    'p7d_txn_count', 
    'p7d_avg_amount', 
    'p7d_sum_amount', 
    'p7d_std_amount',
    'p30d_txn_count', 
    'p30d_avg_amount', 
    'p30d_sum_amount', 
    'p30d_std_amount',
    'p90d_txn_count', 
    'p90d_avg_amount'
]

# Optimize memory loading by explicitly requesting ONLY necessary columns
select_cols = ", ".join(feature_cols + ['is_fraud'])
query = text(f"SELECT {select_cols} FROM training_features ORDER BY transaction_date ASC;")

with engine.connect() as conn:
    df = pd.read_sql(query, conn)

print(f"Data Fetch Complete! Successfully loaded {len(df):,} rows into memory.", flush=True)

X = df[feature_cols]
y = df['is_fraud']

# 2. Chronological 80/20 Train/Test Split (No random shuffling)
split_idx = int(len(df) * 0.8)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

neg_count, pos_count = np.bincount(y_train)
scale_pos_weight = neg_count / pos_count

print(f"Train Dataset : {len(X_train):,} rows | Fraud Cases: {y_train.sum():,}", flush=True)
print(f"Test Dataset  : {len(X_test):,} rows | Fraud Cases: {y_test.sum():,}", flush=True)
print(f"Imbalance Ratio (scale_pos_weight) : {scale_pos_weight:.2f}\n", flush=True)

# 3. Feature Scaling
print("Scaling features...", flush=True)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# 4. Train Baseline Model
print("Training Baseline Model: Logistic Regression (class_weight='balanced')...", flush=True)
lr_model = LogisticRegression(
    class_weight='balanced',
    max_iter=1000,
    random_state=42
)
lr_model.fit(X_train_scaled, y_train)

# 5. Model Predictions
y_pred = lr_model.predict(X_test_scaled)
y_proba = lr_model.predict_proba(X_test_scaled)[:, 1]

# 6. Comprehensive Evaluation
print("\n==================================================", flush=True)
print("       LOGISTIC REGRESSION BASELINE EVALUATION    ", flush=True)
print("==================================================\n", flush=True)

cm = confusion_matrix(y_test, y_pred)
tn, fp, fn, tp = cm.ravel()

print("--- Confusion Matrix ---", flush=True)
print(f"True Negatives  (Legit Allowed) : {tn:,}", flush=True)
print(f"False Positives (False Alarms)  : {fp:,}", flush=True)
print(f"False Negatives (Missed Fraud)  : {fn:,}", flush=True)
print(f"True Positives  (Fraud Caught)  : {tp:,}\n", flush=True)

roc_auc = roc_auc_score(y_test, y_proba)
pr_auc = average_precision_score(y_test, y_proba)

print("--- Threshold-Independent Metrics ---", flush=True)
print(f"ROC-AUC Score : {roc_auc:.4f}", flush=True)
print(f"PR-AUC Score  : {pr_auc:.4f}  (Key baseline metric for imbalanced fraud)", flush=True)

print("\n--- Detailed Classification Report ---", flush=True)
print(classification_report(y_test, y_pred, target_names=['Legitimate (0)', 'Fraud (1)'], digits=4), flush=True)

importance_df = pd.DataFrame({
    'Feature': feature_cols,
    'Coefficient': lr_model.coef_[0],
    'Absolute_Impact': np.abs(lr_model.coef_[0])
}).sort_values(by='Absolute_Impact', ascending=False)

print("\n--- Top Feature Coefficients (Log-Odds Impact) ---", flush=True)
print(importance_df[['Feature', 'Coefficient']].to_string(index=False), flush=True)

# 7. Serialize Baseline Artifacts for Week 5 Comparison
os.makedirs("model_training/saved_models", exist_ok=True)
joblib.dump(lr_model, "model_training/saved_models/baseline_logistic_regression.pkl")
joblib.dump(scaler, "model_training/saved_models/scaler.pkl")
print("\nBaseline artifacts saved to 'model_training/saved_models/'.", flush=True)