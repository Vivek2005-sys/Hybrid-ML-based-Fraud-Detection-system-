import pandas as pd
import sys
import os
from sqlalchemy import text

# Force Python to recognize the "app" package structure
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine 

print("Executing SQL Feature Extraction with Profile Window Functions on transactions...")

# SQL Query calculating 30m rolling features and 7d/30d historical profiles
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
        
        -- Rolling 30m Velocity Features
        COUNT(id) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_date 
            RANGE BETWEEN INTERVAL '30 minutes' PRECEDING AND CURRENT ROW
        ) AS velocity_30m_count,
        
        SUM(amount) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_date 
            RANGE BETWEEN INTERVAL '30 minutes' PRECEDING AND CURRENT ROW
        ) AS total_amount_30m,

        -- 7-Day Profile Features (Excluding Current Transaction)
        COUNT(id) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_date 
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND INTERVAL '1 second' PRECEDING
        ) AS p7d_txn_count,

        COALESCE(SUM(amount) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_date 
            RANGE BETWEEN INTERVAL '7 days' PRECEDING AND INTERVAL '1 second' PRECEDING
        ), 0.0) AS p7d_sum_amount,

        -- 30-Day Profile Features (Excluding Current Transaction)
        COUNT(id) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_date 
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '1 second' PRECEDING
        ) AS p30d_txn_count,

        COALESCE(AVG(amount) OVER (
            PARTITION BY customer_id 
            ORDER BY transaction_date 
            RANGE BETWEEN INTERVAL '30 days' PRECEDING AND INTERVAL '1 second' PRECEDING
        ), 0.0) AS p30d_avg_amount

    FROM transactions
""")

with engine.connect() as conn:
    df = pd.read_sql(query, conn)

print(f"Successfully loaded {len(df):,} transactions into memory.")
print("Evaluating All 10 Rules...")

df['transaction_date'] = pd.to_datetime(df['transaction_date'])
df['hour'] = df['transaction_date'].dt.hour

# Evaluate Individual Rules
r1 = df['velocity_30m_count'] >= 3
r2 = df['total_amount_30m'] >= 10000
r3 = (df['total_amount_30m'] >= 5000) & (df['merchant_category'].isin(['Electronics', 'Transport']))
r4 = (df['is_active_vpn'] == True) & (df['is_international'] == True)
r5 = (df['is_active_vpn'] == True) & (df['hour'] < 5)
r6 = (df['is_international'] == True) & (df['amount'] > 5000.0)
r7 = (df['hour'] >= 0) & (df['hour'] <= 4)
r8 = (df['p30d_txn_count'] > 0) & (df['amount'] > (df['p30d_avg_amount'] * 6.0))
r9 = (df['p7d_txn_count'] > 0) & (df['total_amount_30m'] >= (df['p7d_sum_amount'] * 0.9))
r10 = (df['p30d_txn_count'] == 0) & (df['amount'] >= 1000.0)

# Store per-rule triggers for audit reporting
df['rule_1'] = r1
df['rule_2'] = r2
df['rule_3'] = r3
df['rule_4'] = r4
df['rule_5'] = r5
df['rule_6'] = r6
df['rule_7'] = r7
df['rule_8'] = r8
df['rule_9'] = r9
df['rule_10'] = r10

# Master rule trigger
df['rule_triggered'] = r1 | r2 | r3 | r4 | r5 | r6 | r7 | r8 | r9 | r10

print("\n==================================================")
print("             RULE ENGINE EVALUATION SUMMARY       ")
print("==================================================\n")

fraud_df = df[df['is_fraud'] == 1]
total_fraud = len(fraud_df)

if total_fraud > 0:
    caught_by_rules = fraud_df['rule_triggered'].sum()
    missed_by_rules = total_fraud - caught_by_rules
    overall_recall = (caught_by_rules / total_fraud) * 100

    print(f"Total Fraud Transactions : {total_fraud:,}")
    print(f"Caught by Rule Engine    : {caught_by_rules:,}")
    print(f"Missed (ML Target)       : {missed_by_rules:,}")
    print(f"Overall Recall           : {overall_recall:.2f}%\n")

    print("--- Performance Breakdown per Rule ---")
    rule_names = {
        'rule_1': 'R1: High_Velocity_Window',
        'rule_2': 'R2: Velocity_Amount',
        'rule_3': 'R3: High_Value_Risky_Category',
        'rule_4': 'R4: VPN_International_Mismatch',
        'rule_5': 'R5: Night_Owl_VPN',
        'rule_6': 'R6: International_High_Limit',
        'rule_7': 'R7: Late_Night_Transaction',
        'rule_8': 'R8: Amount_Spike_vs_30D_Avg',
        'rule_9': 'R9: Rapid_Spend_vs_7D_Total',
        'rule_10': 'R10: Dormant_High_Value_Txn'
    }

    rule_stats = []
    for col, name in rule_names.items():
        caught = fraud_df[col].sum()
        rule_recall = (caught / total_fraud) * 100
        rule_stats.append({
            'Rule Name': name,
            'Fraud Caught': caught,
            'Recall Contribution (%)': round(rule_recall, 2)
        })

    rule_summary_df = pd.DataFrame(rule_stats)
    print(rule_summary_df.to_string(index=False))

    print("\n--- Recall Per Merchant Category ---")
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