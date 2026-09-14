import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import os
import uuid

# Page Configuration
st.set_page_config(page_title="Artifact Builder", page_icon="🧩", layout="wide")

# Custom CSS matching Drona Pay dark theme
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

st.markdown("<div class='main-header'>Dynamic Artifact Builder</div>", unsafe_allow_html=True)
st.markdown("Create custom time-window aggregations on the fly. These artifacts are computed instantly and injected into JSONLogic as variables (e.g., `{\"var\": \"your_artifact_name\"}`).")

@st.cache_resource
def get_engine():
    return create_engine(os.getenv("DATABASE_URL", "postgresql://fraud_user:securepassword@db:5432/fraud_db"))

engine = get_engine()

# Fetch Artifacts
def get_artifacts():
    with engine.connect() as conn:
        try:
            df = pd.read_sql("SELECT * FROM artifacts ORDER BY created_at DESC", conn)
            return df
        except Exception:
            return pd.DataFrame()

df_arts = get_artifacts()

col_left, col_right = st.columns([1, 2])

with col_left:
    with st.container(height=600, border=True):
        st.markdown("#### Existing Artifacts")
        if df_arts.empty:
            st.info("No custom artifacts found.")
        else:
            for idx, row in df_arts.iterrows():
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{row['name']}**")
                    st.caption(f"{row['aggregation']} of amount over last {row['lookback_hours']} hours.")
                with c2:
                    with st.popover("Delete"):
                        st.write("Are you sure?")
                        if st.button("Confirm", key=f"conf_{row['id']}", type="primary"):
                            try:
                                with engine.begin() as conn:
                                    conn.execute(text("DELETE FROM artifacts WHERE id = :id"), {"id": row['id']})
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting: {e}")
                st.divider()

with col_right:
    with st.container(height=600, border=True):
        st.markdown("#### Create New Artifact")
        
        with st.form("new_artifact_form"):
            art_name = st.text_input("Artifact Name", placeholder="e.g., txn_count_1hr", help="Use lowercase with underscores. This will be the exact variable name in JSONLogic.")
            art_desc = st.text_input("Description", placeholder="e.g., Total transaction count in the last 1 hour.")
            
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                agg = st.selectbox("Aggregation Type", ["COUNT", "SUM", "AVG", "MAX"])
            with c2:
                time_unit = st.selectbox("Time Unit", ["Hours", "Days"])
            with c3:
                lookback_val = st.number_input("Lookback Value", min_value=0.1, max_value=2160.0, value=1.0, step=1.0)
                
            st.info("Note: All aggregations currently compute across the transaction `amount` column.")
                
            submitted = st.form_submit_button("Create Artifact")
            if submitted:
                final_lookback_hours = lookback_val if time_unit == "Hours" else lookback_val * 24.0
                
                if not art_name:
                    st.error("Artifact name is required.")
                else:
                    try:
                        new_id = str(uuid.uuid4())
                        with engine.begin() as conn:
                            query = text("""
                                INSERT INTO artifacts (id, name, description, lookback_hours, aggregation)
                                VALUES (:id, :name, :description, :lookback_hours, :aggregation)
                            """)
                            conn.execute(query, {
                                "id": new_id,
                                "name": art_name.replace(" ", "_").lower(),
                                "description": art_desc,
                                "lookback_hours": final_lookback_hours,
                                "aggregation": agg
                            })
                        st.success(f"Artifact '{art_name}' successfully created and active in the engine!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to create artifact. It may already exist. Error: {e}")
