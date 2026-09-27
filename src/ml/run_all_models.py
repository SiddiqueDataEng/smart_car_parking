"""
Run all ML models in sequence.
Run:  python -m src.ml.run_all_models
"""
import time
from src.catalog.logger import get_logger

log = get_logger("ml.run_all")


def run():
    t0 = time.time()
    log.info("=" * 60)
    log.info("Running all ML models")
    log.info("=" * 60)

    results = {}

    # 1. Forecasting (Prophet)
    log.info("\n[1/5] Forecasting...")
    try:
        from src.ml.forecasting import run as run_forecast
        results["forecasting"] = run_forecast()
    except Exception as e:
        log.error("Forecasting failed: %s", e)
        results["forecasting"] = {"error": str(e)}

    # 2. Classification + Churn
    log.info("\n[2/5] Classification...")
    try:
        from src.ml.classification import run as run_clf
        results["classification"] = run_clf()
    except Exception as e:
        log.error("Classification failed: %s", e)
        results["classification"] = {"error": str(e)}

    # 3. Clustering
    log.info("\n[3/5] Clustering...")
    try:
        from src.ml.clustering import run as run_clust
        results["clustering"] = run_clust()
    except Exception as e:
        log.error("Clustering failed: %s", e)
        results["clustering"] = {"error": str(e)}

    # 4. Anomaly Detection
    log.info("\n[4/5] Anomaly Detection...")
    try:
        from src.ml.anomaly import run as run_anomaly
        results["anomaly"] = run_anomaly()
    except Exception as e:
        log.error("Anomaly detection failed: %s", e)
        results["anomaly"] = {"error": str(e)}

    # 5. Dynamic Pricing
    log.info("\n[5/5] Dynamic Pricing...")
    try:
        from src.ml.pricing import run as run_price
        results["pricing"] = run_price()
    except Exception as e:
        log.error("Pricing failed: %s", e)
        results["pricing"] = {"error": str(e)}

    elapsed = time.time() - t0
    log.info("=" * 60)
    log.info("All ML models complete in %.1f s", elapsed)
    log.info("=" * 60)
    print(f"\n✅  All ML models done in {elapsed:.0f}s")
    return results


if __name__ == "__main__":
    run()
