"""
SQL Editor Page — 50+ Analytical Queries + Free-Form Runner
============================================================
Accessible to: Super Admin, Data Analyst
"""
import time
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.data_loader import get_duckdb_conn
from dashboard.query_library import QUERY_LIBRARY, get_categories, get_by_category

_ROOT = Path(__file__).resolve().parents[2]


def page_sql_editor():
    st.title("🔍 SQL Editor")
    st.caption("Run analytical queries against all Medallion layers using DuckDB SQL")

    # ── Query library sidebar ──────────────────────────────────────────────────
    col_left, col_right = st.columns([1, 3])

    with col_left:
        st.subheader("Query Library")
        st.caption(f"{len(QUERY_LIBRARY)} prebuilt queries")

        category = st.selectbox(
            "Category",
            ["— Select —"] + get_categories(),
            key="sql_category",
        )

        selected_query_id = None
        if category != "— Select —":
            queries_in_cat = get_by_category(category)
            query_names = [f"{q['id']}: {q['name']}" for q in queries_in_cat]
            sel = st.selectbox("Query", ["— Choose —"] + query_names, key="sql_query_name")
            if sel != "— Choose —":
                selected_query_id = sel.split(":")[0].strip()

        st.markdown("---")
        # Query history
        if st.session_state.get("query_history"):
            st.subheader("⏱ History")
            for i, hist in enumerate(reversed(st.session_state["query_history"][-10:])):
                with st.expander(f"Q{len(st.session_state['query_history'])-i}: {hist['time']}", expanded=False):
                    st.code(hist["sql"][:200] + ("..." if len(hist["sql"]) > 200 else ""), language="sql")
                    if st.button("Load", key=f"hist_{i}"):
                        st.session_state["sql_editor_content"] = hist["sql"]
                        st.rerun()

    with col_right:
        # Pre-fill editor when a library query is selected
        if selected_query_id:
            from dashboard.query_library import get_by_id
            q = get_by_id(selected_query_id)
            st.session_state["sql_editor_content"] = q.get("sql", "").strip()
            st.info(f"**{q['name']}** — {q['description']}")

        # Code editor (text area)
        default_sql = st.session_state.get(
            "sql_editor_content",
            "-- Write your SQL query here\n-- All views: silver_fact, silver_locations, silver_vehicles,\n"
            "--   silver_customers, silver_violations, silver_anpr, silver_staff,\n"
            "--   gold_daily_revenue, gold_hourly_occupancy, gold_peak_analysis,\n"
            "--   gold_location_performance, gold_customer_rfm, gold_violation_summary,\n"
            "--   gold_monthly_trends, bronze_transactions, sensor_events\n\n"
            "SELECT city, COUNT(*) AS transactions, ROUND(SUM(fee_pkr), 0) AS revenue\n"
            "FROM silver_fact\nGROUP BY city\nORDER BY revenue DESC;",
        )

        sql_input = st.text_area(
            "SQL Query",
            value=default_sql,
            height=220,
            key="sql_text_area",
            label_visibility="collapsed",
            help="DuckDB SQL — supports window functions, CTEs, lateral joins, and more",
        )

        # Action buttons
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([1, 1, 1, 3])
        run_btn    = btn_col1.button("▶ Run",    type="primary", use_container_width=True)
        clear_btn  = btn_col2.button("🗑 Clear",                 use_container_width=True)
        example_btn = btn_col3.button("💡 Example",             use_container_width=True)

        if clear_btn:
            st.session_state["sql_editor_content"] = ""
            st.rerun()

        if example_btn:
            st.session_state["sql_editor_content"] = (
                "SELECT city, payment_method,\n"
                "    COUNT(*) AS txns,\n"
                "    ROUND(SUM(fee_pkr), 0) AS revenue\n"
                "FROM silver_fact\n"
                "GROUP BY city, payment_method\n"
                "ORDER BY revenue DESC\nLIMIT 20;"
            )
            st.rerun()

        # ── Execute ────────────────────────────────────────────────────────────
        if run_btn and sql_input.strip():
            sql = sql_input.strip()
            con = get_duckdb_conn()
            t0  = time.time()

            try:
                result_df = con.execute(sql).df()
                elapsed   = time.time() - t0

                # Store in history
                if "query_history" not in st.session_state:
                    st.session_state["query_history"] = []
                st.session_state["query_history"].append({
                    "sql":  sql,
                    "time": time.strftime("%H:%M:%S"),
                    "rows": len(result_df),
                })

                # Results header
                st.markdown(f"""
                    <div style='background:#E8F5E9; border-radius:6px; padding:8px 14px;
                         border-left:4px solid #2E8B57; margin-bottom:8px;'>
                        ✅ <b>{len(result_df):,} rows</b> returned in
                        <b>{elapsed*1000:.0f}ms</b>
                    </div>
                """, unsafe_allow_html=True)

                # Results table
                st.dataframe(result_df, use_container_width=True, hide_index=True,
                             height=min(500, 40 + len(result_df) * 35))

                # Export button
                if not result_df.empty:
                    csv = result_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇ Download CSV",
                        csv,
                        file_name=f"query_result_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        key=f"dl_{time.strftime('%H%M%S')}",
                    )

            except Exception as e:
                elapsed = time.time() - t0
                st.error(f"**SQL Error** ({elapsed*1000:.0f}ms)\n\n```\n{e}\n```")

        elif run_btn:
            st.warning("Enter a SQL query first.")

        # ── Query reference card ───────────────────────────────────────────────
        with st.expander("📖 Available Views & Columns", expanded=False):
            views = {
                "silver_fact": [
                    "transaction_id", "location_id", "vehicle_id", "customer_id",
                    "entry_time", "exit_time", "duration_minutes", "fee_pkr",
                    "payment_method", "vehicle_type", "entry_date", "entry_hour",
                    "day_of_week", "entry_month", "entry_year", "city", "province",
                    "neighborhood", "zone_type", "total_slots", "plate_number",
                    "is_blacklisted", "has_season_pass", "is_ramadan", "is_eid",
                    "is_monsoon", "is_weekend", "is_anomaly", "anomaly_score",
                ],
                "gold_location_performance": [
                    "location_id", "location_name", "city", "province",
                    "total_revenue_pkr", "total_transactions", "avg_fee_pkr",
                    "avg_duration_minutes", "violation_count", "daily_utilisation_rate",
                ],
                "gold_customer_rfm": [
                    "customer_id", "full_name", "customer_city", "gender", "age",
                    "recency_days", "frequency", "monetary_pkr", "avg_spend_pkr",
                    "has_season_pass", "most_used_payment", "most_used_vehicle_type",
                ],
                "gold_monthly_trends": [
                    "city", "year", "month", "total_revenue_pkr",
                    "transaction_count", "mom_revenue_growth_pct",
                ],
                "silver_violations": [
                    "violation_id", "transaction_id", "location_id", "vehicle_id",
                    "violation_type", "violation_time", "fine_pkr", "fine_paid", "resolved",
                ],
                "silver_anpr": [
                    "anpr_event_id", "location_id", "vehicle_id", "camera_id",
                    "event_type", "scan_time", "confidence_score", "is_blacklisted_hit", "plate_number",
                ],
                "sensor_events": [
                    "sensor_event_id", "slot_id", "location_id", "status", "timestamp",
                ],
            }
            for view, cols in views.items():
                st.markdown(f"**`{view}`**: {', '.join(f'`{c}`' for c in cols)}")
