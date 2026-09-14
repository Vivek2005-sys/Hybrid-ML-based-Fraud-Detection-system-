import sys
import os
import pandas as pd
from sqlalchemy import create_engine
import joblib
import json
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal
from app import models
from rules import rule_engine
from pydantic import BaseModel
from typing import Optional

class TransactionRequest(BaseModel):
    customer_id: int
    amount: float
    merchant: str
    merchant_category: str
    is_active_vpn: Optional[bool] = False
    is_international: Optional[bool] = False
    transaction_date: Optional[datetime] = None

def run_comparison():
    db_url = "postgresql://fraud_user:securepassword@localhost:5433/fraud_db"
    engine = create_engine(db_url)
    db = SessionLocal(bind=engine)
    print("Fetching sample transactions for evaluation...")
    
    # Let's get a mix of fraud and non-fraud
    query = """
        (SELECT * FROM transactions WHERE is_fraud = 1 LIMIT 100)
        UNION ALL
        (SELECT * FROM transactions WHERE is_fraud = 0 LIMIT 400)
        ORDER BY transaction_date DESC
    """
    df = pd.read_sql(query, db.bind)
    
    print(f"Loaded {len(df)} transactions to test.")
    
    # Load ML Model
    try:
        model = joblib.load('ml_features/champion_model.pkl')
        with open('ml_features/model_metadata.json', 'r') as f:
            metadata = json.load(f)
            feature_cols = metadata['feature_cols']
    except Exception as e:
        print(f"Error loading model: {e}")
        return

    results = []
    
    for idx, row in df.iterrows():
        txn = TransactionRequest(
            customer_id=row['customer_id'],
            amount=row['amount'],
            merchant=row['merchant'],
            merchant_category=row['merchant_category'],
            is_active_vpn=row['is_active_vpn'],
            is_international=row['is_international'],
            transaction_date=row['transaction_date']
        )
        
        # 1. Run Rules
        try:
            total_score, max_rule_score, risk_level, current_velocity, triggered_rules, observations = rule_engine.evaluate_transaction(db, txn, txn.transaction_date)
            
            # Rule Decision: We consider it 'caught' by rules if max_rule_score >= 100
            rule_is_fraud = 1 if max_rule_score >= 100 else 0
            
            # 2. Run ML
            flat_features = {
                'amount': txn.amount,
                'is_active_vpn': int(txn.is_active_vpn) if txn.is_active_vpn else 0,
                'is_international': int(txn.is_international) if txn.is_international else 0
            }
            
            ml_snapshot = observations.get("ml_features", {})
            flat_features.update(ml_snapshot)
            
            df_input = pd.DataFrame([flat_features])
            for col in df_input.columns:
                if df_input[col].dtype == 'bool':
                    df_input[col] = df_input[col].astype(int)
                    
            missing_cols = [c for c in feature_cols if c not in df_input.columns]
            for col in missing_cols:
                df_input[col] = 0.0
                
            X_input = df_input[feature_cols].astype(float)
            prob = model.predict_proba(X_input)[0][1]
            ml_is_fraud = 1 if prob >= 0.20 else 0
            
            results.append({
                'is_actual_fraud': row['is_fraud'],
                'rule_caught': rule_is_fraud,
                'ml_caught': ml_is_fraud,
                'rule_score': max_rule_score,
                'ml_prob': prob,
                'amount': row['amount']
            })
        except Exception as e:
            print(f"Error processing {row['id']}: {e}")
            continue
            
    res_df = pd.DataFrame(results)
    
    print("\n--- PERFORMANCE COMPARISON ---")
    
    actual_frauds = res_df[res_df['is_actual_fraud'] == 1]
    actual_legit = res_df[res_df['is_actual_fraud'] == 0]
    
    print(f"\nTotal Actual Frauds Tested: {len(actual_frauds)}")
    
    rules_caught = len(actual_frauds[actual_frauds['rule_caught'] == 1])
    ml_caught = len(actual_frauds[actual_frauds['ml_caught'] == 1])
    
    print(f"Rules Caught : {rules_caught} / {len(actual_frauds)} (Recall: {rules_caught/len(actual_frauds):.2%})")
    print(f"ML Caught    : {ml_caught} / {len(actual_frauds)} (Recall: {ml_caught/len(actual_frauds):.2%})")
    
    print(f"\nTotal Actual Legit Tested: {len(actual_legit)}")
    rules_fp = len(actual_legit[actual_legit['rule_caught'] == 1])
    ml_fp = len(actual_legit[actual_legit['ml_caught'] == 1])
    
    print(f"Rules False Positives (False Alarms): {rules_fp} / {len(actual_legit)}")
    print(f"ML False Positives (False Alarms)   : {ml_fp} / {len(actual_legit)}")
    
    # Why ML is better: Look at the frauds ML caught that rules missed
    evasive_frauds = actual_frauds[(actual_frauds['ml_caught'] == 1) & (actual_frauds['rule_caught'] == 0)]
    print(f"\n--- EVASIVE FRAUD (Caught by ML, Missed by Rules) ---")
    print(f"Number of evasive frauds caught perfectly by ML: {len(evasive_frauds)}")
    
    if not evasive_frauds.empty:
        print("\nExample of evasive fraud:")
        print(evasive_frauds[['amount', 'rule_score', 'ml_prob']].head(5))

    db.close()

if __name__ == "__main__":
    run_comparison()
