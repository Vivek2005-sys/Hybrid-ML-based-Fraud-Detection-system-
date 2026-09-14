import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os

# Page Configuration handled in main.py

# Custom CSS targeting Streamlit's native container borders to look like Drona Pay
st.markdown("""
<style>
    /* Dark Theme Setup */
    .stApp {
        background-color: #1a1a24;
        color: #E2E8F0;
    }
    
    /* Native Container Card Styling */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #21212d !important;
        border: 1px solid #36364a !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }
    
    /* Headers & Subtitles */
    h1, h2, h3, h4 {
        color: #F0F6FC !important;
    }
    
    /* Hide Default Streamlit Menu / Footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# Page Header
st.title("Live Transactions")

# Filter Bar (like Drona Pay UI)
col_f1, col_f2, col_f3, col_f4 = st.columns([2, 2, 2, 1])
with col_f1:
    txn_type_filter = st.selectbox("Type", ["All", "UPI", "Credit Card", "Debit Card", "Wire Transfer"])
with col_f2:
    class_filter = st.selectbox("Class (Action)", ["All", "ALLOW", "REVIEW", "BLOCK"])
with col_f3:
    min_score_filter = st.number_input("Score (>=)", value=0.0, step=0.1, min_value=0.0, max_value=1.0)
with col_f4:
    st.write("")
    st.write("")
    st.button("🔍")


@st.cache_resource
def get_engine():
    return create_engine(os.getenv("DATABASE_URL", "postgresql://fraud_user:securepassword@localhost:5433/fraud_db"))

@st.fragment(run_every="3s")
def render_live_dashboard():
    engine = get_engine()
    query = """
        SELECT 
            transaction_date,
            customer_id,
            amount,
            txn_type,
            merchant,
            merchant_category,
            is_active_vpn,
            is_international,
            final_score as total_risk_score,
            results
        FROM transaction_scores
        ORDER BY transaction_date DESC
        LIMIT 50;
    """
    df = pd.read_sql(query, engine)
    
    if not df.empty:
        # Extract fields from the 'results' JSON column
        df['max_rule_score'] = df['results'].apply(lambda x: x.get('max_rule_score', 0.0) if isinstance(x, dict) else 0.0)
        df['ml_fraud_score'] = df['results'].apply(lambda x: x.get('ml_fraud_score', 0.0) if isinstance(x, dict) else 0.0)
        df['final_action'] = df['results'].apply(lambda x: x.get('final_action', 'UNKNOWN') if isinstance(x, dict) else 'UNKNOWN')
        df['triggered_rules'] = df['results'].apply(lambda x: x.get('triggered_rules', []) if isinstance(x, dict) else [])
        df['ml_narrative'] = df['results'].apply(lambda x: x.get('ml_narrative', 'No narrative provided.') if isinstance(x, dict) else '')
    else:
        # Create empty dataframe with correct columns if db is empty
        df = pd.DataFrame(columns=[
            "transaction_date", "customer_id", "amount", "txn_type", 
            "merchant_category", "max_rule_score", "ml_fraud_score", 
            "total_risk_score", "final_action", "is_active_vpn", 
            "is_international", "triggered_rules", "ml_narrative"
        ])

    df_scores = df

    # Apply Filters
    if txn_type_filter != "All":
        df_scores = df_scores[df_scores['txn_type'] == txn_type_filter]
    if class_filter != "All":
        df_scores = df_scores[df_scores['final_action'] == class_filter]
    if min_score_filter > 0:
        df_scores = df_scores[df_scores['total_risk_score'] >= min_score_filter]

    # Main Split Dashboard View
    col_left, col_right = st.columns([1.85, 1.15])

    # LEFT CONTAINER: Live Transactions Log Table
    with col_left:
        with st.container(height=650, border=True):
            st.markdown(f"#### 📋 Live Transactions (Recent 50) 🟢 Live")
            
            selected_event = st.dataframe(
                df_scores[[
                    "customer_id", "merchant_category", "transaction_date", "txn_type", "amount", "total_risk_score", "final_action"
                ]],
                use_container_width=True,
                hide_index=True,
                height=530,  # Fills the 650px container nicely
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "customer_id": "Unique ID",
                    "merchant_category": "Class",
                    "transaction_date": "Time",
                    "txn_type": "Txn Type",
                    "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                    "total_risk_score": "Score",
                    "final_action": "Action"
                }
            )

    # RIGHT CONTAINER: Decision Details Inspector
    with col_right:
        with st.container(height=650, border=True):
            st.markdown("#### 🔍 Decision Details")
            
            selected_rows = selected_event.get("selection", {}).get("rows", [])
            
            if selected_rows:
                row_idx = selected_rows[0]
                txn_data = df_scores.iloc[row_idx]
                
                st.markdown(f"### Customer ID: `{txn_data['customer_id']}`")
                st.caption(f"Date: {txn_data['transaction_date']} | Transaction Type: {txn_data['txn_type']} ({txn_data['merchant_category']})")
                st.divider()
                
                # Risk Metrics
                kpi1, kpi2 = st.columns(2)
                with kpi1:
                    st.metric(label="Unified Risk Score", value=f"{txn_data['total_risk_score']:.2f}")
                with kpi2:
                    action = txn_data['final_action']
                    if action == "BLOCK":
                        st.error("🚫 BLOCK")
                    elif action == "REVIEW":
                        st.warning("⚠️ REVIEW")
                    else:
                        st.success("✅ ALLOW")
                
                st.markdown(f"**Max Rule Score:** `{txn_data['max_rule_score']}` | **ML Fraud Score:** `{txn_data['ml_fraud_score']:.4f}`")
                st.write(f"**VPN Active:** {'Yes' if txn_data['is_active_vpn'] else 'No'} | **International:** {'Yes' if txn_data['is_international'] else 'No'}")
                
                st.divider()
                
                st.markdown("##### ML Narrative (Explainability)")
                st.info(f"🤖 {txn_data.get('ml_narrative', 'No ML narrative generated.')}")
                
                st.divider()
                st.markdown("##### Triggered Rules & Anomaly Audit Log")
                
                rules = txn_data['triggered_rules']
                if isinstance(rules, list) and len(rules) > 0:
                    for r in rules:
                        st.error(f"⚠️ **{r.get('rule_name', 'Rule')}**: +{r.get('score_impact', 0)} pts")
                        st.caption(r.get('description', 'Policy threshold exceeded'))
                elif txn_data['ml_fraud_score'] >= 0.70:
                    st.error(f"⚠️ **ML Model Anomaly Detected**: Score {txn_data['ml_fraud_score']:.4f}")
                    st.caption("Behavioral pattern spike detected by XGBoost model bypassing static rules.")
                else:
                    st.success("No high-severity policy rules triggered.")
                    
                st.divider()
                
            else:
                st.info("👈 Select any row from the Live Transactions table to view decision details.")

# Execute the fragment
render_live_dashboard()
