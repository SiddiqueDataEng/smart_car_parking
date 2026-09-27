"""
ML Model 5 — Anomaly Detection (Isolation Forest)
==================================================
Flags unusual parking transactions:
  - Suspiciously short / long durations
  - Unusual fee amounts
  - Off-hours access
  - Blacklisted vehicle patterns

Writes anomaly scores back to Silver layer.

Run:  python -m src.ml.anomaly
"""
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

from src.catalog.logger import get_logger

log = get_logger("ml.anomaly")
_ROOT   = Path(__file__).resolve().parents[2]
_MODELS = _ROOT / "src" / "ml" / "models"
_OUT    = _ROOT / "notebooks" / "outputs"

FEATURE_COLS = [
    "entry_hour", "day_of_week", "duration_minutes",
    "fee_pkr", "fee_zscore", "dur_zscore",
    "is_late_night", "is_very_short", "is_very_long",
    "is_blacklisted", "is_ramadan", "is_monsoon", "is_weekend",
    "location_enc",
]


def run() -> dict:
    t0 = time.time()
    log.info("=" * 60)
    log.info("ML — Anomaly Detection (Isolation Forest)")
    log.info("=" * 60)

    _MODELS.mkdir(parents=True, exist_ok=True)
    _OUT.mkdir(parents=True, exist_ok=True)

    feat_path = _ROOT / "data" / "platinum" / "features_anomaly.parquet"
    if not feat_path.exists():
        log.error("features_anomaly.parquet not found")
        return {}

    df = pd.read_parquet(feat_path)
    feat_cols = [c for c in FEATURE_COLS if c in df.columns]
    df = df.dropna(subset=feat_cols)

    X = df[feat_cols].values

    scaler  = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── Train Isolation Forest ─────────────────────────────────────────────────
    contamination = 0.03  # expect ~3% anomalies
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    preds        = model.fit_predict(X_scaled)   # -1=anomaly, 1=normal
    scores       = model.score_samples(X_scaled) # lower = more anomalous

    df["anomaly_score"] = scores
    df["is_anomaly"]    = (preds == -1).astype(int)

    flag_rate = df["is_anomaly"].mean()
    log.info(
        "Anomaly detection: %d flagged / %d total (%.2f%%)",
        df["is_anomaly"].sum(), len(df), 100 * flag_rate,
    )

    # Validate flag rate 1–5%
    if 0.01 <= flag_rate <= 0.05:
        log.info("✓ Flag rate %.2f%% within expected range [1%%, 5%%]", 100 * flag_rate)
    else:
        log.warning("⚠ Flag rate %.2f%% outside expected range", 100 * flag_rate)

    # ── Write anomaly scores back to Silver fact table ─────────────────────────
    silver_path = _ROOT / "data" / "silver" / "silver_fact.parquet"
    silver_df   = pd.read_parquet(silver_path)

    anomaly_map = df.set_index("transaction_id")[["anomaly_score", "is_anomaly"]]
    silver_df = silver_df.join(anomaly_map, on="transaction_id", how="left")
    silver_df["anomaly_score"] = silver_df["anomaly_score"].fillna(0.0)
    silver_df["is_anomaly"]    = silver_df["is_anomaly"].fillna(0).astype(int)

    silver_df.to_parquet(silver_path, index=False)
    log.info("Anomaly scores written back to silver_fact.parquet")

    # ── Top anomalies table ────────────────────────────────────────────────────
    top_anomalies = (
        df[df["is_anomaly"] == 1]
        .sort_values("anomaly_score")
        .head(20)[[
            "transaction_id", "entry_hour", "duration_minutes",
            "fee_pkr", "is_blacklisted", "is_late_night",
            "is_very_short", "is_very_long", "anomaly_score",
        ]]
    )
    log.info("Top 10 anomalies:\n%s", top_anomalies.head(10).to_string(index=False))

    # ── Scatter: fee vs duration with anomaly highlighted ─────────────────────
    plot_df = df.sample(min(5000, len(df)), random_state=42).copy()
    plot_df["type"] = plot_df["is_anomaly"].map({1: "Anomaly", 0: "Normal"})

    fig = px.scatter(
        plot_df, x="duration_minutes", y="fee_pkr",
        color="type",
        color_discrete_map={"Normal": "#2E8B57", "Anomaly": "#FF4444"},
        opacity=0.6,
        title=f"Anomaly Detection — Fee vs Duration (flagged: {flag_rate:.1%})",
        labels={"duration_minutes": "Duration (min)", "fee_pkr": "Fee (PKR)"},
        template="plotly_white",
    )
    fig.write_html(_OUT / "anomaly_scatter.html")

    # Hour-of-day anomaly distribution
    hourly = df.groupby("entry_hour")["is_anomaly"].mean().reset_index()
    fig2 = px.bar(
        hourly, x="entry_hour", y="is_anomaly",
        title="Anomaly Rate by Hour of Day",
        labels={"is_anomaly": "Anomaly Rate", "entry_hour": "Hour"},
        color="is_anomaly", color_continuous_scale="Reds",
        template="plotly_white",
    )
    fig2.write_html(_OUT / "anomaly_by_hour.html")

    # ── Save model ────────────────────────────────────────────────────────────
    model_path = _MODELS / "anomaly_detector.pkl"
    joblib.dump({"model": model, "scaler": scaler, "features": feat_cols}, model_path)
    log.info("Model saved → %s", model_path)

    elapsed = time.time() - t0

    # Log metrics
    metrics_path = _ROOT / "logs" / "ml_runs.log"
    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(f"\n[anomaly] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  total_transactions={len(df)}\n")
        f.write(f"  flagged={df['is_anomaly'].sum()}\n")
        f.write(f"  flag_rate={flag_rate:.4f}\n")
        f.write(f"  contamination_param={contamination}\n")

    log.info("Anomaly detection complete in %.1f s", elapsed)
    print(f"\n✅  Anomaly Detection: {df['is_anomaly'].sum()} flagged ({flag_rate:.1%})")
    print(f"   Scores written to silver_fact.parquet")

    return {
        "flagged":   int(df["is_anomaly"].sum()),
        "flag_rate": float(flag_rate),
        "total":     len(df),
    }


if __name__ == "__main__":
    run()
