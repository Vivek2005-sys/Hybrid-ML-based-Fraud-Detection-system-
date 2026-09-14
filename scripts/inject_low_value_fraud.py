"""
inject_low_value_fraud.py
=============================
Adds a NEW fraud archetype - "Low-Value Evasive Fraud" - directly into
your EXISTING transactions table, without regenerating the 1.5M-row
dataset from scratch. Calibrates each injected transaction to the
VICTIM'S OWN real historical average (pulled live from the database),
exactly mirroring the customer 3726 test case (small absolute amount,
extreme personal z-score) that revealed the training data gap.

USAGE:
    python inject_low_value_fraud.py

AFTER RUNNING THIS:
    1. Rerun your training_features CREATE TABLE AS query (the one from
       Week 4/5) to pick up these new rows - window functions need full
       recomputation, but you're rerunning existing SQL, not regenerating
       raw data.
    2. Retrain your models.
"""

import random
import uuid
from datetime import timedelta
from sqlalchemy import create_engine, text

random.seed(42)  # reproducibility, consistent with the rest of your project

DB_URL = "postgresql://fraud_user:securepassword@localhost:5433/fraud_db"
engine = create_engine(DB_URL)

# How many victim customers to target, and how many fraud episodes each
NUM_VICTIMS = 60          # spread across personas for realism
EPISODES_PER_VICTIM = (2, 3)   # each victim gets 2-3 separate fraud transactions

# The amount is calibrated to each victim's OWN real average, not a fixed number
MULTIPLIER_RANGE = (8, 15)     # 8-15x their real average
ABSOLUTE_CAP = 3000.0           # never exceed this, regardless of multiplier
ABSOLUTE_FLOOR = 300.0          # never go below this, keeps it a meaningful test


def get_candidate_customers(conn, n):
    """
    Selects n real customers who have enough transaction history to
    compute a meaningful average from (mirrors the >=5 prior txns guard
    used everywhere else in this project).
    """
    query = text("""
        SELECT customer_id, COUNT(*) as txn_count
        FROM transactions
        GROUP BY customer_id
        HAVING COUNT(*) >= 20
        ORDER BY RANDOM()
        LIMIT :n
    """)
    result = conn.execute(query, {"n": n}).fetchall()
    return [row.customer_id for row in result]


def get_victim_profile(conn, customer_id):
    """
    Pulls this customer's REAL average amount and their most recent
    transaction timestamp, so injected fraud is calibrated to real,
    current behaviour, not a hypothetical.
    """
    query = text("""
        SELECT AVG(amount) as avg_amount, MAX(transaction_date) as last_txn
        FROM transactions
        WHERE customer_id = :cust_id
    """)
    row = conn.execute(query, {"cust_id": customer_id}).fetchone()
    return float(row.avg_amount), row.last_txn


def build_fraud_transaction(customer_id, victim_avg, base_time):
    """
    One low-value evasive fraud transaction:
      - amount = victim_avg * (8 to 15x), capped between 300 and 3000
      - deliberately spaced (same evasion delay logic as Dynamic Rule
        Evasion) so this archetype ALSO stays evasive on velocity/timing,
        isolating the amount-side gap specifically
    """
    multiplier = random.uniform(*MULTIPLIER_RANGE)
    amount = victim_avg * multiplier
    amount = max(ABSOLUTE_FLOOR, min(amount, ABSOLUTE_CAP))
    amount = round(amount, 2)

    # same evasion-delay pattern as your existing Dynamic Rule Evasion scenario
    hypothetical_time_windows = [15, 30, 60]
    target_window = random.choice(hypothetical_time_windows)
    evasion_delay = target_window + random.randint(1, 5)
    txn_time = base_time + timedelta(minutes=evasion_delay)

    return {
        "id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "amount": amount,
        "merchant": "Unknown Merchant",   # distinct, filterable marker - same convention used during earlier manual testing
        "merchant_category": "Retail",     # deliberately NOT a high-risk category - isolates the amount signal
        "transaction_date": txn_time,
        "is_active_vpn": False,
        "is_international": False,
        "is_fraud": 1,
    }, txn_time


def main():
    with engine.begin() as conn:  # single transaction - all-or-nothing
        print("Selecting candidate victim customers...")
        candidates = get_candidate_customers(conn, NUM_VICTIMS)
        print(f"Selected {len(candidates)} customers with sufficient history.\n")

        all_new_rows = []
        summary = []

        for customer_id in candidates:
            victim_avg, last_txn_time = get_victim_profile(conn, customer_id)
            if victim_avg is None or victim_avg <= 0 or last_txn_time is None:
                continue  # skip anything malformed, don't silently guess

            n_episodes = random.randint(*EPISODES_PER_VICTIM)
            base_time = last_txn_time

            for _ in range(n_episodes):
                fraud_row, txn_time = build_fraud_transaction(customer_id, victim_avg, base_time)
                all_new_rows.append(fraud_row)
                base_time = txn_time  # next episode builds on this one's time, keeps them spread out

            summary.append({
                "customer_id": customer_id,
                "real_avg_amount": round(victim_avg, 2),
                "episodes_injected": n_episodes,
            })

        print(f"Constructed {len(all_new_rows)} new fraud transactions across {len(summary)} victims.\n")

        # Insert in one batch
        insert_query = text("""
            INSERT INTO transactions (
                id, customer_id, amount, merchant, merchant_category,
                transaction_date, is_active_vpn, is_international, is_fraud
            ) VALUES (
                :id, :customer_id, :amount, :merchant, :merchant_category,
                :transaction_date, :is_active_vpn, :is_international, :is_fraud
            )
        """)
        conn.execute(insert_query, all_new_rows)

        print("Insert complete. Sample of injected transactions:\n")
        for row in summary[:10]:
            print(f"  customer_id={row['customer_id']:<8} "
                  f"real_avg=Rs{row['real_avg_amount']:<10} "
                  f"episodes={row['episodes_injected']}")

    print(f"""
{'='*65}
DONE. {len(all_new_rows)} new "Low-Value Evasive Fraud" transactions
inserted directly into `transactions`, marked merchant='Unknown Merchant'
for easy identification/cleanup if needed:

    SELECT * FROM transactions WHERE merchant = 'Unknown Merchant';
    -- to remove if you ever need to:
    -- DELETE FROM transactions WHERE merchant = 'Unknown Merchant';

NEXT STEPS:
  1. DROP TABLE training_features;
  2. Rerun your training_features CREATE TABLE AS query (Week 4/5)
     to recompute all features, now including these new fraud rows
     and their effect on subsequent transactions' running stats.
  3. Retrain Random Forest (and your other models).
  4. Rerun test_single_transaction.py's Case A - check whether the
     model now catches low-absolute-amount, high-personal-deviation
     fraud after seeing real examples of this pattern during training.
{'='*65}
""")


if __name__ == "__main__":
    main()