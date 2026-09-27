"""
ML Model 4 — Customer Segmentation (K-Means Clustering)
========================================================
Segments customers using RFM + behavioral features.
Produces named cluster labels and saves silhouette + elbow plots.

Run:  python -m src.ml.clustering
"""
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

from src.catalog.logger import get_logger

log = get_logger("ml.clustering")
_ROOT   = Path(__file__).resolve().parents[2]
_MODELS = _ROOT / "src" / "ml" / "models"
_OUT    = _ROOT / "notebooks" / "outputs"

FEATURE_COLS = [
    "recency_score", "frequency_score", "monetary_score",
    "avg_spend_pkr", "avg_duration_bucket", "locations_visited",
    "payment_enc", "vehicle_enc", "gender_enc", "has_season_pass_enc",
]

# Qualitative cluster names — assigned by inspecting centroid order
CLUSTER_NAMES = {
    0: "Casual Visitors",
    1: "Loyal Regulars",
    2: "High-Value Corporates",
    3: "Occasional Spenders",
    4: "Season Pass Holders",
}


def run() -> dict:
    t0 = time.time()
    log.info("=" * 60)
    log.info("ML — Customer Segmentation (K-Means)")
    log.info("=" * 60)

    _MODELS.mkdir(parents=True, exist_ok=True)
    _OUT.mkdir(parents=True, exist_ok=True)

    feat_path = _ROOT / "data" / "platinum" / "features_clustering.parquet"
    if not feat_path.exists():
        log.error("features_clustering.parquet not found")
        return {}

    df = pd.read_parquet(feat_path)
    feat_cols = [c for c in FEATURE_COLS if c in df.columns]
    df = df.dropna(subset=feat_cols)

    X = df[feat_cols].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── Elbow + Silhouette to pick K ─────────────────────────────────────────
    max_k = min(10, len(df) // 100)
    inertias    = []
    silhouettes = []
    k_range     = range(2, max_k + 1)

    log.info("Running elbow method (k=2..%d)...", max_k)
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        sil = silhouette_score(X_scaled, labels, sample_size=min(5000, len(X_scaled)))
        silhouettes.append(sil)
        log.info("  k=%d | inertia=%.0f | silhouette=%.4f", k, km.inertia_, sil)

    # Elbow plot
    fig_elbow = go.Figure()
    fig_elbow.add_trace(go.Scatter(x=list(k_range), y=inertias,
                                   mode="lines+markers", name="Inertia",
                                   line=dict(color="#2E8B57")))
    fig_elbow.update_layout(
        title="K-Means Elbow Plot — Customer Segmentation",
        xaxis_title="Number of Clusters (k)",
        yaxis_title="Inertia",
        template="plotly_white",
    )
    fig_elbow.write_html(_OUT / "clustering_elbow.html")

    # Pick best k by highest silhouette
    best_k = list(k_range)[int(np.argmax(silhouettes))]
    best_sil = max(silhouettes)
    # Clamp to 5 for named labels
    final_k = min(best_k, 5)
    log.info("Best k by silhouette: %d (score=%.4f) → using k=%d", best_k, best_sil, final_k)

    # ── Final model ───────────────────────────────────────────────────────────
    final_km = KMeans(n_clusters=final_k, random_state=42, n_init=10)
    df["cluster_id"]   = final_km.fit_predict(X_scaled)
    df["cluster_name"] = df["cluster_id"].map(CLUSTER_NAMES).fillna(
        df["cluster_id"].apply(lambda x: f"Segment {x}")
    )

    # Validate: no cluster has < 1% of customers
    cluster_pcts = df["cluster_id"].value_counts(normalize=True)
    min_pct = cluster_pcts.min()
    log.info("Cluster distribution:\n%s", cluster_pcts.to_string())
    if min_pct < 0.01:
        log.warning("Smallest cluster has only %.1f%% of customers", 100 * min_pct)
    else:
        log.info("✓ All clusters ≥ 1%% (min: %.1f%%)", 100 * min_pct)

    final_sil = silhouette_score(
        X_scaled, df["cluster_id"], sample_size=min(5000, len(X_scaled))
    )

    # ── Scatter visualisation (PCA 2D) ────────────────────────────────────────
    from sklearn.decomposition import PCA
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(X_scaled)
    df["pca_x"] = coords[:, 0]
    df["pca_y"] = coords[:, 1]

    scatter_df = df[["pca_x", "pca_y", "cluster_name",
                      "monetary_pkr", "frequency", "recency_days"]].copy()
    scatter_df["monetary_pkr"] = scatter_df["monetary_pkr"].round(0)

    fig_scatter = px.scatter(
        scatter_df.sample(min(3000, len(scatter_df)), random_state=42),
        x="pca_x", y="pca_y",
        color="cluster_name",
        hover_data=["monetary_pkr", "frequency", "recency_days"],
        title=f"Customer Segmentation (k={final_k}, Silhouette={final_sil:.3f})",
        template="plotly_white",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_scatter.write_html(_OUT / "clustering_scatter.html")

    # ── RFM heatmap per cluster ────────────────────────────────────────────────
    cluster_summary = (
        df.groupby("cluster_name")[["recency_days", "frequency", "monetary_pkr"]]
        .mean()
        .round(1)
        .reset_index()
    )
    log.info("Cluster summary:\n%s", cluster_summary.to_string(index=False))

    # Save enriched feature table
    df.to_parquet(feat_path, index=False)
    log.info("Updated features_clustering.parquet with cluster labels")

    # Save model + scaler
    model_path = _MODELS / "customer_clustering.pkl"
    joblib.dump({
        "model":    final_km,
        "scaler":   scaler,
        "features": feat_cols,
        "k":        final_k,
        "cluster_names": CLUSTER_NAMES,
        "pca":      pca,
    }, model_path)
    log.info("Model saved → %s", model_path)

    elapsed = time.time() - t0

    # Log metrics
    metrics_path = _ROOT / "logs" / "ml_runs.log"
    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(f"\n[clustering] {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  k={final_k}\n")
        f.write(f"  silhouette_score={final_sil:.4f}\n")
        f.write(f"  min_cluster_pct={min_pct:.4f}\n")
        for name, pct in cluster_pcts.items():
            label = CLUSTER_NAMES.get(name, f"Segment {name}")
            f.write(f"  cluster_{name}_{label}={pct:.3f}\n")

    log.info("Clustering complete in %.1f s | k=%d | Silhouette=%.4f",
             elapsed, final_k, final_sil)
    print(f"\n✅  Clustering: k={final_k} | Silhouette={final_sil:.4f}")
    print(f"   Segments: {list(cluster_pcts.index.map(CLUSTER_NAMES.get))}")
    print(cluster_summary.to_string(index=False))

    return {
        "k": final_k,
        "silhouette": final_sil,
        "cluster_summary": cluster_summary.to_dict(),
    }


if __name__ == "__main__":
    run()
