"""
Customer Self-Service Dashboard Pages
========================================
  - Find Parking   : Search by city / neighborhood
  - My History     : Past transactions
  - Season Pass    : Status + renewal
  - My Violations  : Linked violations
  - Loyalty Score  : RFM-derived points
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.data_loader import load_silver_fact, load_gold

_ROOT = Path(__file__).resolve().parents[2]


def _get_customer_id() -> str:
    return st.session_state.get("user", {}).get("customer_id", "")


def _customer_fact(fact: pd.DataFrame, cust_id: str) -> pd.DataFrame:
    """Return only rows belonging to the logged-in customer."""
    return fact[fact["customer_id"] == cust_id]


# ── Page: Find Parking ────────────────────────────────────────────────────────

def page_find_parking():
    st.title("🔎 Find Parking")

    locs = pd.read_parquet(_ROOT / "data" / "silver" / "silver_locations.parquet")
    fact = load_silver_fact()

    col1, col2 = st.columns(2)
    with col1:
        city = st.selectbox("City", sorted(locs["city"].unique()), key="fp_city")
    with col2:
        neighborhoods = locs[locs["city"] == city]["neighborhood"].unique()
        hood = st.selectbox("Neighborhood (optional)", ["All"] + sorted(neighborhoods),
                            key="fp_hood")

    df = locs[locs["city"] == city].copy()
    if hood != "All":
        df = df[df["neighborhood"] == hood]

    # Estimate occupied slots: avg peak-hour transactions over last 30 days
    fact_dt = fact.copy()
    fact_dt["entry_date"] = pd.to_datetime(fact_dt["entry_date"])
    latest_date  = fact_dt["entry_date"].max()
    window_start = latest_date - pd.Timedelta(days=30)

    recent = fact_dt[
        (fact_dt["city"] == city) &
        (fact_dt["entry_date"] >= window_start)
    ].copy()

    peak_hour = int(recent["entry_hour"].value_counts().idxmax()) if len(recent) else 18
    active_now = (
        recent[recent["entry_hour"] == peak_hour]
        .groupby("location_id")["transaction_id"]
        .count()
        .div(max(30, (latest_date - window_start).days))
        .mul(1.5)
        .round()
        .astype(int)
        .rename("recent_txns")
    )
    df = df.join(active_now, on="location_id", how="left")
    df["recent_txns"] = df["recent_txns"].fillna(0).astype(int).clip(0, df["total_slots"])
    df["estimated_available"] = (df["total_slots"] - df["recent_txns"]).astype(int)
    df["availability_pct"] = (df["estimated_available"] / df["total_slots"] * 100).round(0)
    df["status"] = df["estimated_available"].apply(
        lambda x: "🟢 Available" if x > 10 else "🟡 Limited" if x > 0 else "🔴 Full"
    )

    st.markdown(f"### {len(df)} Parking Locations in {city}" + (f" — {hood}" if hood != "All" else ""))

    for _, loc in df.sort_values("estimated_available", ascending=False).iterrows():
        with st.expander(
            f"{loc['status']} **{loc['location_name']}** · {loc['neighborhood']} · "
            f"PKR {loc['hourly_rate_pkr']:.0f}/hr"
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Slots",      loc["total_slots"])
            c2.metric("Est. Available",   max(0, int(loc["estimated_available"])))
            c3.metric("Rate (PKR/hr)",    f"{loc['hourly_rate_pkr']:.0f}")
            c4.metric("Monthly Pass",     f"PKR {loc['monthly_pass_pkr']:.0f}")

            features = []
            if loc.get("has_anpr"):     features.append("📷 ANPR")
            if loc.get("has_valet"):    features.append("🤵 Valet")
            if loc.get("has_ev_charging"): features.append("⚡ EV Charging")
            if loc.get("is_covered"):   features.append("🏠 Covered")
            if features:
                st.markdown("  ".join(features))
            st.caption(f"Zone: {loc['zone_type']} | Floors: {loc['floors']}")


# ── Page: My History ──────────────────────────────────────────────────────────

def page_history():
    st.title("📋 My Parking History")

    cust_id = _get_customer_id()
    if not cust_id:
        st.warning("No customer ID linked to this account.")
        return

    fact = load_silver_fact()
    df   = _customer_fact(fact, cust_id)

    if df.empty:
        st.info("No parking history found for your account.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Visits",   f"{len(df):,}")
    c2.metric("Total Spent",    f"PKR {df['fee_pkr'].sum():,.0f}")
    c3.metric("Avg Duration",   f"{df['duration_minutes'].mean():.0f} min")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        monthly = df.groupby("entry_month")["fee_pkr"].sum().reset_index()
        monthly["month"] = monthly["entry_month"].apply(
            lambda m: ["Jan","Feb","Mar","Apr","May","Jun",
                       "Jul","Aug","Sep","Oct","Nov","Dec"][int(m)-1]
        )
        fig = px.bar(monthly, x="month", y="fee_pkr",
                     title="Monthly Spending (PKR)",
                     color="fee_pkr", color_continuous_scale="Greens",
                     template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        by_loc = df.groupby("location_name")["fee_pkr"].sum().reset_index().nlargest(8, "fee_pkr")
        fig2 = px.pie(by_loc, values="fee_pkr", names="location_name",
                      title="Spend by Location", hole=0.4,
                      template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Transaction History")
    cols_show = ["transaction_id", "location_name", "city", "entry_time",
                 "exit_time", "duration_minutes", "fee_pkr", "payment_method"]
    st.dataframe(
        df[[c for c in cols_show if c in df.columns]].sort_values("entry_time", ascending=False),
        use_container_width=True, hide_index=True,
    )


# ── Page: Season Pass ─────────────────────────────────────────────────────────

def page_season_pass():
    st.title("🎫 Season Pass")

    cust_id = _get_customer_id()
    custs   = pd.read_parquet(_ROOT / "data" / "silver" / "silver_customers.parquet")
    cust    = custs[custs["customer_id"] == cust_id]

    if cust.empty:
        st.warning("Customer profile not found.")
        return

    row = cust.iloc[0]
    has_pass   = bool(row.get("has_season_pass", False))
    expiry     = row.get("season_pass_expiry")

    if has_pass:
        st.success("✅ You have an active Season Pass")
        if expiry:
            st.info(f"Expiry: **{expiry}**")

        # Usage stats
        fact = load_silver_fact()
        df   = _customer_fact(fact, cust_id)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Uses",   f"{len(df):,}")
        c2.metric("Total Saved",  f"PKR {df['fee_pkr'].mean() * len(df) * 0.3:.0f}")
        c3.metric("Avg Duration", f"{df['duration_minutes'].mean():.0f} min")

        st.markdown("---")
        st.subheader("Benefits")
        st.markdown("""
        - ✅ Unlimited parking at all locations
        - ✅ Priority access to covered parking
        - ✅ 20% discount on valet service
        - ✅ Free EV charging (30 min/day)
        - ✅ Loyalty points × 2
        """)

        if st.button("🔄 Renew Season Pass", type="primary"):
            st.success("Renewal request submitted! Our team will contact you within 24 hours.")
    else:
        st.warning("You don't have a Season Pass yet.")
        st.markdown("""
        ### Season Pass Benefits
        - Unlimited monthly parking at PKR **2,500 – 5,000/month**
        - Save up to **40%** vs daily rates
        - Priority spot reservation
        - Access to all 52 locations in 10 cities
        """)
        if st.button("🎫 Purchase Season Pass", type="primary"):
            st.info("Redirecting to payment gateway... (Demo mode)")


# ── Page: My Violations ────────────────────────────────────────────────────────

def page_violations():
    st.title("🚨 My Violations")

    cust_id = _get_customer_id()
    fact    = load_silver_fact()
    cust_df = _customer_fact(fact, cust_id)

    viol = pd.read_parquet(_ROOT / "data" / "silver" / "silver_violations.parquet")

    # Filter violations by customer's vehicles
    cust_vehicles = cust_df["vehicle_id"].unique().tolist()
    my_viol = viol[viol["vehicle_id"].isin(cust_vehicles)]

    if my_viol.empty:
        st.success("✅ No violations on record. Keep parking responsibly!")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Violations", len(my_viol))
    c2.metric("Total Fines",      f"PKR {my_viol['fine_pkr'].sum():,.0f}")
    c3.metric("Outstanding",
              f"PKR {my_viol[~my_viol['fine_paid']]['fine_pkr'].sum():,.0f}")

    st.dataframe(
        my_viol[[
            "violation_id", "vehicle_id", "violation_type",
            "location_id", "violation_time", "fine_pkr", "fine_paid", "resolved",
        ]].sort_values("violation_time", ascending=False),
        use_container_width=True, hide_index=True,
    )

    unpaid = my_viol[~my_viol["fine_paid"]]
    if not unpaid.empty:
        st.warning(f"You have {len(unpaid)} unpaid fine(s) totalling "
                   f"PKR {unpaid['fine_pkr'].sum():,.0f}")
        if st.button("💳 Pay All Fines", type="primary"):
            st.success("Payment initiated! (Demo mode)")


# ── Page: Loyalty Score ────────────────────────────────────────────────────────

def page_loyalty():
    st.title("⭐ Loyalty Score")

    cust_id = _get_customer_id()
    rfm = load_gold("customer_rfm")
    cust = rfm[rfm["customer_id"] == cust_id]

    if cust.empty:
        st.info("No loyalty data yet. Start parking to earn points!")
        return

    row = cust.iloc[0]
    frequency = int(row.get("frequency", 0))
    monetary  = float(row.get("monetary_pkr", 0))
    recency   = int(row.get("recency_days", 999))

    # Score formula: F×10 + M/100 − R×0.5
    score = int(min(5000, max(0, frequency * 10 + monetary / 100 - recency * 0.5)))

    # Tier
    if score >= 3000:
        tier, color = "🥇 Gold Member",    "#FFD700"
    elif score >= 1500:
        tier, color = "🥈 Silver Member",  "#C0C0C0"
    else:
        tier, color = "🥉 Bronze Member",  "#CD7F32"

    st.markdown(f"""
        <div style='text-align:center; padding:20px; background:#f8f9fa;
             border-radius:12px; border:2px solid {color}'>
            <h1 style='color:{color}; margin:0'>{score:,}</h1>
            <p style='font-size:1.1rem; margin:4px 0'><b>{tier}</b></p>
            <p style='color:#888; margin:0'>Loyalty Points</p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Visits",      f"{frequency:,}")
    c2.metric("Total Spent",       f"PKR {monetary:,.0f}")
    c3.metric("Days Since Visit",  f"{recency}")

    st.subheader("How to Earn More Points")
    st.markdown("""
    | Action                     | Points |
    |---------------------------|--------|
    | Each parking session       | +10    |
    | Every PKR 100 spent        | +1     |
    | Season Pass holder         | ×2     |
    | JazzCash/EasyPaisa payment | +5     |
    | Refer a friend             | +50    |
    """)

    # Progress to next tier
    if score < 1500:
        needed = 1500 - score
        st.progress(score / 1500, text=f"Silver Member: {needed:,} pts to go")
    elif score < 3000:
        needed = 3000 - score
        st.progress((score - 1500) / 1500, text=f"Gold Member: {needed:,} pts to go")
    else:
        st.success("🏆 You've reached the highest tier — Gold Member!")
