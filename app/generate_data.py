import random
from faker import Faker
import sys
from sqlalchemy.orm import Session
import os
# This forces Python to look at the root folder so it understands the "app" package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import SessionLocal, engine
from app import models

# This forces the randomness to be exactly the same every time you run the script
random.seed(42)
Faker.seed(42)
# Initialize Faker and ensure tables are created
fake = Faker()
models.Base.metadata.create_all(bind=engine)

def generate_customers(num_customers=3000):
    db: Session = SessionLocal()
    
    # Clear out any old customers so we start fresh for the ML baseline
    db.query(models.Customer).delete()
    db.commit()

    print(f"Generating {num_customers} highly realistic customers for ML baselines...")
    
    # Our 3 core personas that will expose the rule engine flaws
    personas = ["Student", "Daily Spender", "High Roller"]
    
    # Standard baseline devices
    devices = ["iPhone 13", "iPhone 15", "Samsung Galaxy S23", "Windows PC", "MacBook Air"]
    
    customers_to_insert = []

    for _ in range(num_customers):
        # 60% Daily Spenders, 30% Students, 10% High Rollers
        assigned_persona = random.choices(personas, weights=[30, 60, 10])[0]
        
        # Determine if this user naturally uses a VPN for everyday browsing (approx 15% of people)
        usually_uses_vpn = random.choices([True, False], weights=[15, 85])[0]
        
        customer_data = {
            "first_name": fake.first_name(),
            "last_name": fake.last_name(),
            "email": fake.unique.email(),
            "phone_number": fake.phone_number(),
            "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=80),
            "primary_city": fake.city(),
            "primary_state": fake.state(),
            "account_creation_date": fake.date_time_between(start_date='-4y', end_date='now'),
            "persona_type": assigned_persona,
            "usual_login_device": random.choice(devices),
            "is_vpn_user": usually_uses_vpn
        }
        customers_to_insert.append(customer_data)
    
    # BULK INSERT: Pushes all 3,000 rows in seconds rather than minutes
    db.bulk_insert_mappings(models.Customer, customers_to_insert)
    db.commit()
    db.close()
    
    print(f"✅ Successfully inserted {num_customers} baseline customers into the database!")

if __name__ == "__main__":
    generate_customers(3000)