"""
Location Manager Dashboard Pages
==================================
  - Occupancy  : Real-time slot grid (color-coded)
  - Staff       : Shift overview table
  - Revenue     : Today's revenue vs target gauge
  - Violations  : Violation log with plate + timestamp
"""
import random
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import load_gold, load_silver_fact, query


# ── Page: Slot Occupancy ──────────────────────────────────────────────────────

def page_occupancy():
    st.title("🅿 Slot Occupancy Monitor")
    st.caption("Simulated real-time view based on latest transaction data")

    loc_perf  = load_gold("location_performance")
    hourly    = load_gold("hourly_occupancy")

    # ── Compute realistic instantaneous occupancy per location ──────────────
    # Use gold_hourly_occupancy at peak hour to get a proper occupancy rate,
    # then scale it to absolute slot counts.
    hourly = load_gold("hourly_occupancy")

    # Peak hour = hour with highest average transaction count across all locations
    peak_hour = int(
        hourly.groupby("hour_of_day")["transaction_count"].mean().idxmax()
    )

    # Average occupancy rate at peak hour per location
    peak_occ = (
        hourly[hourly["hour_of_day"] == peak_hour]
        .groupby("location_id")["occupancy_rate_proxy"]
        .mean()
        .clip(0.05, 0.95)          # keep between 5% and 95%
        .rename("occ_rate")
    )
    loc_perf = loc_perf.join(peak_occ, on="location_id", how="left")
    # Fallback to 50% for locations with no data
    loc_perf["occ_rate"] = loc_perf["occ_rate"].fillna(0.50)
    loc_perf = loc_perf.join(peak_occ, on="location_id", how="left")
    # Fallback to 50% for locations with no data
    loc_perf["occ_rate"] = loc_perf["occ_rate"].fillna(0.50)

    cities = ["All Cities"] + sorted(loc_perf["city"].unique().tolist())
    city   = st.selectbox("Filter by City", cities, key="occ_city")
    df = loc_perf if city == "All Cities" else loc_perf[loc_perf["city"] == city]

    st.caption(f"Showing occupancy at peak hour ({peak_hour}:00) — averaged over 2-year dataset")
    st.markdown("---")

    for _, loc in df.iterrows():
        total     = int(loc["total_slots"])
        occ_rate  = float(loc["occ_rate"])
        occupied  = max(1, round(total * occ_rate))
        # Violations: proportional to real violation count from gold table
        violation = min(
            max(0, int(loc.get("violation_count", 0) // 730)),
            max(0, total - occupied)
        )
        free      = max(0, total - occupied - violation)

        occ_pct  = occupied  / total if total > 0 else 0
        free_pct = free      / total if total > 0 else 0

        with st.expander(
            f"📍 {loc['location_name']} — {loc['city']} ({loc['zone_type']})"
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Slots",   total)
            c2.metric("🟢 Free",       free,      delta=f"{free_pct:.0%}")
            c3.metric("🔴 Occupied",   occupied,  delta=f"{occ_pct:.0%}")
            c4.metric("🟡 Violations", violation)

            # Slot grid (up to 60 slots visualised)
            n_show = min(total, 60)
            rng = random.Random(int(loc["total_slots"]) + occupied)
            slot_states = (
                ["🟢"] * free + ["🔴"] * occupied + ["🟡"] * violation
            )[:n_show]
            rng.shuffle(slot_states)

            cols_per_row = 15
            for row_start in range(0, len(slot_states), cols_per_row):
                row_slots = slot_states[row_start: row_start + cols_per_row]
                st.markdown(" ".join(row_slots))

            if total > 60:
                st.caption(f"Showing 60 of {total} slots")


# ── Page: Staff Shifts ────────────────────────────────────────────────────────

def page_staff():
    st.title("👥 Staff Shift Overview")

    staff_df = pd.read_parquet(
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "data" / "silver" / "silver_staff.parquet"
    )
    loc_perf = load_gold("location_performance")

    cities = ["All Cities"] + sorted(loc_perf["city"].unique().tolist())
    city   = st.selectbox("City", cities, key="staff_city")
    role_filter = st.multiselect(
        "Role",
        ["Security Guard", "Cashier", "Valet", "Supervisor"],
        default=["Security Guard", "Cashier"],
        key="staff_role",
    )

    # Join location data
    loc_city = loc_perf.set_index("location_id")["city"].to_dict()
    staff_df["city"] = staff_df["location_id"].map(loc_city)

    df = staff_df.copy()
    if city != "All Cities":
        df = df[df["city"] == city]
    if role_filter:
        df = df[df["role"].isin(role_filter)]

    # Summary
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Shifts",   f"{len(df):,}")
    c2.metric("Unique Staff",   df["staff_name"].nunique())
    c3.metric("Locations",      df["location_id"].nunique())

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        role_cnt = df["role"].value_counts().reset_index()
        role_cnt.columns = ["role", "count"]
        fig = px.pie(role_cnt, values="count", names="role",
                     title="Staff by Role", hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Set2,
                     template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        shift_cnt = df["shift_type"].value_counts().reset_index()
        shift_cnt.columns = ["shift", "count"]
        fig2 = px.bar(shift_cnt, x="shift", y="count",
                      title="Shifts by Type",
                      color="shift", template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Recent Shifts")
    display = df[["shift_id", "location_id", "staff_name", "role",
                  "shift_type", "shift_start", "shift_end"]].head(100)
    st.dataframe(display, use_container_width=True, hide_index=True)


# ── Page: Today's Revenue Gauge ───────────────────────────────────────────────

def page_revenue_gauge():
    st.title("💰 Today's Revenue Dashboard")

    fact = load_silver_fact()
    loc_perf = load_gold("location_performance")

    # Use most recent date in dataset as "today"
    today = pd.to_datetime(fact["entry_date"]).max()
    today_data = fact[pd.to_datetime(fact["entry_date"]) == today]

    c1, c2, c3 = st.columns(3)
    c1.metric("Date",          str(today.date()))
    c2.metric("Transactions",  f"{len(today_data):,}")
    c3.metric("Revenue (PKR)", f"{today_data['fee_pkr'].sum():,.0f}")

    st.markdown("---")

    # Gauge per location (top 6)
    loc_today = (
        today_data.groupby("location_id")["fee_pkr"].sum()
        .reset_index()
        .merge(loc_perf[["location_id", "location_name", "city", "total_slots"]])
        .nlargest(6, "fee_pkr")
    )

    cols = st.columns(3)
    for idx, (_, row) in enumerate(loc_today.iterrows()):
        # Target: avg daily revenue for that location
        avg_daily = loc_perf.loc[
            loc_perf["location_id"] == row["location_id"], "total_revenue_pkr"
        ].values
        avg_daily = float(avg_daily[0]) / 730 if len(avg_daily) > 0 else 1000
        actual = float(row["fee_pkr"])
        pct = min(actual / max(avg_daily, 1), 1.5)

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=actual,
            delta={"reference": avg_daily, "relative": True, "valueformat": ".1%"},
            title={"text": f"{row['location_name']}<br><span style='font-size:0.8em'>{row['city']}</span>"},
            gauge={
                "axis": {"range": [0, avg_daily * 1.5]},
                "bar":  {"color": "#2E8B57"},
                "steps": [
                    {"range": [0, avg_daily * 0.5], "color": "#FFCDD2"},
                    {"range": [avg_daily * 0.5, avg_daily], "color": "#FFF9C4"},
                    {"range": [avg_daily, avg_daily * 1.5], "color": "#C8E6C9"},
                ],
                "threshold": {
                    "line": {"color": "#FF4444", "width": 3},
                    "thickness": 0.75,
                    "value": avg_daily,
                },
            },
        ))
        fig.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20))
        with cols[idx % 3]:
            st.plotly_chart(fig, use_container_width=True)


# ── Page: Violations Log ──────────────────────────────────────────────────────

def page_violations():
    st.title("🚨 Violations Log")

    viol = pd.read_parquet(
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "data" / "silver" / "silver_violations.parquet"
    )
    loc_perf = load_gold("location_performance")
    loc_map  = loc_perf.set_index("location_id")[["location_name", "city"]].to_dict("index")

    viol["location_name"] = viol["location_id"].map(
        lambda x: loc_map.get(x, {}).get("location_name", x)
    )
    viol["city"] = viol["location_id"].map(
        lambda x: loc_map.get(x, {}).get("city", "")
    )

    # Summary metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Violations",  f"{len(viol):,}")
    c2.metric("Total Fines (PKR)", f"{viol['fine_pkr'].sum():,.0f}")
    c3.metric("Fines Paid",        f"{viol['fine_paid'].sum():,}")
    c4.metric("Resolved",          f"{viol['resolved'].sum():,}")

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        vtype = viol["violation_type"].value_counts().reset_index()
        vtype.columns = ["type", "count"]
        fig = px.bar(vtype, x="count", y="type", orientation="h",
                     title="Violations by Type",
                     color="count", color_continuous_scale="Reds",
                     template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        city_v = viol["city"].value_counts().reset_index().head(10)
        city_v.columns = ["city", "count"]
        fig2 = px.bar(city_v, x="city", y="count",
                      title="Violations by City",
                      color="count", color_continuous_scale="Oranges",
                      template="plotly_white")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Violation Records")
    search = st.text_input("Search by Vehicle ID or Violation Type", key="viol_search")
    display = viol[[
        "violation_id", "vehicle_id", "violation_type",
        "location_name", "city", "violation_time",
        "fine_pkr", "fine_paid", "resolved",
    ]].copy()
    if search:
        mask = (
            display["vehicle_id"].str.contains(search, case=False, na=False)
            | display["violation_type"].str.contains(search, case=False, na=False)
        )
        display = display[mask]
    st.dataframe(display.head(200), use_container_width=True, hide_index=True)
