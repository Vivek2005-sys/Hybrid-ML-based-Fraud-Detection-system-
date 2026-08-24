import uuid
from sqlalchemy import Column, Integer, Float, String, ForeignKey , DateTime ,Date ,Boolean,JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from .database import Base

# --- NEW: Helper function to generate IST Time ---
def get_ist_time():
    return datetime.utcnow() + timedelta(hours=5, minutes=30)
# 1. The New Customer Table
class Customer(Base):
    __tablename__ = "customers"
    
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True, index=True)
    phone_number = Column(String)
    date_of_birth = Column(Date)

    # Behavioral Anchors for the ML Model
    primary_city = Column(String)
    primary_state = Column(String)
    account_creation_date = Column(DateTime, default=get_ist_time)
    persona_type = Column(String)
    usual_login_device = Column(String)
    is_vpn_user = Column(Boolean, default=False)

    # This creates a virtual link to see all transactions for a customer
    transactions = relationship("Transaction", back_populates="customer")
    
    
    
# 2. The Updated Transaction Table
class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    
    amount = Column(Float)
    merchant = Column(String)
    merchant_category = Column(String) # e.g., Groceries, Electronics
    transaction_date = Column(DateTime, default=get_ist_time, index=True)
    
    # Fraud tracking features
    is_active_vpn = Column(Boolean, default=False)
    is_international = Column(Boolean, default=False)
    is_fraud = Column(Integer, default=0) # 0 for Normal, 1 for Fraud
    
    customer = relationship("Customer", back_populates="transactions")


class TransactionScore(Base):
    __tablename__ = "transaction_scores"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # The raw inputs you sent via Postman
    customer_id = Column(Integer)
    amount = Column(Float)
    merchant = Column(String)
    merchant_category = Column(String)
    transaction_date = Column(DateTime, default=get_ist_time)
    is_active_vpn = Column(Boolean, default=False)
    is_international = Column(Boolean, default=False)
    observations = Column(JSON, default=dict)
    
    # The Rule Engine Outputs
    total_risk_score = Column(Float, default=0.0)
    max_rule_score = Column(Float, default=0.0)  # <-- ADD THIS LINE
    risk_level = Column(String, default="LOW - ALLOW")
    risk_level = Column(String, default="LOW - ALLOW")
    velocity_30m_count = Column(Integer, default=1)
    triggered_rules = Column(JSON, default=list)
    