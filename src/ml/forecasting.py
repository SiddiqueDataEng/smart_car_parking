"""
ML Model 1 — Occupancy & Revenue Forecasting with Prophet
==========================================================
Trains one Prophet model per location for 30-day revenue/occupancy forecasts.
Serialises models and saves forecast plots.

Run:  python -m src.ml.forecasting
"""
import time
import warnings
from pathlib import Path

import joblib
import pandas as pd
import numpy as np
import plotly.graph_objects as go

warnings.filterwarnings("ignore")

from src.catalog.logger import get_logger

log = get_logger("ml.forecasting")
_ROOT = Path(__file__).resolve().parents[2]
_MODELS = _ROOT / "src" / "ml" / "models"
_OUT    = _ROOT / "notebooks" / "outputs"


def _load_features() -> pd.DataFrame:
    path = _ROOT / "data" / "platinum" / "features_forecast.parquet"
    df = pd.read_parquet(path)
    df["ds"] = pd.to_datetime(df["ds"])
    return df


def _mape(actual: pd.Series, predicted: pd.Series) -> float:
    mask = actual != 0
    return float(np.mean(np.abs((actual[mask] - predicted[mask]) / actual[mask])) * 100)


def train_prophet_for_location(
    df_loc: pd.DataFrame,
    metric: str = "revenue_pkr",
    horizon_days: int = 30,
) -> dict:
    """Train Prophet (or fallback linear trend) on a single location's time series."""
    df_loc = df_loc.sort_values("ds").copy()

    # Need at least 2 * horizon rows
    if len(df_loc) < max(60, horizon_days * 2):
        return {}

    # Temporal split — last `horizon_days` as test
    cutoff  = df_loc["ds"].max() - pd.Timedelta(days=horizon_days)
    train   = df_loc[df_loc["ds"] <= cutoff].rename(columns={metric: "y"})
    test    = df_loc[df_loc["ds"] >  cutoff].rename(columns={metric: "y"})

    if len(train) < 30 or len(test) < 5:
        return {}

    # ── Try Prophet ────────────────────────────────────────────────
    try:
        from prophet import Prophet

        regressors = [
            "is_ramadan", "is_eid", "is_monsoon",
            "is_public_holiday", "is_independence_day",
        ]

        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10,
        )
        for r in regressors:
            if r in train.columns:
                model.add_regressor(r)

        model.fit(train[["ds", "y"] + [r for r in regressors if r in train.columns]])

        future = model.make_future_dataframe(periods=horizon_days)
        for r in regressors:
            if r in df_loc.columns:
                reg_map = df_loc.set_index("ds")[r].to_dict()
                future[r] = future["ds"].map(reg_map).fillna(0).astype(int)

        forecast = model.predict(future)

    # ── Fallback: sklearn linear trend ────────────────────────────
    except (ImportError, Exception) as prophet_err:
        if "not installed" not in str(prophet_err) and "No module" not in str(prophet_err):
            log.warning("Prophet failed (%s), using linear fallback", prophet_err)
        from sklearn.linear_model import Ridge
        from sklearn.preprocessing import StandardScaler

        train_copy = train.copy()
        train_copy["t"] = np.arange(len(train_copy))
        train_copy["dow_sin"] = np.sin(2 * np.pi * train_copy["ds"].dt.dayofweek / 7)
        train_copy["dow_cos"] = np.cos(2 * np.pi * train_copy["ds"].dt.dayofweek / 7)
        train_copy["month_sin"] = np.sin(2 * np.pi * train_copy["ds"].dt.month / 12)
        train_copy["month_cos"] = np.cos(2 * np.pi * train_copy["ds"].dt.month / 12)

        feat_cols = ["t", "dow_sin", "dow_cos", "month_sin", "month_cos"]
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(train_copy[feat_cols].values)
        y_tr = train_copy["y"].values

        lr = Ridge(alpha=1.0)
        lr.fit(X_tr, y_tr)

        # Build future dates
        last_date = df_loc["ds"].max()
        future_dates = pd.date_range(
            df_loc["ds"].min(),
            last_date + pd.Timedelta(days=horizon_days),
            freq="D",
        )
        n = len(future_dates)
        future_feat = np.column_stack([
            np.arange(n),
            np.sin(2 * np.pi * future_dates.dayofweek / 7),
            np.cos(2 * np.pi * future_dates.dayofweek / 7),
            np.sin(2 * np.pi * future_dates.month / 12),
            np.cos(2 * np.pi * future_dates.month / 12),
        ])
        X_fut = scaler.transform(future_feat)
        yhat  = lr.predict(X_fut).clip(0)
        std   = y_tr.std()

        forecast = pd.DataFrame({
            "ds":         future_dates,
            "yhat":       yhat,
            "yhat_lower": (yhat - 1.96 * std).clip(0),
            "yhat_upper": yhat + 1.96 * std,
        })
        model = lr  # Save the fallback model

    # MAPE on test period
    test_pred = forecast[forecast["ds"].isin(test["ds"])]["yhat"]
    test_actual = test["y"].values
    mape = _mape(pd.Series(test_actual), pd.Series(test_pred.values)) if len(test_pred) > 0 else None

    return {
        "model":    model,
        "forecast": forecast,
        "mape":     mape,
        "train_rows": len(train),
        "test_rows":  len(test),
    }


def run():
    t0 = time.time()
    log.info("=" * 60)
    log.info("ML — Revenue Forecasting (Prophet)")
    log.info("=" * 60)

    _MODELS.mkdir(parents=True, exist_ok=True)
    _OUT.mkdir(parents=True, exist_ok=True)

    df = _load_features()
    locations = df["location_id"].unique()
    log.info("Training Prophet on %d locations...", len(locations))

    results = []
    trained = 0
    failed  = 0

    for loc_id in locations:
        df_loc = df[df["location_id"] == loc_id].copy()
        res = train_prophet_for_location(df_loc, metric="revenue_pkr")
        if not res:
            failed += 1
            continue

        # Save model
        model_path = _MODELS / f"prophet_{loc_id}.pkl"
        joblib.dump(res["model"], model_path)

        # Save forecast CSV
        fc = res["forecast"][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        fc.to_csv(_OUT / f"forecast_{loc_id}.csv", index=False)

        results.append({
            "location_id": loc_id,
            "mape":        res["mape"],
            "train_rows":  res["train_rows"],
        })
        trained += 1
        if trained % 10 == 0:
            mapes = [r["mape"] for r in results if r["mape"] is not None]
            log.info("  Trained %d/%d | Avg MAPE: %.1f%%",
                     trained, len(locations), np.mean(mapes) if mapes else 0)

    # ── Summary plot for top location ────────────────────────────────────────
    if results:
        best = min(results, key=lambda x: x["mape"] or 999)
        loc_id = best["location_id"]
        forecast_csv = pd.read_csv(_OUT / f"forecast_{loc_id}.csv", parse_dates=["ds"])
        df_loc = df[df["location_id"] == loc_id].sort_values("ds")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_loc["ds"], y=df_loc["revenue_pkr"],
            name="Actual Revenue (PKR)", line=dict(color="#2E8B57")
        ))
        fig.add_trace(go.Scatter(
            x=forecast_csv["ds"], y=forecast_csv["yhat"],
            name="Forecast", line=dict(color="#FF6B35", dash="dash")
        ))
        fig.add_trace(go.Scatter(
            x=pd.concat([forecast_csv["ds"], forecast_csv["ds"][::-1]]),
            y=pd.concat([forecast_csv["yhat_upper"], forecast_csv["yhat_lower"][::-1]]),
            fill="toself", fillcolor="rgba(255,107,53,0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="95% CI"
        ))
        fig.update_layout(
            title=f"Revenue Forecast — {loc_id} | MAPE: {best['mape']:.1f}%",
            xaxis_title="Date", yaxis_title="Revenue (PKR)",
            template="plotly_white", height=450,
        )
        fig.write_html(_OUT / "forecast_best_location.html")

    # ── Metrics log ───────────────────────────────────────────────────────────
    mapes = [r["mape"] for r in results if r["mape"] is not None]
    avg_mape = np.mean(mapes) if mapes else 0

    metrics_path = _ROOT / "logs" / "ml_runs.log"
    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(f"\n[forecasting] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  locations_trained={trained}\n")
        f.write(f"  locations_failed={failed}\n")
        f.write(f"  avg_mape={avg_mape:.2f}%\n")
        f.write(f"  min_mape={min(mapes):.2f}% max_mape={max(mapes):.2f}%\n" if mapes else "")

    elapsed = time.time() - t0
    log.info("=" * 60)
    log.info("Forecasting complete — %d models trained in %.1f s", trained, elapsed)
    log.info("Avg MAPE: %.1f%% | Min MAPE: %.1f%%", avg_mape, min(mapes) if mapes else 0)
    log.info("=" * 60)
    print(f"\nForecasting: {trained} models | Avg MAPE: {avg_mape:.1f}%")

    return {"trained": trained, "avg_mape": avg_mape, "results": results}


if __name__ == "__main__":
    run()
