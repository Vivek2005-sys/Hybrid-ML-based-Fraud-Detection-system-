import numpy as np
from datetime import timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

def get_observation_snapshot(db: Session, customer_id: int, current_amount: float, current_merchant: str, txn_time):
    """
    Real-time Observation Engine
    Calculates ML features on the fly for incoming transactions and handles Cold Starts gracefully.
    """
    # 1. Fetch a bounded recent history (Limit 50 is plenty for a 7-day lookback)
    # Note: Change 'transaction_scores' to your actual raw table name if different
    query = text("""
        SELECT amount, merchant_category, transaction_date 
        FROM transactions
        WHERE customer_id = :cust_id 
          AND transaction_date < :time
        ORDER BY transaction_date DESC;
    """)
    
    history = db.execute(query, {"cust_id": customer_id, "time": txn_time}).fetchall()
    
    # 2. Base Features & Cold Start Defaults
    ml_features = {
        'minutes_since_last_txn_clean': 99999.0,
        'amount_z_score': 0.0,
        'gap_volatility_5tx_clean': 0.0,
        'merchant_diversity_7d': 1,
        'hour_of_day': txn_time.hour,
        'day_of_week': txn_time.weekday(),
        'is_weekend': 1 if txn_time.weekday() >= 5 else 0,
        'is_night_txn': 1 if txn_time.hour < 5 else 0,
        'is_high_risk_category': 1 if current_merchant in ['Luxury Goods', 'Financial Services', 'Gaming'] else 0

    }
    
    # If no history exists, return the defaults instantly (Extreme Cold Start)
    if not history:
        return ml_features 
        
    amounts = [float(row.amount) for row in history]
    dates = [row.transaction_date for row in history]
    
    # 3. Calculate Time Gap
    ml_features['minutes_since_last_txn_clean'] = round((txn_time - dates[0]).total_seconds() / 60.0, 2)
    
    # 4. Calculate Z-Score (Requires at least 5 prior txns)
    if len(amounts) > 5:
        hist_avg = sum(amounts) / len(amounts)
        hist_std = np.std(amounts, ddof=1)
        if hist_std > 0:
            ml_features['amount_z_score'] = round((current_amount - hist_avg) / hist_std, 3)
            
    # 5. Calculate Burstiness / Gap Volatility (Requires at least 2 prior txns)
    if len(dates) >= 2:
        # Include current txn time in the recent times list (up to 6 dates for 5 gaps)
        recent_times = [txn_time] + dates[:5]
        gaps = [(recent_times[i] - recent_times[i+1]).total_seconds() / 60.0 for i in range(len(recent_times)-1)]
        if len(gaps) > 1:
            ml_features['gap_volatility_5tx_clean'] = round(float(np.std(gaps, ddof=1)), 2)
            
    # 6. Calculate Merchant Diversity (7-day lookback)
    cutoff_7d = txn_time - timedelta(days=7)
    recent_merchants = {row.merchant_category for row in history if row.transaction_date >= cutoff_7d}
    recent_merchants.add(current_merchant) # Always include the one they are visiting right now
    ml_features['merchant_diversity_7d'] = len(recent_merchants)
    
    return ml_features