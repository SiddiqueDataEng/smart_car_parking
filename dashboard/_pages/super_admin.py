"""
Super Admin Dashboard Pages
============================
  - Overview       : KPI cards + city map
  - Revenue        : MoM trends, city heatmap, payment pie, top locations
  - Forecast       : Prophet 30-day forecast per location
  - Anomaly Alerts : Isolation Forest flagged transactions
  - Catalog        : Data catalog viewer
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import (
    load_gold, load_silver_fact, load_ml_metrics, query, get_duckdb_conn,
)

_ROOT = Path(__file__).resolve().parents[2]


# ── Helper ────────────────────────────────────────────────────────────────────

def _metric(col, label, value, delta=None, prefix="", suffix=""):
    with col:
        st.metric(label, f"{prefix}{value:,.0f}{suffix}", delta=delta)


def _city_filter(df: pd.DataFrame, key: str = "city_filter") -> pd.DataFrame:
    cities = ["All Cities"] + sorted(df["city"].unique().tolist())
    sel = st.selectbox("Filter by City", cities, key=key)
    if sel != "All Cities":
        df = df[df["city"] == sel]
    return df


# ── Page: Overview ────────────────────────────────────────────────────────────

def page_overview():
    st.title("📊 Executive Overview")
    st.caption("All figures for the full 2023–2024 dataset")

    # KPI cards
    fact = load_silver_fact()
    loc_perf = load_gold("location_performance")

    total_rev   = fact["fee_pkr"].sum()
    total_txns  = len(fact)
    active_locs = fact["location_id"].nunique()
    avg_dur     = fact["duration_minutes"].mean()

    monthly = load_gold("monthly_trends")
    latest  = monthly.sort_values(["year", "month"]).iloc[-1]
    mom     = latest.get("mom_revenue_growth_pct", 0) or 0

    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "💰 Total Revenue", total_rev / 1e6, f"{mom:+.1f}% MoM", suffix=" M PKR")
    _metric(c2, "🎫 Total Transactions", total_txns)
    _metric(c3, "📍 Active Locations", active_locs)
    _metric(c4, "⏱ Avg Duration (min)", avg_dur)

    st.markdown("---")
    col_left, col_right = st.columns(2)

    # City Revenue Bar
    city_rev = (
        fact.groupby("city")["fee_pkr"]
        .sum()
        .reset_index()
        .sort_values("fee_pkr", ascending=False)
    )
    with col_left:
        fig = px.bar(
            city_rev, x="city", y="fee_pkr",
            title="Revenue by City (PKR)",
            color="fee_pkr", color_continuous_scale="Greens",
            template="plotly_white",
        )
        fig.update_layout(showlegend=False, height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Vehicle Type Donut
    vtype_rev = fact.groupby("vehicle_type")["fee_pkr"].sum().reset_index()
    with col_right:
        fig2 = px.pie(
            vtype_rev, values="fee_pkr", names="vehicle_type",
            title="Revenue by Vehicle Type",
            hole=0.45, template="plotly_white",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig2.update_layout(height=350)
        st.plotly_chart(fig2, use_container_width=True)

    # Monthly Trend
    st.subheader("Monthly Revenue Trend by City")
    monthly["period"] = monthly["year"].astype(str) + "-" + monthly["month"].apply(
        lambda m: f"{m:02d}"
    )
    cities_sel = st.multiselect(
        "Select Cities", sorted(monthly["city"].unique()),
        default=["Karachi", "Lahore", "Islamabad"],
        key="overview_cities",
    )
    plot_m = monthly[monthly["city"].isin(cities_sel)] if cities_sel else monthly
    fig3 = px.line(
        plot_m, x="period", y="total_revenue_pkr",
        color="city", title="Monthly Revenue (PKR)",
        template="plotly_white",
        color_discrete_sequence=px.colors.qualitative.Set1,
    )
    fig3.update_layout(height=380)
    st.plotly_chart(fig3, use_container_width=True)

    # Top 10 Locations Table
    st.subheader("Top 10 Locations")
    top = loc_perf.nlargest(10, "total_revenue_pkr")[
        ["location_name", "city", "zone_type", "total_transactions",
         "total_revenue_pkr", "violation_count", "daily_utilisation_rate"]
    ].copy()
    top["total_revenue_pkr"]      = top["total_revenue_pkr"].apply(lambda x: f"PKR {x:,.0f}")
    top["daily_utilisation_rate"] = top["daily_utilisation_rate"].apply(
        lambda x: f"{x:.2f} txn/slot/day"
    )
    top = top.rename(columns={
        "location_name":         "Location",
        "city":                  "City",
        "zone_type":             "Zone",
        "total_transactions":    "Transactions",
        "total_revenue_pkr":     "Revenue",
        "violation_count":       "Violations",
        "daily_utilisation_rate":"Turnover (txn/slot/day)",
    })
    st.dataframe(top, use_container_width=True, hide_index=True)


# ── Page: Revenue Analytics ───────────────────────────────────────────────────

def page_revenue():
    st.title("💰 Revenue Analytics")

    fact    = load_silver_fact()
    monthly = load_gold("monthly_trends")

    # Filters
    col1, col2 = st.columns(2)
    with col1:
        cities = ["All Cities"] + sorted(fact["city"].unique().tolist())
        city   = st.selectbox("City", cities, key="rev_city")
    with col2:
        years = sorted(fact["entry_year"].unique().tolist())
        year  = st.selectbox("Year", ["All"] + [str(y) for y in years], key="rev_year")

    df = fact.copy()
    if city != "All Cities":
        df = df[df["city"] == city]
    if year != "All":
        df = df[df["entry_year"] == int(year)]

    # KPI row
    c1, c2, c3, c4 = st.columns(4)
    _metric(c1, "Total Revenue", df["fee_pkr"].sum() / 1e6, suffix=" M PKR")
    _metric(c2, "Transactions",  len(df))
    _metric(c3, "Avg Fee",       df["fee_pkr"].mean(), suffix=" PKR")
    _metric(c4, "Avg Duration",  df["duration_minutes"].mean(), suffix=" min")

    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Trend", "🗺 City Heatmap", "💳 Payment Mix", "📍 Top Locations"])

    with tab1:
        daily = df.groupby("entry_date")["fee_pkr"].sum().reset_index()
        daily["rolling_7d"] = daily["fee_pkr"].rolling(7).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily["entry_date"], y=daily["fee_pkr"],
                                 name="Daily", opacity=0.4,
                                 line=dict(color="#2E8B57", width=1)))
        fig.add_trace(go.Scatter(x=daily["entry_date"], y=daily["rolling_7d"],
                                 name="7-day MA", line=dict(color="#FF6B35", width=2)))
        fig.update_layout(title="Daily Revenue with 7-day Moving Average",
                          xaxis_title="Date", yaxis_title="Revenue (PKR)",
                          template="plotly_white", height=380)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        # City × Month heatmap
        hm_data = (
            fact.groupby(["city", "entry_month"])["fee_pkr"]
            .sum()
            .reset_index()
            .pivot(index="city", columns="entry_month", values="fee_pkr")
            .fillna(0)
        )
        fig2 = px.imshow(
            hm_data, text_auto=".2s",
            title="Revenue Heatmap: City × Month",
            color_continuous_scale="Greens",
            aspect="auto", template="plotly_white",
        )
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

    with tab3:
        pay_rev = df.groupby("payment_method")["fee_pkr"].sum().reset_index()
        fig3 = px.pie(
            pay_rev, values="fee_pkr", names="payment_method",
            hole=0.4, title="Revenue by Payment Method",
            color_discrete_sequence=["#2E8B57", "#FF6B35", "#2196F3", "#9C27B0"],
            template="plotly_white",
        )
        st.plotly_chart(fig3, use_container_width=True)

        pay_count = df.groupby("payment_method").size().reset_index(name="count")
        pay_count["pct"] = (pay_count["count"] / pay_count["count"].sum() * 100).round(1)
        st.dataframe(pay_count, use_container_width=True, hide_index=True)

    with tab4:
        lp = load_gold("location_performance")
        if city != "All Cities":
            lp = lp[lp["city"] == city]
        top10 = lp.nlargest(10, "total_revenue_pkr")
        fig4 = px.bar(
            top10, y="location_name", x="total_revenue_pkr",
            orientation="h", title="Top 10 Locations by Revenue",
            color="total_revenue_pkr", color_continuous_scale="Greens",
            template="plotly_white",
        )
        fig4.update_layout(height=420)
        st.plotly_chart(fig4, use_container_width=True)


# ── Page: Forecast ────────────────────────────────────────────────────────────

def page_forecast():
    st.title("🔮 Revenue Forecast (30-day)")

    out_dir = _ROOT / "notebooks" / "outputs"
    loc_perf = load_gold("location_performance")
    locations = loc_perf.sort_values("total_revenue_pkr", ascending=False)

    selected_loc = st.selectbox(
        "Select Location",
        locations["location_id"].tolist(),
        format_func=lambda lid: (
            locations.loc[locations["location_id"] == lid, "location_name"].values[0]
            + f" ({locations.loc[locations['location_id'] == lid, 'city'].values[0]})"
        ),
        key="forecast_loc",
    )

    csv_path = out_dir / f"forecast_{selected_loc}.csv"
    fact = load_silver_fact()
    df_loc = (
        fact[fact["location_id"] == selected_loc]
        .groupby("entry_date")["fee_pkr"]
        .sum()
        .reset_index()
    )

    if csv_path.exists():
        forecast = pd.read_csv(csv_path, parse_dates=["ds"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(df_loc["entry_date"]), y=df_loc["fee_pkr"],
            name="Historical", line=dict(color="#2E8B57", width=2)
        ))
        fig.add_trace(go.Scatter(
            x=forecast["ds"], y=forecast["yhat"],
            name="Forecast", line=dict(color="#FF6B35", dash="dash", width=2)
        ))
        fig.add_trace(go.Scatter(
            x=pd.concat([forecast["ds"], forecast["ds"][::-1]]),
            y=pd.concat([forecast["yhat_upper"], forecast["yhat_lower"][::-1]]),
            fill="toself", fillcolor="rgba(255,107,53,0.12)",
            line=dict(color="rgba(255,255,255,0)"),
            name="95% Confidence Interval",
        ))
        loc_name = locations.loc[
            locations["location_id"] == selected_loc, "location_name"
        ].values[0]
        fig.update_layout(
            title=f"Revenue Forecast — {loc_name}",
            xaxis_title="Date", yaxis_title="Revenue (PKR)",
            template="plotly_white", height=450,
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Forecast Data")
        future = forecast[forecast["ds"] > pd.to_datetime(df_loc["entry_date"].max())]
        future_display = future[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        future_display.columns = ["Date", "Forecast (PKR)", "Lower CI", "Upper CI"]
        st.dataframe(future_display.round(0), use_container_width=True, hide_index=True)
    else:
        st.info("Forecast not yet generated. Run `python -m src.ml.forecasting` first.")
        st.subheader("Historical Revenue")
        fig = px.line(df_loc, x="entry_date", y="fee_pkr",
                      title="Historical Revenue",
                      template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)


# ── Page: Anomaly Alerts ──────────────────────────────────────────────────────

def page_anomalies():
    st.title("⚠️ Anomaly Alerts")
    st.caption("Transactions flagged by Isolation Forest ML model")

    try:
        fact = load_silver_fact()
        if "is_anomaly" not in fact.columns:
            st.warning("Anomaly scores not yet computed. Run `python -m src.ml.anomaly` first.")
            return

        total   = len(fact)
        flagged = int(fact["is_anomaly"].sum())
        rate    = flagged / total if total > 0 else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Transactions", f"{total:,}")
        c2.metric("Flagged Anomalies",  f"{flagged:,}", f"{rate:.2%}")
        c3.metric("Normal Transactions", f"{total - flagged:,}")

        st.markdown("---")
        anomalies = fact[fact["is_anomaly"] == 1].sort_values(
            "anomaly_score" if "anomaly_score" in fact.columns else "fee_pkr"
        )

        col1, col2 = st.columns([2, 1])
        with col1:
            # Scatter
            sample = fact.sample(min(3000, len(fact)), random_state=42).copy()
            sample["Type"] = sample["is_anomaly"].map({1: "Anomaly", 0: "Normal"})
            fig = px.scatter(
                sample, x="duration_minutes", y="fee_pkr",
                color="Type",
                color_discrete_map={"Normal": "#2E8B57", "Anomaly": "#FF4444"},
                opacity=0.5, template="plotly_white",
                title="Fee vs Duration (Anomalies Highlighted)",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Hour distribution
            hour_anom = (
                fact.groupby("entry_hour")["is_anomaly"].mean()
                .reset_index()
                .rename(columns={"is_anomaly": "anomaly_rate"})
            )
            fig2 = px.bar(
                hour_anom, x="entry_hour", y="anomaly_rate",
                title="Anomaly Rate by Hour",
                color="anomaly_rate", color_continuous_scale="Reds",
                template="plotly_white",
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Flagged Transactions")
        display_cols = [
            "transaction_id", "city", "vehicle_type", "entry_time",
            "entry_hour", "duration_minutes", "fee_pkr",
            "is_blacklisted", "anomaly_score",
        ]
        disp = anomalies[[c for c in display_cols if c in anomalies.columns]].head(100)
        st.dataframe(disp, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error loading anomaly data: {e}")


# ── Page: Data Catalog ────────────────────────────────────────────────────────

def page_catalog():
    st.title("🗂️ Data Catalog & Lineage")

    import json
    cat_path = _ROOT / "data" / "catalog.json"
    lin_path = _ROOT / "data" / "lineage.json"

    if not cat_path.exists():
        st.warning("Catalog not yet generated. Run the full pipeline first.")
        return

    with open(cat_path) as f:
        catalog = json.load(f)
    with open(lin_path) as f:
        lineage = json.load(f)

    rows = list(catalog.values())
    df_cat = pd.DataFrame(rows)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Datasets",    len(df_cat))
    c2.metric("Total Rows",        f"{df_cat['row_count'].sum():,}")
    c3.metric("Bronze Datasets",   len(df_cat[df_cat["layer"] == "Bronze"]))
    c4.metric("Gold Datasets",     len(df_cat[df_cat["layer"] == "Gold"]))

    st.markdown("---")
    tab1, tab2 = st.tabs(["📋 Catalog Table", "🔗 Lineage Graph"])

    with tab1:
        layer_filter = st.selectbox(
            "Filter by Layer", ["All"] + sorted(df_cat["layer"].unique()),
            key="cat_layer_filter"
        )
        df_show = df_cat if layer_filter == "All" else df_cat[df_cat["layer"] == layer_filter]
        display = df_show[["name", "layer", "row_count", "last_updated", "description"]].copy()
        display["row_count"] = display["row_count"].apply(lambda x: f"{x:,}")
        display["last_updated"] = display["last_updated"].str[:19]
        st.dataframe(display.sort_values(["layer", "name"]),
                     use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("Dataset Lineage (Source → Target)")
        for target, sources in sorted(lineage.items()):
            sources_str = " + ".join(f"`{s}`" for s in sources)
            st.markdown(f"**{sources_str}** → `{target}`")
