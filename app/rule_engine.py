import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from json_logic import jsonLogic
from . import models
from ml_features.observations import get_observation_snapshot

# Load JSON Logic Rules once when the engine starts
try:
    with open('./rules/rules.json', 'r') as f:
        rules_data = json.load(f)
    RULES = rules_data.get('rules', [])
    print(f"Rule Engine Online: {len(RULES)} rules loaded.")
except Exception as e:
    print(f"Warning: Could not load rules.json: {e}")
    RULES = []

def evaluate_transaction(db: Session, txn, txn_time: datetime):
    total_score = 0.0
    max_rule_score = 0.0
    triggered_rules = []
    
   # 1. Build the Context (Feature Extraction) - Anchored Burst Window
    
    # Find the exact transaction that started the most recent sequence
    anchor_txn = db.query(models.TransactionScore).filter(
        models.TransactionScore.customer_id == txn.customer_id,
        models.TransactionScore.transaction_date < txn_time,
        models.TransactionScore.velocity_30m_count == 1
    ).order_by(models.TransactionScore.transaction_date.desc()).first()

    # Check if the current transaction is within 30 minutes of that specific anchor
    if anchor_txn and txn_time <= anchor_txn.transaction_date + timedelta(minutes=30):
        window_start = anchor_txn.transaction_date
    else:
        # The 30-minute timer expired! Start a brand new window.
        window_start = txn_time

    # Count the transactions strictly inside this specific window
    recent_txns = db.query(models.TransactionScore).filter(
        models.TransactionScore.customer_id == txn.customer_id,
        models.TransactionScore.transaction_date >= window_start,
        models.TransactionScore.transaction_date < txn_time 
    )
    
    recent_txn_count = recent_txns.count()
    past_amount = db.query(func.sum(models.TransactionScore.amount)).filter(
        models.TransactionScore.customer_id == txn.customer_id,
        models.TransactionScore.transaction_date >= window_start,
        models.TransactionScore.transaction_date < txn_time
    ).scalar() or 0.0

    current_velocity = recent_txn_count + 1
    total_amount_30m = past_amount + txn.amount

    # <-- NEW FEATURE EXTRACTION: Personal Baseline Calculation -->
    # Get the total number of transactions made by the customer prior to this one
    prior_txn_count = db.query(models.TransactionScore).filter(
        models.TransactionScore.customer_id == txn.customer_id,
        models.TransactionScore.transaction_date < txn_time
    ).count()

    # Calculate average 30m velocity baseline
    avg_txn_count_30m_baseline = 1.0  # Default safe baseline to avoid division by zero
    
    if prior_txn_count > 0:
        # Find the very first time this customer ever made a transaction
        first_txn_date = db.query(func.min(models.TransactionScore.transaction_date)).filter(
            models.TransactionScore.customer_id == txn.customer_id
        ).scalar()
        
        if first_txn_date:
            # Calculate total minutes between their first transaction and now
            total_minutes_active = (txn_time - first_txn_date).total_seconds() / 60.0
            # Calculate how many 30-minute windows they have been active for (min 1 window)
            total_30m_windows = max(total_minutes_active / 30.0, 1.0)
            # Divide total transactions by total windows to get their typical pace
            avg_txn_count_30m_baseline = prior_txn_count / total_30m_windows
    # =========================================================================

    # Fetch the customer details for the observations payload
    customer = db.query(models.Customer).filter(models.Customer.id == txn.customer_id).first()
  
    
    customer_data = {}
    if customer:
        customer_data = {
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "email": customer.email,
            "primary_city": customer.primary_city,
            "persona_type": customer.persona_type,
            "usual_login_device": customer.usual_login_device
        }

    # <-- NEW: Fetch real-time ML feature snapshot in milliseconds -->
    ml_snapshot = get_observation_snapshot(
        db=db,
        customer_id=txn.customer_id,
        current_amount=txn.amount,
        current_merchant=txn.merchant_category,
        txn_time=txn_time
    )

    # Build the Context for JSON Rules AND the Observations Payload
    rule_context = {
        "amount": txn.amount,
        "is_active_vpn": txn.is_active_vpn,
        "is_international": txn.is_international,
        "hour": txn_time.hour,
        "txn_count_30m": current_velocity,
        "total_amount_30m": total_amount_30m,
        "merchant_category": txn.merchant_category,
        "prior_txn_count": prior_txn_count,                               # <-- NEW
        "avg_txn_count_30m_baseline": avg_txn_count_30m_baseline
        
    }

    # <-- NEW: Build the final Drona Pay style observations dictionary -->
    observations = {
        "customer": customer_data,
        "velocity_features": {
            "txn_count_30m": current_velocity,
            "total_amount_30m": total_amount_30m,
            "prior_txn_count": prior_txn_count,                           # <-- NEW
            "avg_txn_count_30m_baseline": round(avg_txn_count_30m_baseline, 2)  # <-- NEW
            
        },
        "ml_features": ml_snapshot
    }



    # 2. Evaluate Context Against JSON Rules
    for rule in RULES:
        try:
            rule_logic = rule.get('condition', rule.get('logic', {}))
            if jsonLogic(rule_logic, rule_context):
                score_impact = rule.get('score_impact', rule.get('score', 20.0)) 
                total_score += score_impact
                
                # <-- 2. Update the max_rule_score if this rule is higher
                if score_impact > max_rule_score:
                    max_rule_score = score_impact
                
                triggered_rules.append({
                    "rule_id": rule['rule_id'], 
                    "rule_name": rule.get('rule_name', rule.get('name', 'Unknown Rule')), 
                    "score_impact": score_impact, 
                    "description": rule['description']
                })
        except Exception as e:
            print(f"Error evaluating JSON Logic rule {rule.get('rule_id', 'Unknown')}: {e}")

    # 3. Determine Final Risk Classification
    if total_score >= 60:
        risk_level = "CRITICAL - BLOCK"
    elif total_score >= 30:
        risk_level = "MEDIUM - FLAG"
    else:
        risk_level = "LOW - ALLOW"

    return total_score, max_rule_score, risk_level, current_velocity, triggered_rules, observations