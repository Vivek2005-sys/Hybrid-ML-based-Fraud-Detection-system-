import streamlit as st
import pandas as pd
import json
import os
from sqlalchemy import create_engine, text

# Page Configuration
st.set_page_config(page_title="Rule Configurator", page_icon="⚙️", layout="wide")

# Custom CSS matching Drona Pay dark theme and compact layout
st.markdown("""
<style>
    .stApp {
        background-color: #12141c;
        color: #F0F6FC;
    }
    .st-emotion-cache-1wmy9hl {
        background-color: #1e212f !important;
        border: 1px solid #30363d !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }
    div[data-testid="stMetricValue"] {
        color: #e83e8c;
    }
    .main-header {
        font-size: 24px;
        font-weight: 600;
        margin-bottom: 20px;
        color: #fff;
    }
    /* Buttons */
    div[data-testid="stButton"] button {
        background-color: #4f46e5 !important;
        color: white !important;
        border: none !important;
        font-weight: bold !important;
    }
    div[data-testid="stButton"] button:hover {
        background-color: #4338ca !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-header'>Rule Configurator</div>", unsafe_allow_html=True)

@st.cache_resource
def get_engine():
    return create_engine(os.getenv("DATABASE_URL", "postgresql://fraud_user:securepassword@db:5432/fraud_db"))

engine = get_engine()

# Fetch rules
def get_rules():
    with engine.connect() as conn:
        df = pd.read_sql("SELECT * FROM rules ORDER BY rule_name", conn)
    return df

df_rules = get_rules()

if df_rules.empty:
    st.info("No rules found in database. Please run the migration script.")
    st.stop()

# Layout
col_left, col_right = st.columns([1, 2])

# ==========================================
# LEFT COLUMN: Select Rules
# ==========================================
with col_left:
    with st.container(height=700, border=True):
        st.markdown("#### Select Rules")
        
        search_term = st.text_input("Search For Rule", "")
        
        if st.button("➕ Create New Rule", use_container_width=True):
            st.session_state.selected_rule_id = "NEW_RULE"
            st.rerun()
            
        st.divider()
        
        if search_term:
            df_display = df_rules[df_rules['rule_name'].str.contains(search_term, case=False)]
        else:
            df_display = df_rules
            
        # Draw the rule list
        selected_rule_id = st.session_state.get('selected_rule_id', df_display.iloc[0]['id'] if not df_display.empty else None)
        
        for idx, row in df_display.iterrows():
            is_selected = (row['id'] == selected_rule_id)
            
            # Use buttons disguised as rows to act as a selector
            col_name, col_status = st.columns([4, 1])
            with col_name:
                if st.button(f"⚙️ {row['rule_name']}", key=f"sel_{row['id']}", use_container_width=True):
                    st.session_state.selected_rule_id = row['id']
                    st.rerun()
            with col_status:
                st.markdown(f"{'🟢' if row['is_active'] else '⚪'}")

# ==========================================
# RIGHT COLUMN: Manage Rules
# ==========================================
with col_right:
    with st.container(border=True):
        if not selected_rule_id:
            st.write("Select a rule to edit or create a new one.")
        elif selected_rule_id == "NEW_RULE":
            st.markdown("#### Create New Rule")
            st.caption("Draft a brand new JSONLogic rule from scratch.")
            st.divider()
            
            new_rule_name = st.text_input("Rule Name (Unique)", value="New_Rule_Name")
            new_desc = st.text_input("Description", value="What does this rule do?")
            
            col_active, col_score = st.columns(2)
            with col_active:
                new_active = st.toggle("Rule Active", value=True)
            with col_score:
                new_score = st.number_input("Fail Score (Impact)", value=50.0, step=5.0)
            
            st.markdown("### Advanced: JSON Logic")
            new_logic_str = st.text_area("JSON Logic", value='{"<": [{"var": "amount"}, {"var": "parameters.threshold"}]}', height=350)
            
            st.markdown("### Parameters (Thresholds)")
            st.info("Parameters are automatically extracted from your JSON Logic above (look for `parameters.your_var_name`).")
            
            import re
            # Live parse the JSON Logic for any string matching "parameters.XXXX"
            detected_params = list(set(re.findall(r'"parameters\.([a-zA-Z0-9_]+)"', new_logic_str)))
            
            parsed_params = {}
            if not detected_params:
                st.write("No dynamic thresholds detected in JSON.")
            else:
                for param in detected_params:
                    parsed_params[param] = st.number_input(f"{param}", value=0.0, step=1.0, key=f"new_param_{param}")
            
            if st.button(label="Save New Rule", type="primary"):
                try:
                    parsed_logic = json.loads(new_logic_str)
                    
                    import uuid
                    new_id = str(uuid.uuid4())
                    
                    # Save to database
                    with engine.begin() as conn:
                        query = text("""
                            INSERT INTO rules (id, rule_name, description, is_active, score_impact, parameters, logic)
                            VALUES (:id, :rule_name, :description, :is_active, :score_impact, :parameters, :logic)
                        """)
                        conn.execute(query, {
                            "id": new_id,
                            "rule_name": new_rule_name,
                            "description": new_desc,
                            "is_active": new_active,
                            "score_impact": new_score,
                            "parameters": json.dumps(parsed_params),
                            "logic": json.dumps(parsed_logic)
                        })
                        
                    st.success("New rule created successfully!")
                    st.session_state.selected_rule_id = new_id
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Invalid JSON syntax in the Logic block.")
                except Exception as e:
                    st.error(f"Failed to create rule: {e}")
        else:
            rule_data = df_rules[df_rules['id'] == selected_rule_id].iloc[0]
            
            st.markdown("#### Manage Rule")
            new_rule_name = st.text_input("Rule Name", value=rule_data['rule_name'])
            new_desc = st.text_input("Description", value=rule_data['description'])
            st.divider()
            
            col_active, col_score = st.columns(2)
            with col_active:
                new_active = st.toggle("Rule Active", value=rule_data['is_active'])
            with col_score:
                new_score = st.number_input("Fail Score (Impact)", value=float(rule_data['score_impact']), step=5.0)
            
            st.markdown("### Advanced: JSON Logic")
            new_logic_str = st.text_area("JSON Logic", value=json.dumps(rule_data['logic'], indent=2), height=350)
            
            st.markdown("### Parameters (Thresholds)")
            st.info("Parameters are automatically extracted from your JSON Logic above (look for `parameters.your_var_name`).")
            
            import re
            # Live parse the JSON Logic for any string matching "parameters.XXXX"
            detected_params = list(set(re.findall(r'"parameters\.([a-zA-Z0-9_]+)"', new_logic_str)))
            
            new_params = {}
            if not detected_params:
                st.write("No dynamic thresholds detected in JSON.")
            else:
                existing_params = rule_data['parameters'] if isinstance(rule_data['parameters'], dict) else {}
                for param in detected_params:
                    # Use existing value from DB if it exists, otherwise default to 0.0
                    default_val = float(existing_params.get(param, 0.0))
                    new_params[param] = st.number_input(f"{param}", value=default_val, step=1.0, key=f"edit_param_{param}")
            
            if st.button(label="Save Rule Configuration", type="primary"):
                try:
                    parsed_logic = json.loads(new_logic_str)
                    
                    # Save to database
                    with engine.begin() as conn:
                        query = text("""
                            UPDATE rules 
                            SET rule_name = :rule_name,
                                description = :description,
                                is_active = :is_active,
                                score_impact = :score_impact,
                                parameters = :parameters,
                                logic = :logic
                            WHERE id = :id
                        """)
                        conn.execute(query, {
                            "rule_name": new_rule_name,
                            "description": new_desc,
                            "is_active": new_active,
                            "score_impact": new_score,
                            "parameters": json.dumps(new_params),
                            "logic": json.dumps(parsed_logic),
                            "id": selected_rule_id
                        })
                        
                    st.success("Rule updated successfully in database! Changes are instantly active.")
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Invalid JSON syntax in the logic block.")
                except Exception as e:
                    st.error(f"Failed to update rule: {e}")
