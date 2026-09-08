import json
import os
import joblib
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
import logging
import traceback
import pandas as pd
from datetime import datetime, timedelta
from fastapi import Depends
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from json_logic import jsonLogic

from . import models, database
from rules import rule_engine

# Automatically creates tables in PostgreSQL if they do not exist
models.Base.metadata.create_all(bind=database.engine)

# --- ML CHAMPION MODEL & FEATURE CONFIGURATION ---
FEATURE_COLS = [
    'amount', 'is_active_vpn', 'is_international',
    'minutes_since_last_txn_clean', 'gap_volatility_5tx_clean', 'amount_z_score', 'merchant_diversity_7d',
    'hour_of_day', 'is_night_txn', 'is_high_risk_category',
    'p7d_txn_count', 'p7d_avg_amount', 'p7d_sum_amount', 'p7d_std_amount',
    'p30d_txn_count', 'p30d_avg_amount', 'p30d_sum_amount', 'p30d_std_amount',
    'p90d_txn_count', 'p90d_avg_amount'
]

DECISION_THRESHOLD = 0.20
ml_artifacts: Dict[str, Any] = {}

import shap

# --- FASTAPI LIFESPAN (Load Model Once on Startup) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Attempt to load champion model from root ml_features directory
    model_path = "ml_features/champion_model.pkl"
    if not os.path.exists(model_path):
        model_path = "./ml_features/champion_model.pkl"

    try:
        ml_artifacts["champion_model"] = joblib.load(model_path)
        print("✅ Champion XGBoost model loaded into RAM successfully.")
        
        # Initialize SHAP explainer
        ml_artifacts["explainer"] = shap.TreeExplainer(ml_artifacts["champion_model"])
        print("✅ SHAP TreeExplainer initialized successfully.")
    except Exception as e:
        print(f"⚠️ Warning: Could not load champion_model.pkl or initialize SHAP: {e}")
        ml_artifacts["champion_model"] = None
        ml_artifacts["explainer"] = None
    yield
    ml_artifacts.clear()

app = FastAPI(title="Fraud Detection API", lifespan=lifespan)

# --- LOAD RULES DYNAMICALLY ---
print("Loading JSON Logic Rules from rules.json...")
try:
    with open('./rules/rules.json', 'r') as f:
        rules_data = json.load(f)
    LEGACY_RULES = rules_data.get('rules', [])
    print(f"Successfully loaded {len(LEGACY_RULES)} rules.")
except Exception as e:
    print(f"Warning: Could not load rules.json: {e}")
    LEGACY_RULES = []

# Dependency to safely open and close the database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Pydantic Schemas (Input Data Shapes) ---

class CustomerRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone_number: str
    date_of_birth: date
    primary_city: str
    primary_state: str
    persona_type: str
    usual_login_device: str
    is_vpn_user: Optional[bool] = False

class TransactionRequest(BaseModel):
    customer_id: int
    amount: float
    merchant: str
    merchant_category: str
    is_active_vpn: Optional[bool] = False
    is_international: Optional[bool] = False
    transaction_date: Optional[datetime] = None

class RuleTrigger(BaseModel):
    rule_id: str
    rule_name: str
    score_impact: float
    description: str

class ScoreResponse(BaseModel):
    customer_id: int
    amount: float
    final_score: float
    results: Dict[str, Any]

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"status": "System Online"}


# --- CUSTOMER ENDPOINTS ---

@app.post("/customers")
def create_customer(cust: CustomerRequest, db: Session = Depends(get_db)):
    db_cust = models.Customer(
        first_name=cust.first_name,
        last_name=cust.last_name,
        email=cust.email,
        phone_number=cust.phone_number,
        date_of_birth=cust.date_of_birth,
        primary_city=cust.primary_city,
        primary_state=cust.primary_state,
        persona_type=cust.persona_type,
        usual_login_device=cust.usual_login_device,
        is_vpn_user=cust.is_vpn_user
    )
    db.add(db_cust)
    db.commit()
    db.refresh(db_cust)
    return {
        "status": "success",
        "customer_id": db_cust.id,
        "first_name": db_cust.first_name,
        "last_name": db_cust.last_name,
        "persona_type": db_cust.persona_type
    }


@app.get("/customers")
def get_all_customers(db: Session = Depends(get_db)):
    customers = db.query(models.Customer).all()
    return {
        "status": "success",
        "total_results": len(customers),
        "data": customers
    }


@app.delete("/customers/{customer_id}")
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    cust = db.query(models.Customer).filter(models.Customer.id == customer_id).first()

    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")

    db.delete(cust)
    db.commit()

    return {
        "status": "success",
        "message": f"Customer {customer_id} permanently deleted."
    }


# --- TRANSACTION ENDPOINTS ---

@app.post("/transactions")
def create_transaction(txn: TransactionRequest, db: Session = Depends(get_db)):
    txn_time = txn.transaction_date or datetime.utcnow()

    db_txn = models.Transaction(
        customer_id=txn.customer_id,
        amount=txn.amount,
        merchant=txn.merchant,
        merchant_category=txn.merchant_category,
        is_active_vpn=txn.is_active_vpn,
        is_international=txn.is_international,
        transaction_date=txn_time,
        is_fraud=0
    )
    db.add(db_txn)
    db.commit()
    db.refresh(db_txn)

    return {
        "status": "success",
        "transaction_id": db_txn.id,
        "customer_id": db_txn.customer_id,
        "amount": db_txn.amount,
        "merchant": db_txn.merchant
    }


@app.get("/transactions")
def get_all_transactions(db: Session = Depends(get_db)):
    transactions = db.query(models.Transaction).all()
    return {
        "status": "success",
        "total_results": len(transactions),
        "data": transactions
    }


@app.get("/transactions/{transaction_id}")
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    return {"status": "success", "data": txn}




logger = logging.getLogger("uvicorn.error")

@app.post("/score", response_model=ScoreResponse)
def score_transaction(txn: TransactionRequest, db: Session = Depends(get_db)):
    txn_time = txn.transaction_date or (datetime.utcnow() + timedelta(hours=5, minutes=30))
    txn_time = txn_time.replace(tzinfo=None)

    # 1. Evaluate Rule Engine & Retrieve Computed Feature Snapshot
    total_score, max_rule_score, risk_level, current_velocity, triggered_rules, observations = rule_engine.evaluate_transaction(db, txn, txn_time)

    # 2. Evaluate ML Champion Model using the returned 'observations' snapshot
    ml_model = ml_artifacts.get("champion_model")
    ml_score = 0.0
    ml_explanation = []
    ml_narrative = "Explainability skipped."

    if ml_model is not None and isinstance(observations, dict):
        try:
            # Flatten features from transaction and ml_snapshot
            flat_features = {
                'amount': txn.amount,
                'is_active_vpn': int(txn.is_active_vpn) if txn.is_active_vpn else 0,
                'is_international': int(txn.is_international) if txn.is_international else 0
            }
            
            ml_snapshot = observations.get("ml_features", {})
            flat_features.update(ml_snapshot)
            
            df_input = pd.DataFrame([flat_features])

            # [ADDITION 1] Convert booleans to integers (XGBoost requirement)
            for col in df_input.columns:
                if df_input[col].dtype == 'bool':
                    df_input[col] = df_input[col].astype(int)

            # [ADDITION 2] Ensure missing expected columns exist and log mismatches
            missing_cols = [c for c in FEATURE_COLS if c not in df_input.columns]
            if missing_cols:
                logger.warning(f"⚠️ Features missing from observations (defaulted to 0.0): {missing_cols}")
                for col in missing_cols:
                    df_input[col] = 0.0

            # Select exact feature set in strict training column order
            X_input = df_input[FEATURE_COLS].astype(float)

            # [ADDITION 3] Predict probability
            probs = ml_model.predict_proba(X_input)
            ml_score = float(probs[0][1])
            logger.info(f"✅ Calculated ML Fraud Score: {ml_score:.4f}")

            # [ADDITION 4] Compute SHAP Explainability
            explainer = ml_artifacts.get("explainer")
            from ml_features.shap_explainer import generate_explanation
            ml_explanation, ml_narrative = generate_explanation(explainer, X_input, FEATURE_COLS, ml_score, DECISION_THRESHOLD)

        except Exception as e:
            logger.error(f"❌ ML Prediction Failed: {str(e)}")
            logger.error(traceback.format_exc())
            ml_score = 0.0
            ml_explanation = [{"error": "SHAP explanation failed"}]
            ml_narrative = "Explainability engine encountered an error."
    else:
        logger.warning(f"⚠️ Skipping ML Scoring: Model loaded={ml_model is not None}, Dict snapshot={isinstance(observations, dict)}")

    # 3. Compute Max Risk & Final Decision Action
    normalized_rule_score = min(max_rule_score / 100.0, 1.0) if max_rule_score > 1.0 else max_rule_score
    unified_score = round(max(normalized_rule_score, ml_score), 4)

    if max_rule_score >= 100 or unified_score >= 0.70:
        final_action = "BLOCK"
        final_risk_level = "HIGH"
    elif unified_score >= DECISION_THRESHOLD:
        final_action = "REVIEW"
        final_risk_level = "MEDIUM"
    else:
        final_action = "ALLOW"
        final_risk_level = "LOW"

    # 4. Save Test Data to Database
    results = {
        "max_rule_score": max_rule_score,
        "ml_fraud_score": round(ml_score, 4),
        "ml_explanation": ml_explanation,
        "ml_narrative": ml_narrative,
        "risk_level": final_risk_level,
        "final_action": final_action,
        "triggered_rules": triggered_rules
    }

    new_test_score = models.TransactionScore(
        customer_id=txn.customer_id,
        amount=txn.amount,
        merchant=txn.merchant,
        merchant_category=txn.merchant_category,
        transaction_date=txn_time,
        is_active_vpn=txn.is_active_vpn,
        is_international=txn.is_international,
        observations=observations,
        results=results,
        velocity_30m_count=current_velocity,
        final_score=unified_score
    )
    db.add(new_test_score)
    db.commit()

    # 5. Return Unified Hybrid Response
    return ScoreResponse(
        customer_id=txn.customer_id,
        amount=txn.amount,
        final_score=unified_score,
        results=results
    )