"""
Authentication utilities for the SMART Parking Dashboard.
Handles login validation, session state, and role-based page access.
"""
from pathlib import Path
from typing import Optional

import streamlit as st
import yaml

_ROOT = Path(__file__).resolve().parents[1]
_USERS_FILE = _ROOT / "config" / "users.yaml"

# Pages allowed per role
ROLE_PAGES = {
    "Super Admin":      ["overview", "revenue", "forecast", "anomalies", "catalog", "sql_editor"],
    "Location Manager": ["occupancy", "staff", "revenue_gauge", "violations"],
    "Data Analyst":     ["eda_explorer", "ml_metrics", "segmentation", "pricing_sim", "sql_editor"],
    "Customer":         ["find_parking", "my_history", "season_pass", "my_violations", "loyalty"],
}


def load_users() -> list:
    with open(_USERS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)["users"]


def authenticate(username: str, password: str) -> Optional[dict]:
    """Return user dict if credentials match, else None."""
    for user in load_users():
        if user["username"] == username and user["password"] == password:
            return user
    return None


def login_page():
    """Render the login form. Sets st.session_state on success."""
    st.markdown("""
        <style>
        .login-container { max-width: 420px; margin: auto; padding-top: 80px; }
        .logo-text { color: #2E8B57; font-size: 2rem; font-weight: 800; }
        .sub-text  { color: #666; font-size: 0.95rem; margin-bottom: 1.5rem; }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<p class="logo-text">🅿 SMART Parking</p>', unsafe_allow_html=True)
        st.markdown('<p class="sub-text">Pakistan Smart Parking Management System</p>',
                    unsafe_allow_html=True)
        st.markdown("---")

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="e.g. superadmin")
            password = st.text_input("Password", type="password")
            submit   = st.form_submit_button("Sign In", use_container_width=True)

            if submit:
                user = authenticate(username, password)
                if user:
                    st.session_state["logged_in"]   = True
                    st.session_state["user"]        = user
                    st.session_state["role"]        = user["role"]
                    st.session_state["username"]    = user["username"]
                    st.session_state["query_history"] = []
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        st.markdown("---")
        st.caption("Demo credentials:  superadmin / admin123  |  analyst / analyst123  |  customer / customer123")
        st.markdown("</div>", unsafe_allow_html=True)


def require_login():
    """Call at the top of every page. Redirects to login if not authenticated."""
    if not st.session_state.get("logged_in"):
        login_page()
        st.stop()


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


def sidebar_user_info():
    """Render the shared sidebar with user info and logout button."""
    role  = st.session_state.get("role", "Unknown")
    uname = st.session_state.get("username", "")
    name  = st.session_state.get("user", {}).get("name", uname)

    role_colors = {
        "Super Admin":      "#FF6B35",
        "Location Manager": "#2196F3",
        "Data Analyst":     "#9C27B0",
        "Customer":         "#2E8B57",
    }
    color = role_colors.get(role, "#666")

    with st.sidebar:
        st.markdown(f"""
            <div style='text-align:center; padding: 10px 0 5px;'>
                <span style='font-size:2rem'>🅿</span><br/>
                <b style='color:#2E8B57; font-size:1.1rem'>SMART Parking</b><br/>
                <span style='font-size:0.75rem; color:#888'>Pakistan</span>
            </div>
            <hr style='margin:8px 0'>
            <div style='padding:6px 0'>
                <b>{name}</b><br/>
                <span style='background:{color}; color:white; padding:2px 8px;
                      border-radius:10px; font-size:0.75rem'>{role}</span>
            </div>
            <hr style='margin:8px 0'>
        """, unsafe_allow_html=True)

        if st.button("🚪 Logout", use_container_width=True):
            logout()
