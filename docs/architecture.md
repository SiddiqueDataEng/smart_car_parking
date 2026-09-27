# Architecture — SMART Parking Solutions

## Overview

The system uses a **Medallion (Multi-Hop) Architecture** built on DuckDB + Apache Parquet, running locally with zero-server infrastructure. This demonstrates a real lakehouse pattern without requiring cloud resources — ideal for a portfolio project.

```
Raw Generation → Bronze → Silver → Gold → Platinum → ML → Dashboard
```

---

## Layer Design Decisions

### 🥉 Bronze Layer — Raw As-Is
- **What:** Exact output of the data generator, no transformations
- **Why:** Preserves raw state for replay, debugging, and schema evolution
- **Format:** Parquet (columnar, compressed, fast scan)
- **Engine:** Written by Python generators directly via PyArrow

### 🥈 Silver Layer — Cleaned & Normalised
- **What:** Type-cast, deduplicated, enriched with joins and Pakistan seasonality flags
- **Why:** Single source of truth for all analytical queries; bad data filtered here
- **Key transforms:** Timestamp normalisation to PKT (UTC+5), plate standardisation, duration derivation, seasonality flag injection, Silver fact denormalisation
- **Quality Gate:** 11 automated checks (null rates, duplicates, range assertions, referential integrity)
- **Engine:** DuckDB SQL over Bronze Parquet views

### 🥇 Gold Layer — Business KPIs
- **What:** 7 aggregated tables ready for direct dashboard consumption
- **Why:** Pre-aggregation avoids re-computing GROUP BY on 600K rows on every dashboard load
- **Tables:** daily_revenue, hourly_occupancy, peak_analysis, location_performance, customer_rfm, violation_summary, monthly_trends
- **Engine:** DuckDB SQL window functions, CTEs

### 💎 Platinum Layer — ML Feature Store
- **What:** 5 purpose-built feature tables, one per ML use case
- **Why:** Separates feature engineering from model training; avoids leakage via temporal ordering
- **Anti-leakage:** Lag features only use data prior to each row's timestamp; test splits enforce temporal boundaries
- **Tables:** features_forecast, features_classification, features_clustering, features_anomaly, features_pricing

---

## ML Architecture

| Model | Algorithm | Training Strategy | Metric |
|-------|-----------|-------------------|--------|
| Revenue Forecast | Prophet | Per-location, temporal split (last 30 days = test) | MAPE |
| Violation Classifier | Random Forest | Stratified 80/20 split | F1 + ROC-AUC |
| Churn Predictor | XGBoost | Stratified 80/20 split | ROC-AUC |
| Customer Segmentation | K-Means | Elbow + Silhouette to pick k | Silhouette |
| Anomaly Detection | Isolation Forest | Unsupervised, contamination=3% | Flag rate |
| Dynamic Pricing | Gradient Boosting | Temporal 80/20 split | RMSE + R² |

All models serialised with `joblib` to `src/ml/models/`. Metrics logged to `logs/ml_runs.log`.

---

## Dashboard Architecture

```
streamlit run dashboard/app.py
       ↓
   auth.py (login + session state)
       ↓
   app.py (role-based routing)
       ↓
 ┌─────────────────────────────────────┐
 │ pages/super_admin.py                │
 │ pages/location_manager.py           │
 │ pages/data_analyst.py               │
 │ pages/customer.py                   │
 │ pages/sql_editor.py                 │
 └─────────────────────────────────────┘
       ↓
 data_loader.py (cached DuckDB + Parquet reads)
       ↓
 DuckDB views over all Parquet layers
```

**Session state** stores: `logged_in`, `role`, `user`, `query_history`

**Caching:** `@st.cache_data(ttl=3600)` on all Parquet reads; `@st.cache_resource` on the DuckDB connection.

---

## Data Catalog & Lineage

`data/catalog.json` — registry of all 26 datasets with schema, row count, last updated, and source lineage.

`data/lineage.json` — DAG mapping each dataset to its source inputs:

```
locations, vehicles, customers, parking_transactions → silver_fact
silver_fact + silver_violations → gold_location_performance
silver_fact + silver_customers  → gold_customer_rfm
silver_fact                     → features_forecast
features_forecast               → (Prophet models)
```

---

## Configuration-Driven Design

All tuneable parameters live in `config/config.yaml`:
- Cities, weights, neighborhoods
- Vehicle types and base rates
- Date range and transaction volume targets
- Seasonality dates (Ramadan, Eid, monsoon months)
- ML hyperparameters
- Dashboard theme

This means the entire dataset can be regenerated for a different city, time period, or volume by editing one file.
