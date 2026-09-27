"""
ML Model 6 — Dynamic Pricing Recommender (Gradient Boosting)
=============================================================
Learns optimal PKR fee based on:
  occupancy rate, hour, day-of-week, location, vehicle type, seasonality

Outputs recommended vs actual fee comparison.

Run:  python -m src.ml.pricing
"""
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

from src.catalog.logger import get_logger

log = get_logger("ml.pricing")
_ROOT   = Path(__file__).resolve().parents[2]
_MODELS = _ROOT / "src" / "ml" / "models"
_OUT    = _ROOT / "notebooks" / "outputs"

FEATURE_COLS = [
    "occupancy_rate", "entry_hour", "day_of_week", "entry_month",
    "duration_minutes", "vehicle_type_enc", "zone_type_enc", "city_enc",
    "hourly_rate_pkr", "is_ramadan", "is_eid", "is_monsoon", "is_weekend",
    "is_public_holiday", "is_independence_day",
    "hour_sin", "hour_cos",
]


def run() -> dict:
    t0 = time.time()
    log.info("=" * 60)
    log.info("ML — Dynamic Pricing (Gradient Boosting)")
    log.info("=" * 60)

    _MODELS.mkdir(parents=True, exist_ok=True)
    _OUT.mkdir(parents=True, exist_ok=True)

    feat_path = _ROOT / "data" / "platinum" / "features_pricing.parquet"
    if not feat_path.exists():
        log.error("features_pricing.parquet not found")
        return {}

    df = pd.read_parquet(feat_path)
    feat_cols = [c for c in FEATURE_COLS if c in df.columns]
    df = df.dropna(subset=feat_cols + ["actual_fee_pkr"])

    # Remove extreme outliers (top 1% fee)
    q99 = df["actual_fee_pkr"].quantile(0.99)
    df  = df[df["actual_fee_pkr"] <= q99]

    X = df[feat_cols].values
    y = df["actual_fee_pkr"].values

    # Temporal split: use last 20% of data as test
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    log.info("Training GBR on %d samples (test: %d)...", len(X_train), len(X_test))

    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    rmse   = np.sqrt(mean_squared_error(y_test, y_pred))
    r2     = r2_score(y_test, y_pred)
    mape   = np.mean(np.abs((y_test - y_pred) / np.where(y_test == 0, 1, y_test))) * 100

    log.info(
        "Pricing Model — RMSE: %.2f PKR | R²: %.4f | MAPE: %.2f%%",
        rmse, r2, mape,
    )

    # ── Feature importance ────────────────────────────────────────────────────
    imp_df = pd.DataFrame({
        "feature":    feat_cols,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=True).tail(12)

    fig_imp = px.bar(
        imp_df, x="importance", y="feature", orientation="h",
        title="Dynamic Pricing — Feature Importance",
        color="importance", color_continuous_scale="Greens",
        template="plotly_white",
    )
    fig_imp.write_html(_OUT / "pricing_feature_importance.html")

    # ── Predicted vs Actual scatter ────────────────────────────────────────────
    sample_n = min(2000, len(y_test))
    idx = np.random.choice(len(y_test), sample_n, replace=False)

    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=y_test[idx], y=y_pred[idx],
        mode="markers", opacity=0.5,
        marker=dict(color="#2E8B57", size=5),
        name="Predictions",
    ))
    max_val = max(y_test[idx].max(), y_pred[idx].max())
    fig_scatter.add_trace(go.Scatter(
        x=[0, max_val], y=[0, max_val],
        mode="lines", line=dict(dash="dash", color="red"),
        name="Perfect Fit",
    ))
    fig_scatter.update_layout(
        title=f"Dynamic Pricing — Predicted vs Actual (RMSE={rmse:.0f} PKR, R²={r2:.3f})",
        xaxis_title="Actual Fee (PKR)",
        yaxis_title="Predicted Fee (PKR)",
        template="plotly_white",
    )
    fig_scatter.write_html(_OUT / "pricing_pred_vs_actual.html")

    # ── 10 sample pricing scenarios ───────────────────────────────────────────
    scenarios = pd.DataFrame([
        {"occupancy_rate": 0.9, "entry_hour": 18, "day_of_week": 0, "entry_month": 4,
         "duration_minutes": 60, "vehicle_type_enc": 0, "zone_type_enc": 0, "city_enc": 0,
         "hourly_rate_pkr": 60, "is_ramadan": 1, "is_eid": 0, "is_monsoon": 0,
         "is_weekend": 0, "is_public_holiday": 0, "is_independence_day": 0,
         "hour_sin": np.sin(2*np.pi*18/24), "hour_cos": np.cos(2*np.pi*18/24),
         "scenario": "Ramadan Iftar (90% occ)"},
        {"occupancy_rate": 0.3, "entry_hour": 10, "day_of_week": 1, "entry_month": 2,
         "duration_minutes": 45, "vehicle_type_enc": 1, "zone_type_enc": 1, "city_enc": 1,
         "hourly_rate_pkr": 50, "is_ramadan": 0, "is_eid": 0, "is_monsoon": 0,
         "is_weekend": 0, "is_public_holiday": 0, "is_independence_day": 0,
         "hour_sin": np.sin(2*np.pi*10/24), "hour_cos": np.cos(2*np.pi*10/24),
         "scenario": "Weekday Morning (30% occ)"},
        {"occupancy_rate": 1.0, "entry_hour": 20, "day_of_week": 5, "entry_month": 8,
         "duration_minutes": 120, "vehicle_type_enc": 2, "zone_type_enc": 0, "city_enc": 0,
         "hourly_rate_pkr": 80, "is_ramadan": 0, "is_eid": 1, "is_monsoon": 1,
         "is_weekend": 1, "is_public_holiday": 0, "is_independence_day": 0,
         "hour_sin": np.sin(2*np.pi*20/24), "hour_cos": np.cos(2*np.pi*20/24),
         "scenario": "Eid Saturday Night (100% occ)"},
    ])

    scen_feat = [c for c in feat_cols if c in scenarios.columns]
    scenarios["recommended_pkr"] = model.predict(scenarios[scen_feat].values).round(0)
    log.info("Sample pricing scenarios:\n%s",
             scenarios[["scenario", "occupancy_rate", "entry_hour", "recommended_pkr"]].to_string())

    # ── Save model ────────────────────────────────────────────────────────────
    model_path = _MODELS / "dynamic_pricing.pkl"
    joblib.dump({"model": model, "features": feat_cols, "rmse": rmse, "r2": r2},
                model_path)
    log.info("Model saved → %s", model_path)

    elapsed = time.time() - t0

    # Log metrics
    metrics_path = _ROOT / "logs" / "ml_runs.log"
    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(f"\n[pricing] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  rmse={rmse:.2f}\n")
        f.write(f"  r2={r2:.4f}\n")
        f.write(f"  mape={mape:.2f}%\n")
        f.write(f"  train_rows={len(X_train)}\n")
        f.write(f"  test_rows={len(X_test)}\n")

    log.info("Dynamic pricing complete in %.1f s", elapsed)
    print(f"\n✅  Dynamic Pricing — RMSE: {rmse:.0f} PKR | R²: {r2:.3f} | MAPE: {mape:.1f}%")

    return {"rmse": float(rmse), "r2": float(r2), "mape": float(mape)}


if __name__ == "__main__":
    run()
