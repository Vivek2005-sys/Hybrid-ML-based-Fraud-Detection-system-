import streamlit as st

# Configure the page settings globally for the whole app
st.set_page_config(
    page_title="Fraud Detection Portal",
    page_icon="🛡️",
    layout="wide"
)

# Define the pages (both files live inside the pages/ folder)
dashboard_page = st.Page(
    "pages/1_Live_Dashboard.py", 
    title="Live Dashboard", 
    icon="📋", 
    default=True  # This makes it the first screen you see!
)

history_page = st.Page(
    "pages/2_Customer_History.py", 
    title="Customer History", 
    icon="🔍"
)

case_page = st.Page(
    "pages/3_Case_Management.py",
    title="Case Management",
    icon="🔍"
)

rules_page = st.Page(
    "pages/4_Rule_Configurator.py",
    title="Rule Configurator",
    icon="⚙️"
)

artifacts_page = st.Page(
    "pages/5_Artifact_Builder.py",
    title="Artifact Builder",
    icon="🧩"
)

models_page = st.Page(
    "pages/6_Model_Management.py",
    title="Model Management",
    icon="🧠"
)

# Create the navigation menu
pg = st.navigation([dashboard_page, history_page, case_page, rules_page, artifacts_page, models_page])

# Run the selected page
pg.run()
