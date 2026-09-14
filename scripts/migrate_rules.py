import json
import uuid
import os
from sqlalchemy.orm import Session
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../'))
from app.database import SessionLocal
from app.models import Rule

def migrate_rules():
    db = SessionLocal()
    
    # Load old rules
    try:
        with open('./rules/rules.json', 'r') as f:
            data = json.load(f)
            old_rules = data.get('rules', [])
    except Exception as e:
        print(f"Error loading rules.json: {e}")
        return

    # Delete existing rules to start fresh (for dev mode)
    db.query(Rule).delete()

    for r in old_rules:
        name = r.get("name")
        desc = r.get("description")
        score = r.get("score")
        logic = r.get("logic")
        
        # We will extract parameters manually based on known rules to build the parameter dictionary
        parameters = {}
        
        if name == "High_Velocity_Window":
            parameters["txn_count_threshold"] = 3
            logic = {">=": [{"var": "txn_count_30m"}, {"var": "parameters.txn_count_threshold"}]}
        
        elif name == "Velocity_Amount":
            parameters["total_amount_threshold"] = 50000
            logic = {">=": [{"var": "total_amount_30m"}, {"var": "parameters.total_amount_threshold"}]}
            
        elif name == "High_Value_Risky_Category":
            parameters["total_amount_threshold"] = 5000.0
            logic = {
                "and": [
                    {"in": [{"var": "merchant_category"}, ["Electronics", "Transport"]]},
                    {">=": [{"var": "total_amount_30m"}, {"var": "parameters.total_amount_threshold"}]}
                ]
            }
            
        elif name == "Night_Owl_VPN":
            parameters["max_hour"] = 5
            logic = {
                "and": [
                    {"==": [{"var": "is_active_vpn"}, True]},
                    {"<": [{"var": "hour"}, {"var": "parameters.max_hour"}]}
                ]
            }
            
        elif name == "International_High_Limit":
            parameters["amount_threshold"] = 5000.0
            logic = {
                "and": [
                    {"==": [{"var": "is_international"}, True]},
                    {">": [{"var": "amount"}, {"var": "parameters.amount_threshold"}]}
                ]
            }
            
        elif name == "Late_Night_Transaction":
            parameters["min_hour"] = 0
            parameters["max_hour"] = 4
            logic = {
                "and": [
                    {">=": [{"var": "hour"}, {"var": "parameters.min_hour"}]},
                    {"<=": [{"var": "hour"}, {"var": "parameters.max_hour"}]}
                ]
            }
            
        elif name == "High_30D_Average_Spend":
            parameters["avg_30d_threshold"] = 5000.0
            logic = {">": [{"var": "p30d_avg_amount"}, {"var": "parameters.avg_30d_threshold"}]}
            
        elif name == "High_7D_Total_Spend":
            parameters["sum_7d_threshold"] = 15000.0
            logic = {">": [{"var": "p7d_sum_amount"}, {"var": "parameters.sum_7d_threshold"}]}
            
        elif name == "Dormant_High_Value_Transaction":
            parameters["min_txn_amount"] = 1000.0
            logic = {
                "and": [
                    {"==": [{"var": "p30d_txn_count"}, 0]},
                    {">=": [{"var": "amount"}, {"var": "parameters.min_txn_amount"}]}
                ]
            }

        new_rule = Rule(
            id=str(uuid.uuid4()),
            rule_name=name,
            description=desc,
            logic=logic,
            score_impact=score,
            parameters=parameters,
            is_active=True
        )
        db.add(new_rule)
        print(f"Migrated Rule: {name}")

    db.commit()
    db.close()
    print("Migration complete!")

if __name__ == "__main__":
    migrate_rules()
