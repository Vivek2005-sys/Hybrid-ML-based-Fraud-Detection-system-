import json
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel
from json_logic import jsonLogic
from . import rule_engine 

# Imports your database configuration and SQLAlchemy models
from . import models, database

# Automatically creates tables in PostgreSQL if they do not exist
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Fraud Detection API")

# --- LOAD RULES DYNAMICALLY ---
print("Loading JSON Logic Rules from rules.json...")
try:
    # Changed path to point to the correct Docker working directory
    with open('./app/rules.json', 'r') as f:
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
    total_risk_score: float
    risk_level: str
    velocity_30m_count: int
    max_rule_score: float
    triggered_rules: List[RuleTrigger]

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
    # Use current UTC time if no date is provided by Postman
    txn_time = txn.transaction_date or datetime.utcnow()

    db_txn = models.Transaction(
        customer_id=txn.customer_id,
        amount=txn.amount,
        merchant=txn.merchant,
        merchant_category=txn.merchant_category,
        is_active_vpn=txn.is_active_vpn,
        is_international=txn.is_international,
        transaction_date=txn_time,
        is_fraud=0  # Default to 0 upon entry
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


@app.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    txn = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()

    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")

    db.delete(txn)
    db.commit()

    return {
        "status": "success",
        "message": f"Transaction {transaction_id} permanently deleted."
    }

# --- LIVE SCORING ENDPOINT ---



@app.post("/score", response_model=ScoreResponse)
def score_transaction(txn: TransactionRequest, db: Session = Depends(get_db)):
    txn_time = txn.transaction_date or (datetime.utcnow() + timedelta(hours=5, minutes=30))

    # <-- ADD THIS LINE: Strip the timezone awareness so it matches the database -->
    txn_time = txn_time.replace(tzinfo=None)

    # 1. Hand off to the Rule Engine Module (Now expecting 5 returned variables)
    total_score, max_rule_score, risk_level, current_velocity, triggered_rules, observations = rule_engine.evaluate_transaction(db, txn, txn_time)

    # 2. Save the Test Data
    new_test_score = models.TransactionScore(
        customer_id=txn.customer_id,
        amount=txn.amount,
        merchant=txn.merchant,
        merchant_category=txn.merchant_category,
        transaction_date=txn_time,
        is_active_vpn=txn.is_active_vpn,
        is_international=txn.is_international,
        total_risk_score=total_score,
        observations=observations,
        max_rule_score=max_rule_score,  # <-- ADD THIS LINE
        risk_level=risk_level,
        velocity_30m_count=current_velocity,
        triggered_rules=triggered_rules
    )
    db.add(new_test_score)
    db.commit()

    return ScoreResponse(
        customer_id=txn.customer_id,
        amount=txn.amount,
        total_risk_score=total_score,
        max_rule_score=max_rule_score,  # <-- ADD THIS LINE
        risk_level=risk_level,
        velocity_30m_count=current_velocity,
        triggered_rules=triggered_rules
    )
    
