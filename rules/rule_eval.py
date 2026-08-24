import pandas as pd
import sys
import os
from sqlalchemy import text

# Force Python to recognize the "app" package structure
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine 

print("Executing SQL Feature Extraction on 1.5M rows (This will take 1-2 minutes)...")

# We use PostgreSQL Window Functions to calculate the 30-minute rolling features 
query = text("""
    SELECT 
        id, 
        customer_id, 
        amount, 
        merchant_category, 
        is_active_vpn, 
        is_international, 
        transaction_date, 
        is_fraud, 
        
        -- Calculate Rolling 30m Count
        COUNT(id) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_date 
            RANGE BETWEEN INTERVAL '30 minutes' PRECEDING AND CURRENT ROW
        ) AS velocity_30m_count,
        
        -- Calculate Rolling 30m Amount
        SUM(amount) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_date 
            RANGE BETWEEN INTERVAL '30 minutes' PRECEDING AND CURRENT ROW
        ) AS total_amount_30m
        
    FROM transactions
""")

# Load the aggregated data into a Pandas DataFrame
with engine.connect() as conn:
    df = pd.read_sql(query, conn)

print(f"Successfully loaded {len(df):,} transactions into memory.")
print("Evaluating Custom Rules...")

# Initialize rule flags
df['rule_triggered'] = False
df['transaction_date'] = pd.to_datetime(df['transaction_date'])

# Rule 1: High_Velocity_Window (VEL_001)
df.loc[df['velocity_30m_count'] >= 3, 'rule_triggered'] = True

# Rule 2: Velocity_Amount (VEL_002)
df.loc[df['total_amount_30m'] >= 5000, 'rule_triggered'] = True

# Rule 3: High_Value_Risky_Category (CAT_AMT_001)
risky_cats = ['Electronics', 'Transport']
df.loc[(df['total_amount_30m'] >= 1000) & (df['merchant_category'].isin(risky_cats)), 'rule_triggered'] = True

# Rule 4: VPN_International_Mismatch (GEO_001)
df.loc[(df['is_active_vpn'] == True) & (df['is_international'] == True), 'rule_triggered'] = True

# Rule 5: Late_Night_Transaction (TIME_001)
df.loc[(df['transaction_date'].dt.hour >= 0) & (df['transaction_date'].dt.hour <= 4), 'rule_triggered'] = True

print("\n==================================================")
print("            WEEK 3: RULE ENGINE RECALL            ")
print("==================================================\n")

# Filter to ONLY the actual fraud transactions to calculate Recall
fraud_df = df[df['is_fraud'] == 1]

# Calculate overall recall
total_fraud = len(fraud_df)
if total_fraud > 0:
    caught_by_rules = fraud_df['rule_triggered'].sum()
    missed_by_rules = total_fraud - caught_by_rules
    overall_recall = (caught_by_rules / total_fraud) * 100

    print(f"Total Fraud Transactions: {total_fraud:,}")
    print(f"Caught by Rule Engine:    {caught_by_rules:,}")
    print(f"Missed (The ML Target):   {missed_by_rules:,}")
    print(f"Overall Recall:           {overall_recall:.2f}%\n")

    # Group by Merchant Category to show exactly WHAT slipped through
    print("--- Recall Per Merchant Category ---")
    recall_table = fraud_df.groupby('merchant_category').agg(
        Total_Fraud_Cases=('id', 'count'),
        Caught_By_Rules=('rule_triggered', 'sum')
    )
    recall_table['Missed_By_Rules'] = recall_table['Total_Fraud_Cases'] - recall_table['Caught_By_Rules']
    recall_table['Recall (%)'] = (recall_table['Caught_By_Rules'] / recall_table['Total_Fraud_Cases']) * 100
    
    print(recall_table.round(2).to_string())
else:
    print("No fraud transactions found in the dataset to evaluate.")
print("\n==================================================")