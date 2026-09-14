import sys
import os
import random
import uuid
from datetime import datetime, timedelta

# Force Python to recognize the "app" package structure
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, engine
from app import models

# --- THE SEED FIX ---
random.seed(42)
uuid.UUID(int=random.getrandbits(128), version=4)

models.Base.metadata.create_all(bind=engine)

def random_date(start, end):
    delta = end - start
    int_delta = (delta.days * 24 * 60 * 60) + delta.seconds
    random_second = random.randrange(int_delta)
    return start + timedelta(seconds=random_second)

def generate_transactions():
    db = SessionLocal()
    
    print("Clearing old transactions...")
    db.query(models.Transaction).delete()
    db.commit()

    customers = db.query(models.Customer).all()
    if not customers:
        print("No customers found! Please run generate_data.py first.")
        return

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365) 
    
    transactions_batch = []
    total_inserted = 0

    print(f"Generating 1 year of transactions for {len(customers)} customers...")

    for customer in customers:
        if customer.persona_type == "Student":
            annual_count = random.randint(600, 900)
            avg_amt, amt_variance = 15.0, 10.0
            categories = ["Food Delivery", "Streaming", "Transport", "Gaming"]
        elif customer.persona_type == "Daily Spender":
            annual_count = random.randint(300, 600)
            avg_amt, amt_variance = 80.0, 50.0
            categories = ["Groceries", "Fuel", "Retail", "Utilities"]
        else: 
            annual_count = random.randint(50, 150)
            avg_amt, amt_variance = 5000.0, 3000.0
            categories = ["Airlines", "Luxury Goods", "Hotels", "Fine Dining"]

        # --- 2. GENERATE NORMAL BASELINE (97%) ---
        customer_txns = []
        for _ in range(annual_count):
            txn_date = random_date(start_date, end_date)
            amount = max(2.0, random.gauss(avg_amt, amt_variance))
            
            customer_txns.append({
                "id": str(uuid.uuid4()),
                "customer_id": customer.id,
                "amount": round(amount, 2),
                "merchant": f"Merchant_{random.randint(1, 100)}",
                "merchant_category": random.choice(categories),
                "transaction_date": txn_date,
                "is_active_vpn": customer.is_vpn_user, 
                "is_international": random.choices([True, False], weights=[5, 95])[0],
                "is_fraud": 0
            })

        # --- 3. INJECT TARGETED FRAUD (Boosted for ML Training) ---
        if random.random() < 0.40:
            num_attacks = random.randint(3, 7)
            for _ in range(num_attacks):
                attack_time = random_date(start_date, end_date)
            
                if customer.persona_type == "Daily Spender" and random.random() < 0.5:
                    hypothetical_limits = [1500.0, 3000.0, 4800.0] 
                    target_limit = random.choice(hypothetical_limits)
                    evasion_amount = target_limit - random.randint(10, 50) 
                    
                    hypothetical_time_windows = [15, 30, 60] 
                    target_window = random.choice(hypothetical_time_windows)
                    evasion_delay = target_window + random.randint(1, 5) 
                    
                    txn1 = {
                        "id": str(uuid.uuid4()), "customer_id": customer.id, "amount": evasion_amount,
                        "merchant": "Standard Retail", "merchant_category": "Retail", 
                        "transaction_date": attack_time, "is_active_vpn": customer.is_vpn_user,
                        "is_international": False, "is_fraud": 1
                    }
                    txn2 = txn1.copy()
                    txn2["id"] = str(uuid.uuid4())
                    txn2["transaction_date"] = attack_time + timedelta(minutes=evasion_delay) 
                    
                    customer_txns.extend([txn1, txn2])

                elif customer.persona_type == "High Roller":
                    # 50% Chance: Blunt Force Attack (Will get caught by rules)
                    if random.random() < 0.5:
                        customer_txns.append({
                            "id": str(uuid.uuid4()), "customer_id": customer.id, "amount": 49000.0,
                            "merchant": "Offshore Wire", "merchant_category": "Financial Services",
                            "transaction_date": attack_time, 
                            "is_active_vpn": not customer.is_vpn_user, # Trips VPN rule
                            "is_international": True, "is_fraud": 1
                        })
                    # 50% Chance: Evasive Domestic Transfer (Will be missed by rules)
                    else:
                        customer_txns.append({
                            "id": str(uuid.uuid4()), "customer_id": customer.id, 
                            "amount": random.choice([3500.0, 4200.0, 4800.0]), # Stays under $5,000 limit
                            "merchant": "Domestic Transfer", "merchant_category": "Financial Services",
                            "transaction_date": attack_time, 
                            "is_active_vpn": customer.is_vpn_user, # Looks like normal login
                            "is_international": False, # Bypasses GEO_001 rule
                            "is_fraud": 1
                        })

                elif customer.persona_type == "Student":
                    customer_txns.append({
                        "id": str(uuid.uuid4()), "customer_id": customer.id, "amount": 150000.0,
                        "merchant": "Luxury Auto", "merchant_category": "Automotive",
                        "transaction_date": attack_time, "is_active_vpn": True,
                        "is_international": False, "is_fraud": 1
                    })

        # THIS IS THE FIX: Completely outside the IF block!
        transactions_batch.extend(customer_txns)

        # --- 4. BATCH INSERT (Protects RAM) ---
        if len(transactions_batch) >= 10000:
            db.bulk_insert_mappings(models.Transaction, transactions_batch)
            db.commit()
            total_inserted += len(transactions_batch)
            print(f"Inserted {total_inserted} transactions...")
            transactions_batch = [] 

    if transactions_batch:
        db.bulk_insert_mappings(models.Transaction, transactions_batch)
        db.commit()
        total_inserted += len(transactions_batch)
        
    db.close()
    print(f"✅ SUCCESS! Generated and inserted {total_inserted} historical transactions.")

if __name__ == "__main__":
    generate_transactions()