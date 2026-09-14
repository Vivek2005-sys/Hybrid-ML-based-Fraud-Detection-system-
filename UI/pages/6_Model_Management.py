import streamlit as st
import os
import json
import subprocess
import requests

# Page Configuration
st.set_page_config(page_title="Model Management", page_icon="🧠", layout="wide")

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

st.markdown("<div class='main-header'>Model Management (Continuous Training)</div>", unsafe_allow_html=True)
st.markdown("Retrain your XGBoost Champion Model dynamically on all your latest historical data and Custom Artifacts.")

c1, c2 = st.columns([1, 1])

with c1:
    with st.container(border=True, height=500):
        st.markdown("### 🏆 Active Champion Model")
        
        try:
            resp = requests.get("http://api:8000/model_metadata", timeout=5)
            if resp.status_code == 200 and resp.json().get("data"):
                meta = resp.json()["data"]
                st.success(f"**XGBoost v2 (Dynamic)** - Last trained: {meta.get('trained_at', 'Unknown')}")
                
                st.metric("Total Training Records", meta.get("total_records", 0))
                st.metric("Fraud Examples Found", meta.get("fraud_records", 0))
                
                st.markdown("#### Input Schema (Feature Vector)")
                st.write(f"Expects **{len(meta.get('feature_cols', []))}** features.")
                st.json(meta.get("feature_cols", []))
            else:
                st.info("Using baseline default features. No dynamic model metadata found.")
        except Exception as e:
            st.error(f"Could not connect to API to fetch metadata: {e}")

with c2:
    with st.container(border=True, height=500):
        st.markdown("### 🚀 Automated Retraining Pipeline")
        st.write("Triggering this pipeline will run `app/train_xgboost.py`. It will dynamically backfill all your newly created UI Artifacts into historical transaction data, train a new XGBoost model, and instantly hot-swap it in the API.")
        
        st.divider()
        
        if st.button("Trigger Retraining Pipeline", use_container_width=True):
            with st.spinner("Backfilling historical data and training XGBoost..."):
                try:
                    # Call the API container to train and hot-swap itself
                    resp = requests.post("http://api:8000/retrain_model", timeout=300)
                    if resp.status_code == 200:
                        st.balloons()
                        st.success("Training successful and Model Hot-Swapped in production!")
                        st.json(resp.json().get("metadata", {}))
                    else:
                        st.error(f"Training failed: {resp.text}")
                except Exception as e:
                    st.error(f"Execution error: {e}")
            # Do not rerun automatically so the user can see the balloons and metadata
            if st.button("Refresh Model Details"):
                st.rerun()
