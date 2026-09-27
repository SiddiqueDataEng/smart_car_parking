# 🅿 SMART Parking Solutions
### A Production-Grade Data Portfolio Project — Pakistan

![Python](https://img.shields.io/badge/Python-3.11-blue)
![DuckDB](https://img.shields.io/badge/DuckDB-1.0-yellow)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35-red)
![Pandas](https://img.shields.io/badge/Pandas-2.2-green)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.5-orange)
![Prophet](https://img.shields.io/badge/Prophet-1.1-blue)
![XGBoost](https://img.shields.io/badge/XGBoost-2.0-orange)

---

## Project Overview

A complete, end-to-end **Data Analytics + Machine Learning portfolio project** simulating a smart car parking management system for the Pakistani market. Built to demonstrate skills across the full data stack — from data engineering to ML to business dashboarding.

**Inspired by:** [makan.sa](https://www.makan.sa/), [smartparkings.com.pk](https://smartparkings.com.pk), [makkays.com](https://makkays.com/Home/ParkingManagement)

### What's Inside

| Component | Description |
|-----------|-------------|
| 🏭 Data Generator | 598K hyper-realistic transactions across 10 Pakistani cities |
| 🥉 Bronze Layer | Raw Parquet files (8 tables, 40 MB) |
| 🥈 Silver Layer | Cleaned, deduplicated, enriched (DuckDB transforms) |
| 🥇 Gold Layer | 7 aggregated KPI tables (revenue, occupancy, RFM, etc.) |
| 💎 Platinum Layer | 5 ML feature stores (forecast, anomaly, pricing, etc.) |
| 🤖 ML Models | 6 models: Prophet, Random Forest, XGBoost, K-Means, Isolation Forest, GBR |
| 📊 Dashboard | 4-role Streamlit app with 20+ pages |
| 🔍 SQL Editor | 50+ prebuilt analytical queries + free-form runner |
| 📓 EDA Notebooks | 3 storytelling notebooks with business narrative |

---

## Architecture

```
flowchart TD
    A[🏭 Data Generator\nFaker + Custom Seasonality] -->|Raw Parquet| B[🥉 Bronze Layer\nDuckDB + Parquet]
    B -->|Clean + Normalize| C[🥈 Silver Layer\nTyped, Deduped, PKT timestamps]
    C -->|Aggregate KPIs| D[🥇 Gold Layer\nRevenue · Occupancy · RFM · Violations]
    D -->|Feature Engineering| E[💎 Platinum Layer\nML Feature Store]
    E --> F[🤖 ML Models\nForecast · Classify · Cluster · Anomaly · Price]
    F --> G[📊 Streamlit Dashboard\n4 Roles + SQL Editor]
    C --> G
    D --> G
    H[📓 EDA Notebooks\n3 Storytelling Notebooks] --> C & D
    I[🗂️ Data Catalog\nLineage DAG] --> B & C & D & E
    J[✅ Quality Checks\n11 checks on Silver] --> C
```

---

## Data Model

### Bronze Layer (raw)
| Table | Rows | Description |
|-------|------|-------------|
| `locations.parquet` | 52 | Parking locations in 10 cities |
| `vehicles.parquet` | 30,000 | Pakistani vehicles (ABC-1234 plates) |
| `customers.parquet` | 15,000 | Customer profiles (CNIC, 03xx phones) |
| `parking_transactions.parquet` | 598,244 | 2 years of transactions |
| `anpr_events.parquet` | 668,158 | ANPR plate scan logs |
| `sensor_events.parquet` | 310,157 | Slot occupancy sensor pings |
| `violations.parquet` | 11,965 | Parking violations |
| `staff_shifts.parquet` | 65,110 | Staff scheduling records |

### Pakistan Seasonality Baked In
- 🌙 **Ramadan** — reduced daytime, +150% Iftar surge (6–8pm)
- 🎉 **Eid-ul-Fitr & Eid-ul-Adha** — +120% volume uplift
- 🇵🇰 **Independence Day** — Aug 14 surge
- 🕌 **Jummah** — Friday 12–2pm dip
- 🌧 **Monsoon** — Jul–Sep -25% volume
- 🏙 **Real cities** — Karachi (30%), Lahore (25%), Islamabad (15%), +7 more

---

## ML Models

| Model | Algorithm | Key Metric |
|-------|-----------|------------|
| Revenue Forecast | Prophet | Avg MAPE ~5% |
| Violation Classifier | Random Forest | F1 ~0.85, AUC ~0.90 |
| Churn Predictor | XGBoost | AUC ~0.85 |
| Customer Segmentation | K-Means (k=5) | Silhouette ~0.4 |
| Anomaly Detection | Isolation Forest | Flag rate ~3% |
| Dynamic Pricing | Gradient Boosting | RMSE ~5 PKR, R² ~0.999 |

---

## Dashboard Roles

| Role | Pages | Access |
|------|-------|--------|
| **Super Admin** | KPI Overview, Revenue Analytics, Forecast, Anomaly Alerts, Data Catalog, SQL Editor | Full |
| **Location Manager** | Slot Occupancy Grid, Staff Shifts, Revenue Gauge, Violations Log | Operational |
| **Data Analyst** | EDA Explorer, ML Metrics, Segmentation, Pricing Simulator, SQL Editor | Analytics |
| **Customer** | Find Parking, My History, Season Pass, My Violations, Loyalty Score | Self-service |

---

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Generate Data & Run Full Pipeline
```bash
python run_pipeline.py
```

*Or step by step:*
```bash
python -m src.generator.generate_all      # ~3 min
python -m src.pipeline.bronze_to_silver   # ~30 sec
python -m src.pipeline.silver_to_gold     # ~10 sec
python -m src.pipeline.gold_to_platinum   # ~15 sec
python -m src.ml.run_all_models           # ~5-10 min (Prophet + GBR)
```

### 3. Launch Dashboard
```bash
streamlit run dashboard/app.py
```

Open **http://localhost:8501**

### Demo Credentials
| Role | Username | Password |
|------|----------|----------|
| Super Admin | `superadmin` | `admin123` |
| Location Manager | `manager` | `manager123` |
| Data Analyst | `analyst` | `analyst123` |
| Customer | `customer` | `customer123` |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Data Generation | Python, custom seasonality engine |
| Storage | Apache Parquet (PyArrow) |
| Query Engine | DuckDB 1.0 |
| Pipeline | Python scripts + DuckDB SQL |
| Quality Checks | Custom module (Great Expectations style) |
| Forecasting | Prophet 1.1 |
| ML | scikit-learn 1.5, XGBoost 2.0 |
| Visualisation | Plotly 5, Seaborn |
| Dashboard | Streamlit 1.35 |
| Configuration | PyYAML |
| Notebooks | Jupyter |

---

## Project Structure

```
smart_car_parking/
├── config/
│   ├── config.yaml          # All settings
│   └── users.yaml           # Dashboard user accounts
├── data/
│   ├── bronze/              # Raw Parquet (8 files, 40 MB)
│   ├── silver/              # Cleaned Parquet (7 files)
│   ├── gold/                # KPI aggregates (7 files)
│   ├── platinum/            # ML feature stores (5 files)
│   ├── catalog.json         # Data catalog
│   └── lineage.json         # Lineage DAG
├── src/
│   ├── generator/           # Data generation modules
│   ├── pipeline/            # ETL transforms
│   ├── quality/             # Quality gate module
│   ├── ml/                  # 6 ML models + runner
│   └── catalog/             # Catalog + logger
├── dashboard/
│   ├── app.py               # Streamlit entry point
│   ├── auth.py              # Login + session management
│   ├── data_loader.py       # Cached data loading
│   ├── query_library.py     # 50+ SQL queries
│   └── pages/               # Role-specific pages
├── notebooks/
│   ├── 01_EDA_Operations.ipynb
│   ├── 02_EDA_Revenue.ipynb
│   └── 03_EDA_Customer.ipynb
├── logs/
│   ├── pipeline.log         # Pipeline run logs
│   └── ml_runs.log          # ML training metrics
├── run_pipeline.py          # One-command pipeline runner
└── requirements.txt
```

---

## Data Dictionary

See [docs/data_dictionary.md](docs/data_dictionary.md) for full column-level documentation.

---

## Portfolio Notes

This project demonstrates:
- **Data Engineering**: Medallion architecture with DuckDB + Parquet
- **Data Quality**: Automated quality gates (11 checks on Silver layer)
- **Analytics SQL**: 50+ production-grade analytical queries
- **ML Engineering**: 6 models with temporal train/test splits, serialisation, metric logging
- **Pakistan Context**: Real cities, authentic plate formats, PKR currency, local holidays
- **Storytelling**: EDA notebooks written as business presentations
- **Software Engineering**: Modular repo, config-driven, logged, catalog-tracked

---

*Built with ❤️ for the Pakistani parking industry and the data analytics job market.*
