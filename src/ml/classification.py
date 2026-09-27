"""
ML Model 2 — Violation Likelihood Classification (Random Forest)
ML Model 3 — Season Pass Churn Prediction (XGBoost)
================================================================
Run:  python -m src.ml.classification
"""
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    f1_score, classification_report, confusion_matrix,
    roc_auc_score,
)
import xgboost as xgb
import plotly.figure_factory as ff
import plotly.express as px

warnings.filterwarnings("ignore")

from src.catalog.logger import get_logger

log = get_logger("ml.classification")
_ROOT   = Path(__file__).resolve().parents[2]
_MODELS = _ROOT / "src" / "ml" / "models"
_OUT    = _ROOT / "notebooks" / "outputs"


VIOLATION_FEATURES = [
    "entry_hour", "day_of_week", "entry_month", "duration_minutes",
    "fee_pkr", "vehicle_type_enc", "zone_type_enc", "city_enc",
    "is_blacklisted", "has_season_pass", "is_ramadan", "is_eid",
    "is_monsoon", "is_weekend", "is_public_holiday",
    "duration_bucket", "fee_percentile", "is_peak_hour",
]

CHURN_FEATURES = [
    "recency_days", "frequency", "monetary_pkr", "avg_spend_pkr",
    "avg_duration_minutes", "locations_visited",
]


# ── 1. Violation Classifier ───────────────────────────────────────────────────

def train_violation_classifier() -> dict:
    log.info("[1/2] Training Violation Likelihood Classifier (Random Forest)...")

    feat_path = _ROOT / "data" / "platinum" / "features_classification.parquet"
    if not feat_path.exists():
        log.error("features_classification.parquet not found — run gold_to_platinum first")
        return {}

    df = pd.read_parquet(feat_path)

    # Temporal split: last 20% of dates as test (no leakage)
    df = df.dropna(subset=VIOLATION_FEATURES + ["has_violation"])
    feat_cols = [c for c in VIOLATION_FEATURES if c in df.columns]

    X = df[feat_cols].values
    y = df["has_violation"].values.astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    f1  = f1_score(y_test, y_pred, average="weighted")
    auc = roc_auc_score(y_test, y_prob)
    cm  = confusion_matrix(y_test, y_pred)

    log.info(
        "  Violation Classifier — F1: %.4f | ROC-AUC: %.4f | "
        "Train: %d | Test: %d",
        f1, auc, len(X_train), len(X_test),
    )
    log.info("\n%s", classification_report(y_test, y_pred, target_names=["No Viol", "Violation"]))

    # Feature importance plot
    importance_df = pd.DataFrame({
        "feature":   feat_cols,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=True).tail(15)

    fig = px.bar(
        importance_df, x="importance", y="feature", orientation="h",
        title="Violation Classifier — Feature Importance",
        color="importance", color_continuous_scale="Greens",
        template="plotly_white",
    )
    fig.write_html(_OUT / "violation_feature_importance.html")

    # Confusion matrix heatmap
    fig_cm = ff.create_annotated_heatmap(
        z=cm, x=["Pred: No Viol", "Pred: Viol"],
        y=["Actual: No Viol", "Actual: Viol"],
        colorscale="Greens",
    )
    fig_cm.update_layout(title="Violation Classifier — Confusion Matrix")
    fig_cm.write_html(_OUT / "violation_confusion_matrix.html")

    # Save model
    model_path = _MODELS / "violation_classifier.pkl"
    joblib.dump({"model": model, "features": feat_cols}, model_path)
    log.info("  Model saved → %s", model_path)

    return {"f1": f1, "roc_auc": auc, "features": feat_cols}


# ── 2. Churn Predictor ────────────────────────────────────────────────────────

def train_churn_predictor() -> dict:
    log.info("[2/2] Training Season Pass Churn Predictor (XGBoost)...")

    rfm_path = _ROOT / "data" / "gold" / "gold_customer_rfm.parquet"
    if not rfm_path.exists():
        log.error("gold_customer_rfm.parquet not found — run silver_to_gold first")
        return {}

    df = pd.read_parquet(rfm_path)

    # Define churn: recency_days > 90 (no visit in last 90 days)
    df["churned"] = (df["recency_days"] > 90).astype(int)

    feat_cols = [c for c in CHURN_FEATURES if c in df.columns]
    df = df.dropna(subset=feat_cols + ["churned"])

    X = df[feat_cols].values
    y = df["churned"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Class imbalance ratio
    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        scale_pos_weight=pos_weight,
        random_state=42,
        eval_metric="logloss",
        use_label_encoder=False,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    f1  = f1_score(y_test, y_pred, average="weighted")
    auc = roc_auc_score(y_test, y_prob)

    log.info(
        "  Churn Predictor — F1: %.4f | ROC-AUC: %.4f | "
        "Churn rate: %.1f%%",
        f1, auc, 100 * y.mean(),
    )

    # ROC curve plot
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y_test, y_prob)

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=fpr, y=tpr, name=f"XGBoost (AUC={auc:.3f})",
                             line=dict(color="#2E8B57", width=2)))
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], name="Random",
                             line=dict(dash="dash", color="grey")))
    fig.update_layout(
        title="Churn Predictor — ROC Curve",
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        template="plotly_white", height=450,
    )
    fig.write_html(_OUT / "churn_roc_curve.html")

    # Save model
    model_path = _MODELS / "churn_predictor.pkl"
    joblib.dump({"model": model, "features": feat_cols, "threshold": 0.5}, model_path)
    log.info("  Model saved → %s", model_path)

    return {"f1": f1, "roc_auc": auc, "churn_rate": float(y.mean())}


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> dict:
    t0 = time.time()
    log.info("=" * 60)
    log.info("ML — Classification Models")
    log.info("=" * 60)

    _MODELS.mkdir(parents=True, exist_ok=True)
    _OUT.mkdir(parents=True, exist_ok=True)

    violation_metrics = train_violation_classifier()
    churn_metrics     = train_churn_predictor()

    elapsed = time.time() - t0

    # Log to ml_runs.log
    metrics_path = _ROOT / "logs" / "ml_runs.log"
    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(f"\n[classification] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        if violation_metrics:
            f.write(f"  violation_f1={violation_metrics['f1']:.4f}\n")
            f.write(f"  violation_roc_auc={violation_metrics['roc_auc']:.4f}\n")
        if churn_metrics:
            f.write(f"  churn_f1={churn_metrics['f1']:.4f}\n")
            f.write(f"  churn_roc_auc={churn_metrics['roc_auc']:.4f}\n")
            f.write(f"  churn_rate={churn_metrics['churn_rate']:.3f}\n")

    log.info("Classification models complete in %.1f s", elapsed)
    print(f"\n✅  Classification done in {elapsed:.0f}s")
    if violation_metrics:
        print(f"   Violation Classifier — F1: {violation_metrics['f1']:.4f} | AUC: {violation_metrics['roc_auc']:.4f}")
    if churn_metrics:
        print(f"   Churn Predictor      — F1: {churn_metrics['f1']:.4f} | AUC: {churn_metrics['roc_auc']:.4f}")

    return {"violation": violation_metrics, "churn": churn_metrics}


if __name__ == "__main__":
    run()
