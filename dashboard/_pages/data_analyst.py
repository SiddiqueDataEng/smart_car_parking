"""
Data Analyst Dashboard Pages
==============================
  - EDA Explorer       : Pick any Gold table → auto stats + charts
  - ML Metrics         : Model performance cards
  - Segmentation       : Customer cluster scatter
  - Pricing Simulator  : Slider-based dynamic pricing
"""
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.data_loader import load_gold, load_platinum, load_ml_metrics, load_ml_model

_ROOT = Path(__file__).resolve().parents[2]

GOLD_TABLES = {
    "Daily Revenue":          "daily_revenue",
    "Hourly Occupancy":       "hourly_occupancy",
    "Peak Analysis":          "peak_analysis",
    "Location Performance":   "location_performance",
    "Customer RFM":           "customer_rfm",
    "Violation Summary":      "violation_summary",
    "Monthly Trends":         "monthly_trends",
}


# ── Page: EDA Explorer ────────────────────────────────────────────────────────

def page_eda():
    st.title("📈 EDA Explorer")
    st.caption("Pick any Gold layer table to explore distribution, stats, and visualisations")

    selected = st.selectbox("Select Table", list(GOLD_TABLES.keys()), key="eda_table")
    df = load_gold(GOLD_TABLES[selected])

    if df.empty:
        st.warning("Table not found. Run the full pipeline first.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Rows",    f"{len(df):,}")
    c2.metric("Columns", len(df.columns))
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    c3.metric("Numeric Columns", len(numeric_cols))

    st.markdown("---")
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Summary Stats", "📉 Distribution", "🔥 Correlation", "🗃 Raw Data"])

    with tab1:
        st.subheader("Summary Statistics")
        st.dataframe(df[numeric_cols].describe().T.round(3), use_container_width=True)

    with tab2:
        col_sel = st.selectbox("Select column", numeric_cols, key="eda_dist_col")
        if col_sel:
            fig = px.histogram(
                df, x=col_sel, nbins=50,
                title=f"Distribution of {col_sel}",
                color_discrete_sequence=["#2E8B57"],
                template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Mean",   f"{df[col_sel].mean():,.2f}")
            col2.metric("Median", f"{df[col_sel].median():,.2f}")
            col3.metric("Std",    f"{df[col_sel].std():,.2f}")
            col4.metric("Skew",   f"{df[col_sel].skew():.3f}")

    with tab3:
        if len(numeric_cols) >= 2:
            corr = df[numeric_cols].corr()
            fig2 = px.imshow(
                corr, text_auto=".2f",
                title="Correlation Heatmap",
                color_continuous_scale="RdBu_r",
                zmin=-1, zmax=1,
                template="plotly_white",
                aspect="auto",
            )
            fig2.update_layout(height=500)
            st.plotly_chart(fig2, use_container_width=True)

    with tab4:
        st.dataframe(df.head(500), use_container_width=True, hide_index=True)


# ── Page: ML Metrics ─────────────────────────────────────────────────────────

def page_ml_metrics():
    st.title("🤖 ML Model Performance")

    metrics = load_ml_metrics()

    metric_display = {
        "forecasting": {
            "title": "📈 Revenue Forecasting (Prophet)",
            "color": "#2E8B57",
            "fields": {
                "avg_mape": ("Avg MAPE", "%"),
                "locations_trained": ("Locations Trained", ""),
                "min_mape": ("Best MAPE", "%"),
            },
        },
        "classification": {
            "title": "🎯 Violation Classifier (Random Forest)",
            "color": "#FF6B35",
            "fields": {
                "violation_f1": ("F1 Score", ""),
                "violation_roc_auc": ("ROC-AUC", ""),
                "churn_f1": ("Churn F1", ""),
                "churn_roc_auc": ("Churn AUC", ""),
            },
        },
        "clustering": {
            "title": "👥 Customer Clustering (K-Means)",
            "color": "#2196F3",
            "fields": {
                "k": ("Clusters (k)", ""),
                "silhouette_score": ("Silhouette Score", ""),
                "min_cluster_pct": ("Min Cluster Size", ""),
            },
        },
        "anomaly": {
            "title": "⚠️ Anomaly Detection (Isolation Forest)",
            "color": "#FF4444",
            "fields": {
                "flag_rate": ("Flag Rate", ""),
                "flagged": ("Flagged Transactions", ""),
                "total_transactions": ("Total Scanned", ""),
            },
        },
        "pricing": {
            "title": "💡 Dynamic Pricing (Gradient Boosting)",
            "color": "#9C27B0",
            "fields": {
                "rmse": ("RMSE (PKR)", ""),
                "r2": ("R² Score", ""),
                "mape": ("MAPE", "%"),
            },
        },
    }

    for model_key, cfg in metric_display.items():
        model_metrics = metrics.get(model_key, {})
        with st.container():
            st.markdown(f"""
                <div style='border-left: 4px solid {cfg["color"]};
                     padding: 12px 16px; border-radius: 4px;
                     background: #f8f9fa; margin-bottom: 16px;'>
                    <b style='color: {cfg["color"]}'>{cfg["title"]}</b>
                </div>
            """, unsafe_allow_html=True)

            cols = st.columns(len(cfg["fields"]))
            for col, (field_key, (label, suffix)) in zip(cols, cfg["fields"].items()):
                val = model_metrics.get(field_key)
                if val is not None:
                    try:
                        col.metric(label, f"{float(val):,.3f}{suffix}")
                    except (ValueError, TypeError):
                        col.metric(label, str(val))
                else:
                    col.metric(label, "—")

        if not model_metrics:
            st.warning(f"Run `python -m src.ml.run_all_models` to generate metrics for {model_key}.")


# ── Page: Customer Segmentation ───────────────────────────────────────────────

def page_segmentation():
    st.title("👥 Customer Segmentation")

    clust_df = load_platinum("clustering")

    if clust_df.empty or "cluster_name" not in clust_df.columns:
        st.warning("Clustering model not yet run. Run `python -m src.ml.clustering` first.")
        return

    # Summary
    seg_summary = (
        clust_df.groupby("cluster_name")
        .agg(
            customers=("customer_id", "count"),
            avg_monetary=("monetary_pkr", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_recency=("recency_days", "mean"),
        )
        .reset_index()
        .round(1)
    )
    st.subheader("Segment Summary")
    st.dataframe(seg_summary, use_container_width=True, hide_index=True)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        # Scatter (PCA coordinates if available)
        if "pca_x" in clust_df.columns:
            sample = clust_df.sample(min(2000, len(clust_df)), random_state=42)
            fig = px.scatter(
                sample, x="pca_x", y="pca_y",
                color="cluster_name",
                hover_data=["monetary_pkr", "frequency", "recency_days"],
                title="Customer Segments (PCA 2D)",
                template="plotly_white",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            # RFM scatter fallback
            fig = px.scatter(
                clust_df.sample(min(1000, len(clust_df)), random_state=42),
                x="recency_days", y="monetary_pkr",
                color="cluster_name",
                size="frequency",
                title="RFM Scatter by Segment",
                template="plotly_white",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Pie chart of segment sizes
        seg_sizes = clust_df["cluster_name"].value_counts().reset_index()
        seg_sizes.columns = ["segment", "count"]
        fig2 = px.pie(
            seg_sizes, values="count", names="segment",
            hole=0.45, title="Segment Distribution",
            color_discrete_sequence=px.colors.qualitative.Set2,
            template="plotly_white",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # RFM heatmap by segment
    st.subheader("RFM Heatmap by Segment")
    rfm_heat = (
        clust_df.groupby("cluster_name")[
            ["recency_days", "frequency", "monetary_pkr"]
        ]
        .mean()
        .round(1)
    )
    fig3 = px.imshow(
        rfm_heat.T, text_auto=True,
        title="Average RFM by Cluster",
        color_continuous_scale="Greens",
        template="plotly_white",
        aspect="auto",
    )
    st.plotly_chart(fig3, use_container_width=True)


# ── Page: Pricing Simulator ───────────────────────────────────────────────────

def page_pricing_sim():
    st.title("💡 Dynamic Pricing Simulator")
    st.caption("Adjust inputs to get AI-recommended parking fee in PKR")

    model_bundle = load_ml_model("dynamic_pricing")
    if model_bundle is None:
        st.warning("Pricing model not yet trained. Run `python -m src.ml.pricing` first.")
        return

    model    = model_bundle["model"]
    feat_cols = model_bundle["features"]

    # Input sliders
    col1, col2, col3 = st.columns(3)
    with col1:
        occupancy = st.slider("Occupancy Rate (%)", 0, 100, 70, key="price_occ") / 100
        hour      = st.slider("Hour of Day", 0, 23, 18, key="price_hour")
        dow       = st.slider("Day of Week (0=Mon, 6=Sun)", 0, 6, 2, key="price_dow")
    with col2:
        month        = st.slider("Month", 1, 12, 6, key="price_month")
        duration     = st.slider("Duration (minutes)", 15, 480, 60, key="price_dur")
        hourly_rate  = st.slider("Location Base Rate (PKR/hr)", 30, 150, 60, key="price_rate")
    with col3:
        vtype_options = ["Suzuki Alto", "Honda City", "SUV", "Motorbike", "Bus/Minibus",
                         "Rickshaw", "Toyota Corolla", "Honda Civic"]
        vtype    = st.selectbox("Vehicle Type", vtype_options, key="price_vtype")
        zone_opts = ["Commercial", "Residential", "Hospital", "Market",
                     "Corporate", "Educational", "Religious", "Transit Hub"]
        zone     = st.selectbox("Zone Type", zone_opts, key="price_zone")
        city_opts = ["Karachi", "Lahore", "Islamabad", "Rawalpindi",
                     "Peshawar", "Quetta", "Multan", "Faisalabad"]
        city     = st.selectbox("City", city_opts, key="price_city")

    st.markdown("---")
    col_flags = st.columns(4)
    is_ramadan   = col_flags[0].checkbox("🌙 Ramadan", key="price_ram")
    is_eid       = col_flags[1].checkbox("🎉 Eid Day", key="price_eid")
    is_monsoon   = col_flags[2].checkbox("🌧 Monsoon", key="price_mon")
    is_weekend   = col_flags[3].checkbox("🏖 Weekend", key="price_wknd")
    is_holiday   = col_flags[0].checkbox("🇵🇰 Public Holiday", key="price_hol")
    is_indep     = col_flags[1].checkbox("🎆 Independence Day", key="price_ind")

    # Encode categoricals
    from pandas import Categorical
    vtype_enc = {"Suzuki Alto": 0, "Honda City": 1, "SUV": 5, "Motorbike": 6,
                 "Bus/Minibus": 8, "Rickshaw": 7, "Toyota Corolla": 3, "Honda Civic": 4}.get(vtype, 0)
    zone_enc  = {"Commercial": 0, "Residential": 1, "Hospital": 2, "Market": 3,
                 "Corporate": 4, "Educational": 5, "Religious": 6, "Transit Hub": 7}.get(zone, 0)
    city_enc  = {"Karachi": 0, "Lahore": 1, "Islamabad": 2, "Rawalpindi": 3,
                 "Peshawar": 4, "Quetta": 5, "Multan": 6, "Faisalabad": 7}.get(city, 0)

    input_data = {
        "occupancy_rate": occupancy,
        "entry_hour": hour, "day_of_week": dow, "entry_month": month,
        "duration_minutes": duration, "vehicle_type_enc": vtype_enc,
        "zone_type_enc": zone_enc, "city_enc": city_enc,
        "hourly_rate_pkr": hourly_rate,
        "is_ramadan": int(is_ramadan), "is_eid": int(is_eid),
        "is_monsoon": int(is_monsoon), "is_weekend": int(is_weekend),
        "is_public_holiday": int(is_holiday), "is_independence_day": int(is_indep),
        "hour_sin": np.sin(2 * np.pi * hour / 24),
        "hour_cos": np.cos(2 * np.pi * hour / 24),
    }

    feat_vals = [input_data.get(f, 0) for f in feat_cols]
    try:
        recommended = float(model.predict([feat_vals])[0])
        recommended = max(30, round(recommended, 0))

        # Base calculation for comparison
        base_fee = hourly_rate * max(1, duration / 60)

        col_r1, col_r2, col_r3 = st.columns(3)
        col_r1.metric("🤖 Recommended Fee", f"PKR {recommended:,.0f}")
        col_r2.metric("📋 Base Rate Fee",   f"PKR {base_fee:,.0f}")
        col_r3.metric("💰 Difference",      f"PKR {recommended - base_fee:+,.0f}",
                      delta=f"{(recommended - base_fee) / max(base_fee, 1):.1%}")

        # Occupancy effect chart
        occ_range = np.linspace(0, 1, 50)
        fees = []
        for occ_val in occ_range:
            v = input_data.copy()
            v["occupancy_rate"] = occ_val
            fv = [v.get(f, 0) for f in feat_cols]
            fees.append(float(model.predict([fv])[0]))

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=occ_range * 100, y=fees,
            name="Recommended Fee", fill="tozeroy",
            line=dict(color="#2E8B57", width=2),
            fillcolor="rgba(46,139,87,0.15)",
        ))
        fig.add_vline(x=occupancy * 100, line_dash="dash",
                      line_color="#FF6B35", annotation_text="Current")
        fig.update_layout(
            title="Recommended Fee vs Occupancy Rate",
            xaxis_title="Occupancy Rate (%)",
            yaxis_title="Recommended Fee (PKR)",
            template="plotly_white", height=350,
        )
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Prediction error: {e}")
