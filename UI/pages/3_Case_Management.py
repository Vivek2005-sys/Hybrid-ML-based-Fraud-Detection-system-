import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os
import json
import base64

st.set_page_config(page_title="Case Management", page_icon="🚨", layout="wide")

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
    .main-header {
        font-size: 24px;
        font-weight: 600;
        margin-bottom: 20px;
        color: #fff;
    }
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

st.markdown("<div class='main-header'>Case Management</div>", unsafe_allow_html=True)

@st.cache_resource
def get_engine():
    return create_engine(os.getenv("DATABASE_URL", "postgresql://fraud_user:securepassword@db:5432/fraud_db"))

engine = get_engine()

def get_cases():
    with engine.connect() as conn:
        try:
            query = "SELECT * FROM transaction_scores WHERE results->>'final_action' IN ('REVIEW', 'BLOCK') OR results->>'risk_level' IN ('MEDIUM', 'HIGH') ORDER BY transaction_date DESC"
            df = pd.read_sql(query, conn)
            if not df.empty:
                df['total_risk_score'] = df['final_score']
                df['triggered_rules'] = df['results'].apply(lambda x: x.get('triggered_rules', []) if isinstance(x, dict) else [])
            return df
        except Exception as e:
            return pd.DataFrame()

def update_status(case_id_or_list, new_status):
    with engine.begin() as conn:
        if isinstance(case_id_or_list, list):
            conn.execute(text("UPDATE transaction_scores SET status = :s WHERE id = ANY(:ids)"), {"s": new_status, "ids": case_id_or_list})
        else:
            conn.execute(text("UPDATE transaction_scores SET status = :s WHERE id = :id"), {"s": new_status, "id": case_id_or_list})

df_cases = get_cases()

col_queue, col_manage, col_summary = st.columns([1.7, 1.3, 1.5])

with col_queue:
    with st.container(height=680, border=True):
        st.markdown("#### Alert Queue")
        
        status_filter = st.selectbox("Status Filter", ["All", "OPEN", "CLAIMED", "CLOSED"])
        
        if not df_cases.empty:
            df_cases['status'] = df_cases['status'].fillna("OPEN")
            
            if status_filter != "All":
                df_filtered = df_cases[df_cases['status'] == status_filter].reset_index(drop=True)
            else:
                df_filtered = df_cases.reset_index(drop=True)
                
            df_filtered_display = pd.DataFrame()
            df_filtered_display['short_id'] = df_filtered['id'].apply(lambda x: str(x)[:8])
            df_filtered_display['amount'] = df_filtered['amount']
            df_filtered_display['total_risk_score'] = df_filtered['total_risk_score']
            
            selected_event = st.dataframe(
                df_filtered_display,
                use_container_width=True,
                hide_index=True,
                height=520,
                on_select="rerun",
                selection_mode="multi-row",
                column_config={
                    "short_id": "Txn ID",
                    "amount": st.column_config.NumberColumn("Amount", format="$%.0f"),
                    "total_risk_score": "Risk"
                }
            )
        
            selected_rows = selected_event.get("selection", {}).get("rows", [])
        else:
            st.info("No REVIEW cases found in database.")
            selected_rows = []
            df_filtered = pd.DataFrame()

# ==========================================
# COLUMN 2: MANAGE CASE
# ==========================================
with col_manage:
    with st.container(height=680, border=True):
        st.markdown("#### Action Center")
        
        if len(selected_rows) == 1 and not df_cases.empty:
            row_idx = selected_rows[0]
            case_data = df_filtered.iloc[row_idx]
            case_id = case_data['id']
            status = case_data['status']
            
            st.caption("Workflow:")
            if status == "OPEN":
                st.markdown("🔍 **New** ➔ ⏳ Review ➔ ⚖️ Done")
            elif status == "CLAIMED":
                st.markdown("✅ New ➔ 🔍 **Review** ➔ ⚖️ Done")
            else:
                st.markdown("✅ New ➔ ✅ Review ➔ 🔍 **Done**")
                
            st.divider()
            
            if status == "OPEN":
                st.markdown("<br><br><br>", unsafe_allow_html=True)
                st.markdown("<h5 style='text-align: center; color: #888;'>Assign this alert to yourself to take action</h5>", unsafe_allow_html=True)
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button("INVESTIGATE", use_container_width=True):
                        update_status(case_id, "CLAIMED")
                        st.rerun()
                        
            elif status == "CLAIMED":
                st.markdown("##### Actions Required")
                st.write("You own this case. Investigate the summary on the right and take action.")
                
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✅ Approve (Safe)", use_container_width=True):
                    update_status(case_id, "CLOSED")
                    st.success("Alert resolved. Transaction allowed.")
                    st.rerun()
                    
                if st.button("🚫 Block (Fraud)", use_container_width=True):
                    update_status(case_id, "CLOSED")
                    st.error("Alert resolved. User blocked.")
                    st.rerun()
                    
                if st.button("📧 Send Email", use_container_width=True):
                    try:
                        from email_service import send_verification_email
                        obs = case_data.get('observations', {})
                        if isinstance(obs, str):
                            obs = json.loads(obs)
                        customer_info = obs.get('customer', {})
                        cust_email = customer_info.get('email', 'unknown@example.com')
                        cust_name = customer_info.get('first_name', 'Customer')
                        success, msg = send_verification_email(
                            customer_email=cust_email,
                            customer_name=cust_name,
                            transaction_id=case_id,
                            amount=case_data['amount'],
                            txn_type=case_data['txn_type']
                        )
                        if success:
                            st.success(f"Email dispatched to {cust_email}!")
                        else:
                            st.error(msg)
                    except Exception as e:
                        st.warning(str(e))
                        
            elif status == "CLOSED":
                st.success(f"Case is CLOSED.")

        elif len(selected_rows) > 1 and not df_cases.empty:
            st.markdown("##### Bulk Actions")
            st.write(f"You have selected **{len(selected_rows)}** cases.")
            st.divider()
            
            all_closed = all(df_filtered.iloc[r]['status'] == 'CLOSED' for r in selected_rows)
            
            if all_closed:
                st.success("All selected cases are already CLOSED.")
            else:
                if st.button("INVESTIGATE ALL", use_container_width=True):
                    cases_to_update = [df_filtered.iloc[r_idx]['id'] for r_idx in selected_rows]
                    update_status(cases_to_update, "CLAIMED")
                    st.rerun()
                    
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✅ Approve All (Safe)", use_container_width=True):
                    cases_to_update = [df_filtered.iloc[r_idx]['id'] for r_idx in selected_rows]
                    update_status(cases_to_update, "CLOSED")
                    st.rerun()
                    
                if st.button("🚫 Block All (Fraud)", use_container_width=True):
                    cases_to_update = [df_filtered.iloc[r_idx]['id'] for r_idx in selected_rows]
                    update_status(cases_to_update, "CLOSED")
                    st.rerun()
                
        else:
            st.markdown("<br><br><br>", unsafe_allow_html=True)
            st.markdown("<h5 style='text-align: center; color: #888;'>Select a task from the queue</h5>", unsafe_allow_html=True)

# ==========================================
# COLUMN 3: CASE SUMMARY
# ==========================================
with col_summary:
    with st.container(height=680, border=True):
        st.markdown("#### Risk Profile")
        
        if len(selected_rows) == 1 and not df_cases.empty:
            case_data = df_filtered.iloc[selected_rows[0]]
            case_id = case_data['id']
            
            tab1, tab2, tab3 = st.tabs(["Risk Breakdown", "Txn Details", "Verification Documents"])
            
            with tab1:
                st.markdown(f"**Customer Profile:** `{case_data['customer_id']}`")
                risk = case_data['total_risk_score']
                st.markdown(f"<h3 style='text-align: center;'>🔥 {risk:.2f} Risk Score</h3>", unsafe_allow_html=True)
                
                st.divider()
                st.markdown("##### Triggered Rules")
                rules = case_data['triggered_rules']
                if rules:
                    for r in rules:
                        st.warning(f"**{r.get('rule_name', 'Rule')}**: +{r.get('score_impact', 0)}")
                else:
                    st.info("No explicit rules found in JSON.")
                    
            with tab2:
                st.write(f"**Transaction ID:** `{case_id}`")
                st.write(f"**Date:** {case_data['transaction_date']}")
                st.write(f"**Transaction Type:** {case_data['txn_type']}")
                st.write(f"**Amount:** ${case_data['amount']:,.2f}")
                
            with tab3:
                results = case_data.get('results', {})
                if isinstance(results, str):
                    try:
                        results = json.loads(results)
                    except:
                        results = {}
                        
                docs = results.get("attached_documents", [])
                
                if not docs:
                    st.info("Awaiting customer response...")
                    st.write("No verification documents have been received yet for this transaction.")
                else:
                    st.success(f"Customer has submitted {len(docs)} document(s)!")
                    for idx, doc in enumerate(docs):
                        st.markdown(f"**File:** `{doc['filename']}`")
                        try:
                            img_bytes = base64.b64decode(doc['content'])
                            if "image" in doc.get("content_type", "") or doc['filename'].lower().endswith(('.png', '.jpg', '.jpeg')):
                                st.image(img_bytes, caption=doc['filename'], use_column_width=True)
                            
                            st.download_button(
                                label=f"Download {doc['filename']}",
                                data=img_bytes,
                                file_name=doc['filename'],
                                mime=doc.get("content_type", "application/octet-stream"),
                                key=f"dl_{case_id}_{idx}"
                            )
                        except Exception as e:
                            st.error(f"Could not load preview for {doc['filename']}")
                        st.divider()
                        
        elif len(selected_rows) > 1 and not df_cases.empty:
            st.info(f"Bulk actions mode active ({len(selected_rows)} selected).")
            st.write("Individual risk profiles are hidden during bulk selection. Please use the Action Center to apply actions to all selected cases simultaneously.")
        else:
            st.write("-")
