import pandas as pd
import numpy as np
import xgboost as xgb
import joblib
import json
import os
import sys
from datetime import datetime

# Add app to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from app.database import engine

def train_champion_model():
    print("🚀 Starting XGBoost Continuous Training Pipeline...")
    
    # 1. Fetch Historical Transactions
    print("📡 Fetching historical transactions from database...")
    query = "SELECT * FROM transactions ORDER BY transaction_date ASC"
    df = pd.read_sql(query, engine)
    
    if len(df) < 50:
        raise ValueError("Not enough historical data to train a reliable XGBoost model. (Minimum 50 records required).")
        
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    
    # 2. Fetch Custom Dynamic Artifacts
    print("🧩 Fetching Dynamic Artifact Definitions...")
    try:
        artifacts = pd.read_sql("SELECT name, lookback_hours, aggregation FROM artifacts", engine)
    except Exception:
        artifacts = pd.DataFrame()
        
    print(f"   Found {len(artifacts)} dynamic artifacts.")
    
    # 3. Feature Engineering (Backfilling)
    print("⚙️ Backfilling features (Rolling Windows & Time Deltas)...")
    df = df.sort_values(by=['customer_id', 'transaction_date'])
    
    # Base features
    df['hour_of_day'] = df['transaction_date'].dt.hour
    df['is_night_txn'] = (df['hour_of_day'] < 5).astype(int)
    
    high_risk = ['Luxury Goods', 'Financial Services', 'Gaming']
    df['is_high_risk_category'] = df['merchant_category'].isin(high_risk).astype(int)
    
    # Time gap
    df['minutes_since_last_txn_clean'] = df.groupby('customer_id')['transaction_date'].diff().dt.total_seconds() / 60.0
    df['minutes_since_last_txn_clean'] = df['minutes_since_last_txn_clean'].fillna(99999.0)
    
    # Standard Hardcoded Profiles (7d, 30d, 90d)
    windows = {'7d': '7D', '30d': '30D', '90d': '90D', '24h': '1D'}
    df = df.set_index('transaction_date')
    
    for prefix, win in windows.items():
        grouped = df.groupby('customer_id')['amount'].rolling(win, closed='left')
        df[f'p{prefix}_txn_count'] = grouped.count().reset_index(level=0, drop=True).fillna(0)
        df[f'p{prefix}_sum_amount'] = grouped.sum().reset_index(level=0, drop=True).fillna(0.0)
        df[f'p{prefix}_avg_amount'] = grouped.mean().reset_index(level=0, drop=True).fillna(0.0)
        df[f'p{prefix}_std_amount'] = grouped.std().reset_index(level=0, drop=True).fillna(0.0)
        
    # Replace the p24h prefix to match standard API
    df['txn_count_24h'] = df['p24h_txn_count']
    
    # Acceleration
    df['velocity_acceleration_24h'] = np.where(df['p30d_txn_count'] > 0, 
                                               df['txn_count_24h'] / (df['p30d_txn_count'] / 30.0), 
                                               0.0)
                                               
    # Standard remaining ML features (simplified backfill for Z-score and gap volatility)
    df['amount_z_score'] = 0.0
    df['gap_volatility_5tx_clean'] = 0.0
    df['merchant_diversity_7d'] = 1
    
    # 4. Compute Dynamic Artifacts (Rolling Windows)
    for idx, row in artifacts.iterrows():
        name = row['name']
        lookback = f"{row['lookback_hours']}h"
        agg = row['aggregation'].upper()
        
        grouped = df.groupby('customer_id')['amount'].rolling(lookback, closed='left')
        if agg == 'COUNT':
            df[name] = grouped.count().reset_index(level=0, drop=True).fillna(0.0)
        elif agg == 'SUM':
            df[name] = grouped.sum().reset_index(level=0, drop=True).fillna(0.0)
        elif agg == 'AVG':
            df[name] = grouped.mean().reset_index(level=0, drop=True).fillna(0.0)
        elif agg == 'MAX':
            df[name] = grouped.max().reset_index(level=0, drop=True).fillna(0.0)
            
    df = df.reset_index()
    
    # 5. Model Training (XGBoost)
    print("🧠 Training XGBoost Classifier...")
    
    # Define exact feature columns we just generated
    base_cols = [
        'amount', 'is_active_vpn', 'is_international',
        'minutes_since_last_txn_clean', 'gap_volatility_5tx_clean', 'amount_z_score', 'merchant_diversity_7d',
        'hour_of_day', 'is_night_txn', 'is_high_risk_category',
        'p7d_txn_count', 'p7d_avg_amount', 'p7d_sum_amount', 'p7d_std_amount',
        'p30d_txn_count', 'p30d_avg_amount', 'p30d_sum_amount', 'p30d_std_amount',
        'p90d_txn_count', 'p90d_avg_amount'
    ]
    
    dynamic_cols = artifacts['name'].tolist() if not artifacts.empty else []
    feature_cols = base_cols + dynamic_cols
    
    X = df[feature_cols].astype(float)
    y = df['is_fraud'].astype(int)
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric='logloss',
        random_state=42
    )
    
    model.fit(X, y)
    
    # 6. Save Model and Metadata
    print("💾 Saving Model & Metadata...")
    
    os.makedirs("./ml_features", exist_ok=True)
    joblib.dump(model, "./ml_features/champion_model.pkl")
    
    metadata = {
        "trained_at": datetime.utcnow().isoformat(),
        "total_records": len(df),
        "fraud_records": int(y.sum()),
        "feature_cols": feature_cols,
        "dynamic_artifacts_included": len(dynamic_cols)
    }
    
    with open("./ml_features/model_metadata.json", "w") as f:
        json.dump(metadata, f, indent=4)
        
    print(f"✅ XGBoost Training Complete! Model deployed with {len(feature_cols)} features.")
    return metadata

if __name__ == "__main__":
    train_champion_model()
