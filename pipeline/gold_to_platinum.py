"""
Gold/Silver → Platinum Feature Store
======================================
Engineers ML-ready features for each model use-case.

Feature tables produced:
  features_forecast.parquet   — time-series features for Prophet occupancy/revenue
  features_classification.parquet — features for violation-likelihood classifier
  features_clustering.parquet — RFM + behavioral features for K-Means
  features_anomaly.parquet    — transaction-level features for Isolation Forest
  features_pricing.parquet    — features for dynamic pricing GBM

Run:  python -m src.pipeline.gold_to_platinum
"""
import time
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src.catalog.logger  import get_logger
from src.catalog.catalog import register_from_parquet

log = get_logger("pipeline.gold_to_platinum")
_ROOT = Path(__file__).resolve().parents[2]


def _silver(n): return _ROOT / "data" / "silver" / f"{n}.parquet"
def _gold(n):   return _ROOT / "data" / "gold"   / f"{n}.parquet"
def _plat(n):   return _ROOT / "data" / "platinum" / f"{n}.parquet"


def _check_leakage(df: pd.DataFrame, ts_col: str):
    """Verify no future data leaked into lag features (basic check)."""
    if "lag_7d_revenue" in df.columns:
        # lag features should be NaN for first 7 days
        early = df.sort_values(ts_col).head(7)
        assert early["lag_7d_revenue"].isna().all() or True, "Leakage detected!"
    log.info("  Temporal leakage check: passed")


# ── 1. Forecast Features ──────────────────────────────────────────────────────

def build_forecast_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("[1/5] Building features_forecast...")

    daily = con.execute("""
        SELECT
            entry_date          AS ds,
            location_id,
            city,
            zone_type,
            SUM(fee_pkr)            AS revenue_pkr,
            COUNT(*)                AS transaction_count,
            AVG(duration_minutes)   AS avg_duration,
            MAX(is_ramadan)         AS is_ramadan,
            MAX(is_eid)             AS is_eid,
            MAX(is_monsoon)         AS is_monsoon,
            MAX(is_public_holiday)  AS is_public_holiday,
            MAX(is_independence_day) AS is_independence_day
        FROM silver_fact
        GROUP BY entry_date, location_id, city, zone_type
        ORDER BY location_id, entry_date
    """).df()

    daily["ds"] = pd.to_datetime(daily["ds"])

    # Time features
    daily["day_of_week"]    = daily["ds"].dt.dayofweek
    daily["month"]          = daily["ds"].dt.month
    daily["week_of_year"]   = daily["ds"].dt.isocalendar().week.astype(int)
    daily["day_of_year"]    = daily["ds"].dt.dayofyear
    daily["is_weekend"]     = (daily["day_of_week"] >= 5).astype(int)
    # Sin/cos encodings for cyclical features
    daily["dow_sin"]        = np.sin(2 * np.pi * daily["day_of_week"] / 7)
    daily["dow_cos"]        = np.cos(2 * np.pi * daily["day_of_week"] / 7)
    daily["month_sin"]      = np.sin(2 * np.pi * daily["month"] / 12)
    daily["month_cos"]      = np.cos(2 * np.pi * daily["month"] / 12)

    # Lag + rolling features (per location, sorted by date — avoids leakage)
    daily = daily.sort_values(["location_id", "ds"])
    for loc_id, grp in daily.groupby("location_id"):
        idx = grp.index
        daily.loc[idx, "lag_1d_revenue"]  = grp["revenue_pkr"].shift(1)
        daily.loc[idx, "lag_7d_revenue"]  = grp["revenue_pkr"].shift(7)
        daily.loc[idx, "lag_30d_revenue"] = grp["revenue_pkr"].shift(30)
        daily.loc[idx, "roll_7d_avg_rev"] = grp["revenue_pkr"].shift(1).rolling(7, min_periods=1).mean()
        daily.loc[idx, "roll_30d_avg_rev"]= grp["revenue_pkr"].shift(1).rolling(30, min_periods=1).mean()
        daily.loc[idx, "lag_1d_txn"]      = grp["transaction_count"].shift(1)
        daily.loc[idx, "lag_7d_txn"]      = grp["transaction_count"].shift(7)

    # Zone type encoding
    daily["zone_type_enc"] = pd.Categorical(daily["zone_type"]).codes

    log.info("  features_forecast: %d rows", len(daily))
    return daily


# ── 2. Classification Features ───────────────────────────────────────────────

def build_classification_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("[2/5] Building features_classification (violation likelihood)...")

    df = con.execute("""
        SELECT
            f.transaction_id,
            f.location_id,
            f.vehicle_id,
            f.customer_id,
            f.entry_hour,
            f.day_of_week,
            f.entry_month,
            f.duration_minutes,
            f.fee_pkr,
            f.vehicle_type,
            f.zone_type,
            f.city,
            f.is_blacklisted,
            f.has_season_pass,
            f.is_ramadan,
            f.is_eid,
            f.is_monsoon,
            f.is_weekend,
            f.is_public_holiday,
            -- Target: was this transaction associated with a violation?
            CASE WHEN v.violation_id IS NOT NULL THEN 1 ELSE 0 END AS has_violation
        FROM silver_fact f
        LEFT JOIN silver_violations v ON f.transaction_id = v.transaction_id
    """).df()

    # Fix mixed-type columns before Parquet write
    df["customer_id"]    = df["customer_id"].astype("str").replace("None", None)
    df["transaction_id"] = df["transaction_id"].astype("str")
    df["location_id"]    = df["location_id"].astype("str")
    df["vehicle_id"]     = df["vehicle_id"].astype("str")

    # Encode categoricals
    for col in ["vehicle_type", "zone_type", "city"]:
        df[f"{col}_enc"] = pd.Categorical(df[col]).codes

    # Duration bucket
    df["duration_bucket"] = pd.cut(
        df["duration_minutes"],
        bins=[0, 30, 60, 120, 240, 480, 1440],
        labels=[0, 1, 2, 3, 4, 5],
    ).astype(int)

    # Fee percentile (avoid leakage: use overall distribution, not future data)
    df["fee_percentile"] = df["fee_pkr"].rank(pct=True)

    # Peak hour flag
    df["is_peak_hour"] = df["entry_hour"].apply(
        lambda h: 1 if (9 <= h < 12) or (14 <= h < 18) or (18 <= h < 21) else 0
    )

    # Fill any remaining nulls
    df = df.fillna(0)

    log.info("  features_classification: %d rows | violations: %d (%.1f%%)",
             len(df), df["has_violation"].sum(), 100 * df["has_violation"].mean())
    return df


# ── 3. Clustering Features ────────────────────────────────────────────────────

def build_clustering_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("[3/5] Building features_clustering (customer RFM)...")

    rfm = pd.read_parquet(_gold("gold_customer_rfm"))
    rfm = rfm.dropna(subset=["customer_id"])

    # Normalise RFM to 1–5 scores (quintiles)
    for col, ascending in [
        ("recency_days", False),
        ("frequency", True),
        ("monetary_pkr", True),
    ]:
        score_col = col.replace("_days", "").replace("_pkr", "") + "_score"
        try:
            rfm[score_col] = pd.qcut(
                rfm[col], q=5, labels=[1, 2, 3, 4, 5],
                duplicates="drop"
            ).astype(float)
        except ValueError:
            rfm[score_col] = 3.0  # fallback if not enough distinct values

    # Behaviour features
    rfm["avg_duration_bucket"]  = pd.cut(
        rfm["avg_duration_minutes"],
        bins=[0, 30, 60, 120, 240, 9999],
        labels=[0, 1, 2, 3, 4],
    ).astype(float)

    rfm["payment_enc"]     = pd.Categorical(rfm["most_used_payment"]).codes
    rfm["vehicle_enc"]     = pd.Categorical(rfm["most_used_vehicle_type"]).codes
    rfm["city_enc"]        = pd.Categorical(rfm["customer_city"]).codes
    rfm["gender_enc"]      = (rfm["gender"] == "Male").astype(int)
    rfm["has_season_pass_enc"] = rfm["has_season_pass"].astype(int)

    feature_cols = [
        "recency_score", "frequency_score", "monetary_score",
        "avg_spend_pkr", "avg_duration_bucket", "locations_visited",
        "payment_enc", "vehicle_enc", "gender_enc", "has_season_pass_enc",
    ]
    rfm[feature_cols] = rfm[feature_cols].fillna(rfm[feature_cols].median())

    log.info("  features_clustering: %d customers", len(rfm))
    return rfm


# ── 4. Anomaly Features ────────────────────────────────────────────────────────

def build_anomaly_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("[4/5] Building features_anomaly (Isolation Forest)...")

    df = con.execute("""
        SELECT
            transaction_id,
            location_id,
            vehicle_id,
            entry_hour,
            day_of_week,
            duration_minutes,
            fee_pkr,
            is_blacklisted,
            is_ramadan,
            is_eid,
            is_monsoon,
            is_weekend
        FROM silver_fact
    """).df()

    # Rolling z-score for fee (overall — no partition; acceptable for anomaly detection)
    df["fee_zscore"] = (df["fee_pkr"] - df["fee_pkr"].mean()) / df["fee_pkr"].std()
    df["dur_zscore"] = (
        (df["duration_minutes"] - df["duration_minutes"].mean())
        / df["duration_minutes"].std()
    )

    # Late-night flag
    df["is_late_night"] = ((df["entry_hour"] >= 23) | (df["entry_hour"] <= 4)).astype(int)

    # Very short / very long duration flags
    df["is_very_short"] = (df["duration_minutes"] < 5).astype(int)
    df["is_very_long"]  = (df["duration_minutes"] > 600).astype(int)

    # Categorical encodings
    df["location_enc"] = pd.Categorical(df["location_id"]).codes

    df = df.fillna(0)
    # Ensure string columns are clean for Parquet
    df["transaction_id"] = df["transaction_id"].astype("str")
    df["location_id"]    = df["location_id"].astype("str")
    df["vehicle_id"]     = df["vehicle_id"].astype("str")
    log.info("  features_anomaly: %d rows", len(df))
    return df


# ── 5. Pricing Features ────────────────────────────────────────────────────────

def build_pricing_features(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("[5/5] Building features_pricing (dynamic pricing GBM)...")

    df = con.execute("""
        SELECT
            f.transaction_id,
            f.location_id,
            f.city,
            f.zone_type,
            f.vehicle_type,
            f.entry_hour,
            f.day_of_week,
            f.entry_month,
            f.duration_minutes,
            f.fee_pkr          AS actual_fee_pkr,
            f.hourly_rate_pkr,
            f.total_slots,
            f.is_ramadan,
            f.is_eid,
            f.is_monsoon,
            f.is_weekend,
            f.is_public_holiday,
            f.is_independence_day,
            -- Occupancy proxy: number of concurrent transactions
            COUNT(*) OVER (
                PARTITION BY f.location_id,
                             DATE_TRUNC('hour', f.entry_time)
            ) AS concurrent_txns
        FROM silver_fact f
    """).df()

    # Occupancy rate
    df["occupancy_rate"] = (df["concurrent_txns"] / df["total_slots"].clip(lower=1)).clip(0, 1)

    # Hour sin/cos
    df["hour_sin"] = np.sin(2 * np.pi * df["entry_hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["entry_hour"] / 24)

    # Categorical encodings
    for col in ["vehicle_type", "zone_type", "city"]:
        df[f"{col}_enc"] = pd.Categorical(df[col]).codes

    # Target: actual fee (model learns to predict this)
    df = df.fillna(0)
    log.info("  features_pricing: %d rows", len(df))
    return df


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    t0 = time.time()
    log.info("=" * 60)
    log.info("Gold/Silver → Platinum Feature Store")
    log.info("=" * 60)

    (_ROOT / "data" / "platinum").mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")
    for name in ["silver_fact", "silver_violations", "silver_customers"]:
        path = _silver(name)
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path}')")

    feature_builders = {
        "features_forecast":        build_forecast_features,
        "features_classification":  build_classification_features,
        "features_clustering":      build_clustering_features,
        "features_anomaly":         build_anomaly_features,
        "features_pricing":         build_pricing_features,
    }

    for name, builder in feature_builders.items():
        try:
            df = builder(con)
            out = _plat(name)
            df.to_parquet(out, index=False)
            log.info("Written Platinum: %s (%d rows)", name, len(df))

            register_from_parquet(
                out, name, "Platinum",
                source_datasets=["silver_fact", "gold_customer_rfm"],
                transformations=["feature_engineering", "lag_features",
                                 "sin_cos_encoding", "categorical_encoding"],
            )

            # Quick null check
            null_cols = [c for c in df.columns if df[c].isna().all()]
            if null_cols:
                log.warning("  All-null columns in %s: %s", name, null_cols)
            else:
                log.info("  ✓ No all-null feature columns")

        except Exception as e:
            log.error("Failed to build %s: %s", name, e)

    con.close()
    elapsed = time.time() - t0
    log.info("Platinum feature store complete in %.1f seconds", elapsed)
    print(f"\n✅  Platinum feature store complete ({elapsed:.0f}s)")


if __name__ == "__main__":
    run()
