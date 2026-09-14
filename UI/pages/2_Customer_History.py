import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import os
import plotly.express as px

# Page Configuration handled in main.py

# Custom CSS matching the main dashboard
st.markdown("""
<style>
    .stApp {
        background-color: #1a1a24;
        color: #E2E8F0;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #21212d !important;
        border: 1px solid #36364a !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }
    h1, h2, h3, h4 {
        color: #F0F6FC !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

st.title("Customer Historical Transactions")

# Search Bar
search_col, _ = st.columns([1, 2])
with search_col:
    customer_id_query = st.text_input("🔍 Search by Customer ID", placeholder="e.g. C001428")

@st.cache_resource
def get_engine():
    return create_engine(os.getenv("DATABASE_URL", "postgresql://fraud_user:securepassword@localhost:5433/fraud_db"))

if customer_id_query:
    engine = get_engine()
    
    # Fetch historical data
    query = f"""
        SELECT 
            transaction_date,
            customer_id,
            amount,
            txn_type,
            merchant,
            merchant_category,
            final_score as total_risk_score,
            results
        FROM transaction_scores
        WHERE customer_id = '{customer_id_query}'
        ORDER BY transaction_date ASC;
    """
    
    try:
        df = pd.read_sql(query, engine)
        
        if df.empty:
            st.warning(f"No transactions found for Customer ID: {customer_id_query}")
        else:
            # Parse JSON results
            df['final_action'] = df['results'].apply(lambda x: x.get('final_action', 'UNKNOWN') if isinstance(x, dict) else 'UNKNOWN')
            
            # KPI Metrics
            total_txns = len(df)
            total_alerts = len(df[df['final_action'].isin(['BLOCK', 'REVIEW'])])
            total_spend = df['amount'].sum()
            
            kpi1, kpi2, kpi3 = st.columns(3)
            with kpi1:
                with st.container(border=True):
                    st.metric("Total Transactions ↗", total_txns)
            with kpi2:
                with st.container(border=True):
                    st.metric("Total Alerts ⚠️", total_alerts)
            with kpi3:
                with st.container(border=True):
                    st.metric("Total Spend 📈", f"${total_spend:,.2f}")
            
            st.write("") # Spacer
            
            # Split View: Table and Chart
            col_left, col_right = st.columns([1.2, 1])
            
            with col_left:
                with st.container(height=500, border=True):
                    st.markdown(f"#### Historical Transactions ({customer_id_query})")
                    # Sort descending for the table view
                    df_display = df.sort_values(by='transaction_date', ascending=False)
                    st.dataframe(
                        df_display[[
                            "transaction_date", "txn_type", "amount", "total_risk_score", "final_action"
                        ]],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "transaction_date": "Date",
                            "txn_type": "Merchant",
                            "amount": st.column_config.NumberColumn("Amount", format="$%.2f"),
                            "total_risk_score": "Risk Score",
                            "final_action": "Status"
                        }
                    )
            
            with col_right:
                with st.container(height=500, border=True):
                    st.markdown("#### Customer Risk Score Over Time")
                    
                    # Line Chart for Risk Score
                    fig = px.line(
                        df, 
                        x="transaction_date", 
                        y="total_risk_score", 
                        markers=True,
                        template="plotly_dark",
                        color_discrete_sequence=["#8A2BE2"] # Purple accent
                    )
                    
                    # Highlight blocked/reviewed transactions on the chart
                    anomalies = df[df['final_action'].isin(['BLOCK', 'REVIEW'])]
                    if not anomalies.empty:
                        fig.add_scatter(
                            x=anomalies['transaction_date'],
                            y=anomalies['total_risk_score'],
                            mode='markers',
                            marker=dict(color='red', size=10, symbol='circle'),
                            name='Alerts'
                        )
                        
                    fig.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        xaxis_title="Date",
                        yaxis_title="Risk Score (0-1.0)",
                        margin=dict(l=0, r=0, t=30, b=0),
                        showlegend=False
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
    except Exception as e:
        st.error(f"Error loading historical data: {str(e)}")
else:
    st.info("👆 Enter a Customer ID in the search bar above to view their historical transactions.")
