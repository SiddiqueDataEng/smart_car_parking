"""
Centralised data loading with caching for the Streamlit dashboard.
All pages import from here — avoids re-reading Parquet on every interaction.
"""
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
import streamlit as st

_ROOT = Path(__file__).resolve().parents[1]


def _p(layer: str, name: str) -> str:
    """Return a Parquet path as a string for DuckDB read_parquet()."""
    return str(_ROOT / "data" / layer / f"{name}.parquet")


# ── DuckDB connection (shared in-memory) ─────────────────────────────────────

@st.cache_resource
def get_duckdb_conn() -> duckdb.DuckDBPyConnection:
    """
    Create a persistent DuckDB in-memory connection with all layers
    registered as views.
    """
    con = duckdb.connect(":memory:")

    # Bronze views
    for t in ["locations", "vehicles", "customers",
              "parking_transactions", "violations", "anpr_events",
              "sensor_events", "staff_shifts"]:
        p = _ROOT / "data" / "bronze" / f"{t}.parquet"
        if p.exists():
            con.execute(
                f"CREATE OR REPLACE VIEW bronze_{t.replace('parking_', '')} "
                f"AS SELECT * FROM read_parquet('{p}')"
            )

    # Alias for query library compatibility
    con.execute(
        f"CREATE OR REPLACE VIEW bronze_transactions "
        f"AS SELECT * FROM read_parquet('{_ROOT / 'data' / 'bronze' / 'parking_transactions.parquet'}')"
    )

    # Silver views
    for t in ["fact", "locations", "vehicles", "customers",
              "violations", "anpr", "staff"]:
        p = _ROOT / "data" / "silver" / f"silver_{t}.parquet"
        if p.exists():
            con.execute(
                f"CREATE OR REPLACE VIEW silver_{t} "
                f"AS SELECT * FROM read_parquet('{p}')"
            )

    # Gold views
    for t in ["daily_revenue", "hourly_occupancy", "peak_analysis",
              "location_performance", "customer_rfm",
              "violation_summary", "monthly_trends"]:
        p = _ROOT / "data" / "gold" / f"gold_{t}.parquet"
        if p.exists():
            con.execute(
                f"CREATE OR REPLACE VIEW gold_{t} "
                f"AS SELECT * FROM read_parquet('{p}')"
            )

    # Platinum views
    for t in ["forecast", "classification", "clustering", "anomaly", "pricing"]:
        p = _ROOT / "data" / "platinum" / f"features_{t}.parquet"
        if p.exists():
            con.execute(
                f"CREATE OR REPLACE VIEW platinum_{t} "
                f"AS SELECT * FROM read_parquet('{p}')"
            )

    # Catalog view
    import json
    cat_path = _ROOT / "data" / "catalog.json"
    if cat_path.exists():
        with open(cat_path) as f:
            catalog = json.load(f)
        rows = [
            {
                "name": v["name"], "layer": v["layer"],
                "row_count": v["row_count"], "last_updated": v["last_updated"],
                "file_path": v["file_path"],
            }
            for v in catalog.values()
        ]
        if rows:
            cat_df = pd.DataFrame(rows)
            con.register("catalog_view", cat_df)

    # Sensor events (separate because large)
    p = _ROOT / "data" / "bronze" / "sensor_events.parquet"
    if p.exists():
        con.execute(f"CREATE OR REPLACE VIEW sensor_events AS SELECT * FROM read_parquet('{p}')")

    return con


# ── Cached dataframe loaders ──────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_silver_fact() -> pd.DataFrame:
    return pd.read_parquet(_ROOT / "data" / "silver" / "silver_fact.parquet")


@st.cache_data(ttl=3600)
def load_locations() -> pd.DataFrame:
    return pd.read_parquet(_ROOT / "data" / "silver" / "silver_locations.parquet")


@st.cache_data(ttl=3600)
def load_gold(table: str) -> pd.DataFrame:
    path = _ROOT / "data" / "gold" / f"gold_{table}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_platinum(table: str) -> pd.DataFrame:
    path = _ROOT / "data" / "platinum" / f"features_{table}.parquet"
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_ml_model(name: str):
    import joblib
    path = _ROOT / "src" / "ml" / "models" / f"{name}.pkl"
    if path.exists():
        return joblib.load(path)
    return None


@st.cache_data(ttl=3600)
def load_ml_metrics() -> dict:
    """Parse ml_runs.log into a structured metrics dict."""
    log_path = _ROOT / "logs" / "ml_runs.log"
    metrics: dict = {}
    if not log_path.exists():
        return metrics

    current_model = None
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("[") and "]" in line:
                current_model = line[1:line.index("]")]
                metrics[current_model] = {}
            elif "=" in line and current_model:
                k, v = line.split("=", 1)
                try:
                    metrics[current_model][k.strip()] = float(v.strip().replace("%", ""))
                except ValueError:
                    metrics[current_model][k.strip()] = v.strip()
    return metrics


def query(sql: str) -> pd.DataFrame:
    """Execute a SQL query against the shared DuckDB connection."""
    con = get_duckdb_conn()
    return con.execute(sql).df()
