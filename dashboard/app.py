"""
SMART Parking Solutions — Main Streamlit App
============================================
Entry point with role-based navigation.

Run:  streamlit run dashboard/app.py
"""
import streamlit as st

# ── Page config must be FIRST ─────────────────────────────────────────────────
st.set_page_config(
    page_title="SMART Parking Solutions",
    page_icon="🅿",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.auth import require_login, sidebar_user_info, login_page

# ── Apply global CSS theme ─────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Primary green accent */
    :root { --primary: #2E8B57; --accent: #FF6B35; }

    /* Hide Streamlit's auto-discovered page navigation */
    [data-testid="stSidebarNav"] { display: none !important; }
    [data-testid="stSidebarNavItems"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    section[data-testid="stSidebar"] > div:first-child > div:first-child { padding-top: 0 !important; }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a5c38 0%, #2E8B57 100%);
    }
    [data-testid="stSidebar"] * { color: white !important; }
    [data-testid="stSidebar"] .stButton button {
        background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.3);
        color: white !important;
        border-radius: 8px;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: rgba(255,255,255,0.25);
    }
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 4px solid #2E8B57;
    }
    h1, h2 { color: #2E8B57; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px 6px 0 0;
        padding: 6px 16px;
    }
</style>
""", unsafe_allow_html=True)


# ── Login gate ────────────────────────────────────────────────────────────────
if not st.session_state.get("logged_in"):
    login_page()
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
sidebar_user_info()
role = st.session_state.get("role", "Customer")

# ── Role-based navigation ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Navigation")

    if role == "Super Admin":
        page = st.radio("", [
            "📊 Overview",
            "💰 Revenue Analytics",
            "🔮 Forecast",
            "⚠️ Anomaly Alerts",
            "🗂️ Data Catalog",
            "🔍 SQL Editor",
        ], label_visibility="collapsed")

    elif role == "Location Manager":
        page = st.radio("", [
            "🅿 Slot Occupancy",
            "👥 Staff Shifts",
            "💰 Today's Revenue",
            "🚨 Violations Log",
        ], label_visibility="collapsed")

    elif role == "Data Analyst":
        page = st.radio("", [
            "📈 EDA Explorer",
            "🤖 ML Metrics",
            "👥 Segmentation",
            "💡 Pricing Simulator",
            "🔍 SQL Editor",
        ], label_visibility="collapsed")

    else:  # Customer
        page = st.radio("", [
            "🔎 Find Parking",
            "📋 My History",
            "🎫 Season Pass",
            "🚨 My Violations",
            "⭐ Loyalty Score",
        ], label_visibility="collapsed")

    st.markdown("---")
    st.caption("SMART Parking Solutions v1.0\n🇵🇰 Pakistan")

# ── Page routing ──────────────────────────────────────────────────────────────
from dashboard._pages import (
    super_admin, location_manager, data_analyst, customer, sql_editor
)

if role == "Super Admin":
    if   "Overview"          in page: super_admin.page_overview()
    elif "Revenue Analytics" in page: super_admin.page_revenue()
    elif "Forecast"          in page: super_admin.page_forecast()
    elif "Anomaly"           in page: super_admin.page_anomalies()
    elif "Catalog"           in page: super_admin.page_catalog()
    elif "SQL Editor"        in page: sql_editor.page_sql_editor()

elif role == "Location Manager":
    if   "Occupancy"  in page: location_manager.page_occupancy()
    elif "Staff"      in page: location_manager.page_staff()
    elif "Revenue"    in page: location_manager.page_revenue_gauge()
    elif "Violations" in page: location_manager.page_violations()

elif role == "Data Analyst":
    if   "EDA"       in page: data_analyst.page_eda()
    elif "ML"        in page: data_analyst.page_ml_metrics()
    elif "Segment"   in page: data_analyst.page_segmentation()
    elif "Pricing"   in page: data_analyst.page_pricing_sim()
    elif "SQL"       in page: sql_editor.page_sql_editor()

else:  # Customer
    if   "Find"     in page: customer.page_find_parking()
    elif "History"  in page: customer.page_history()
    elif "Season"   in page: customer.page_season_pass()
    elif "Violation" in page: customer.page_violations()
    elif "Loyalty"  in page: customer.page_loyalty()
