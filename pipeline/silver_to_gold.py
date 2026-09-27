"""
Silver → Gold Pipeline
======================
Aggregates Silver fact data into Gold KPI tables using DuckDB SQL.

Tables produced:
  gold_daily_revenue        — revenue by location, date, payment method, vehicle type
  gold_hourly_occupancy     — occupancy proxy by location, hour, day-of-week
  gold_peak_analysis        — top peak hours with seasonality overlays
  gold_location_performance — KPIs per location: revenue, utilisation, violations
  gold_customer_rfm         — RFM base table per customer
  gold_violation_summary    — violations aggregated by type, location, time
  gold_monthly_trends       — MoM revenue + occupancy trends per city

Run:  python -m src.pipeline.silver_to_gold
"""
import time
from pathlib import Path

import duckdb
import pandas as pd

from src.catalog.logger  import get_logger
from src.catalog.catalog import register_from_parquet

log = get_logger("pipeline.silver_to_gold")
_ROOT = Path(__file__).resolve().parents[2]


def _silver(name: str) -> Path:
    return _ROOT / "data" / "silver" / f"{name}.parquet"


def _gold(name: str) -> Path:
    return _ROOT / "data" / "gold" / f"{name}.parquet"


def run():
    t0 = time.time()
    log.info("=" * 60)
    log.info("Silver → Gold Pipeline")
    log.info("=" * 60)

    gold_dir = _ROOT / "data" / "gold"
    gold_dir.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")

    # Register Silver views
    silver_tables = [
        "silver_fact", "silver_locations", "silver_vehicles",
        "silver_customers", "silver_violations",
    ]
    for t in silver_tables:
        path = _silver(t)
        con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{path}')")
        log.info("Registered Silver view: %s", t)

    # ── 1. Daily Revenue ──────────────────────────────────────────────────────
    log.info("[1/7] Building gold_daily_revenue...")
    daily_rev = con.execute("""
        SELECT
            entry_date                          AS date,
            location_id,
            city,
            province,
            zone_type,
            payment_method,
            vehicle_type,
            COUNT(*)                            AS transaction_count,
            SUM(fee_pkr)                        AS total_revenue_pkr,
            AVG(fee_pkr)                        AS avg_fee_pkr,
            SUM(duration_minutes)               AS total_duration_minutes,
            AVG(duration_minutes)               AS avg_duration_minutes,
            -- Seasonality flags (majority vote)
            MAX(is_ramadan)                     AS is_ramadan,
            MAX(is_eid)                         AS is_eid,
            MAX(is_monsoon)                     AS is_monsoon,
            MAX(is_public_holiday)              AS is_public_holiday,
            MAX(is_independence_day)            AS is_independence_day
        FROM silver_fact
        GROUP BY
            entry_date, location_id, city, province, zone_type,
            payment_method, vehicle_type
        ORDER BY entry_date, location_id
    """).df()
    daily_rev.to_parquet(_gold("gold_daily_revenue"), index=False)
    log.info("  gold_daily_revenue: %d rows", len(daily_rev))

    # ── 2. Hourly Occupancy ───────────────────────────────────────────────────
    log.info("[2/7] Building gold_hourly_occupancy...")
    hourly_occ = con.execute("""
        SELECT
            location_id,
            city,
            zone_type,
            CAST(entry_hour AS INTEGER)         AS hour_of_day,
            CAST(day_of_week AS INTEGER)        AS day_of_week,
            entry_month                         AS month,
            COUNT(*)                            AS transaction_count,
            SUM(duration_minutes)               AS total_duration_minutes,
            AVG(duration_minutes)               AS avg_duration_minutes,
            AVG(fee_pkr)                        AS avg_fee_pkr,
            SUM(fee_pkr)                        AS total_revenue_pkr,
            -- Proxy occupancy rate = transactions / (total_slots * 1 hour capacity assumed)
            COUNT(*) * 1.0 / MAX(total_slots)   AS occupancy_rate_proxy
        FROM silver_fact
        GROUP BY
            location_id, city, zone_type, entry_hour, day_of_week, entry_month
        ORDER BY location_id, hour_of_day
    """).df()
    hourly_occ.to_parquet(_gold("gold_hourly_occupancy"), index=False)
    log.info("  gold_hourly_occupancy: %d rows", len(hourly_occ))

    # ── 3. Peak Analysis ──────────────────────────────────────────────────────
    log.info("[3/7] Building gold_peak_analysis...")
    peak_analysis = con.execute("""
        SELECT
            city,
            CAST(entry_hour  AS INTEGER) AS hour_of_day,
            CAST(day_of_week AS INTEGER) AS day_of_week,
            is_ramadan,
            is_eid,
            is_monsoon,
            is_public_holiday,
            COUNT(*)              AS transaction_count,
            AVG(fee_pkr)          AS avg_fee_pkr,
            SUM(fee_pkr)          AS total_revenue_pkr,
            AVG(duration_minutes) AS avg_duration_minutes,
            -- Rank within city
            ROW_NUMBER() OVER (
                PARTITION BY city
                ORDER BY COUNT(*) DESC
            ) AS peak_rank_in_city
        FROM silver_fact
        GROUP BY
            city, entry_hour, day_of_week,
            is_ramadan, is_eid, is_monsoon, is_public_holiday
        ORDER BY city, transaction_count DESC
    """).df()
    peak_analysis.to_parquet(_gold("gold_peak_analysis"), index=False)
    log.info("  gold_peak_analysis: %d rows", len(peak_analysis))

    # ── 4. Location Performance ───────────────────────────────────────────────
    log.info("[4/7] Building gold_location_performance...")
    loc_perf = con.execute("""
        WITH txn_stats AS (
            SELECT
                f.location_id,
                f.location_name,
                f.city,
                f.province,
                f.neighborhood,
                f.zone_type,
                f.total_slots,
                f.hourly_rate_pkr,
                COUNT(*)                   AS total_transactions,
                SUM(f.fee_pkr)             AS total_revenue_pkr,
                AVG(f.fee_pkr)             AS avg_fee_pkr,
                AVG(f.duration_minutes)    AS avg_duration_minutes,
                COUNT(DISTINCT f.vehicle_id)   AS unique_vehicles,
                COUNT(DISTINCT f.customer_id)  AS unique_customers,
                MIN(f.entry_date)          AS first_transaction_date,
                MAX(f.entry_date)          AS last_transaction_date
            FROM silver_fact f
            GROUP BY
                f.location_id, f.location_name, f.city, f.province,
                f.neighborhood, f.zone_type, f.total_slots, f.hourly_rate_pkr
        ),
        viol_stats AS (
            SELECT
                location_id,
                COUNT(*) AS violation_count,
                SUM(fine_pkr) AS total_fines_pkr
            FROM silver_violations
            GROUP BY location_id
        )
        SELECT
            t.*,
            COALESCE(v.violation_count, 0)  AS violation_count,
            COALESCE(v.total_fines_pkr, 0)  AS total_fines_pkr,
            -- Utilisation proxy: avg transactions per day / total_slots
            t.total_transactions * 1.0
                / GREATEST(
                    DATE_DIFF('day',
                        CAST(t.first_transaction_date AS DATE),
                        CAST(t.last_transaction_date  AS DATE)
                    ), 1
                )
                / GREATEST(t.total_slots, 1) AS daily_utilisation_rate
        FROM txn_stats t
        LEFT JOIN viol_stats v ON t.location_id = v.location_id
        ORDER BY total_revenue_pkr DESC
    """).df()
    loc_perf.to_parquet(_gold("gold_location_performance"), index=False)
    log.info("  gold_location_performance: %d rows", len(loc_perf))

    # ── 5. Customer RFM ───────────────────────────────────────────────────────
    log.info("[5/7] Building gold_customer_rfm...")
    rfm = con.execute("""
        SELECT
            f.customer_id,
            c.full_name,
            c.city          AS customer_city,
            c.gender,
            c.age,
            c.has_season_pass,
            c.preferred_payment,
            -- RFM components
            DATE_DIFF('day',
                MAX(CAST(f.entry_date AS DATE)),
                DATE '2024-12-31'
            )                                   AS recency_days,
            COUNT(*)                            AS frequency,
            SUM(f.fee_pkr)                      AS monetary_pkr,
            AVG(f.fee_pkr)                      AS avg_spend_pkr,
            AVG(f.duration_minutes)             AS avg_duration_minutes,
            COUNT(DISTINCT f.location_id)       AS locations_visited,
            MIN(f.entry_date)                   AS first_visit_date,
            MAX(f.entry_date)                   AS last_visit_date,
            -- Most used payment
            MODE(f.payment_method)              AS most_used_payment,
            MODE(f.vehicle_type)                AS most_used_vehicle_type
        FROM silver_fact f
        JOIN silver_customers c ON f.customer_id = c.customer_id
        WHERE f.customer_id IS NOT NULL
        GROUP BY
            f.customer_id, c.full_name, c.city, c.gender, c.age,
            c.has_season_pass, c.preferred_payment
        ORDER BY monetary_pkr DESC
    """).df()
    rfm.to_parquet(_gold("gold_customer_rfm"), index=False)
    log.info("  gold_customer_rfm: %d rows", len(rfm))

    # ── 6. Violation Summary ──────────────────────────────────────────────────
    log.info("[6/7] Building gold_violation_summary...")
    viol_summary = con.execute("""
        SELECT
            v.violation_type,
            v.location_id,
            f.city,
            f.zone_type,
            EXTRACT(HOUR FROM v.violation_time)  AS violation_hour,
            EXTRACT(DOW  FROM v.violation_time)  AS violation_dow,
            EXTRACT(MONTH FROM v.violation_time) AS violation_month,
            COUNT(*)                             AS violation_count,
            SUM(v.fine_pkr)                      AS total_fines_pkr,
            AVG(v.fine_pkr)                      AS avg_fine_pkr,
            SUM(CASE WHEN v.fine_paid  THEN 1 ELSE 0 END) AS fines_paid_count,
            SUM(CASE WHEN v.resolved   THEN 1 ELSE 0 END) AS resolved_count
        FROM silver_violations v
        LEFT JOIN silver_fact f ON v.transaction_id = f.transaction_id
        GROUP BY
            v.violation_type, v.location_id, f.city, f.zone_type,
            violation_hour, violation_dow, violation_month
        ORDER BY violation_count DESC
    """).df()
    viol_summary.to_parquet(_gold("gold_violation_summary"), index=False)
    log.info("  gold_violation_summary: %d rows", len(viol_summary))

    # ── 7. Monthly Trends ─────────────────────────────────────────────────────
    log.info("[7/7] Building gold_monthly_trends...")
    monthly = con.execute("""
        WITH monthly_base AS (
            SELECT
                city,
                entry_year   AS year,
                entry_month  AS month,
                COUNT(*)                 AS transaction_count,
                SUM(fee_pkr)             AS total_revenue_pkr,
                AVG(fee_pkr)             AS avg_fee_pkr,
                AVG(duration_minutes)    AS avg_duration_minutes,
                COUNT(DISTINCT vehicle_id)   AS unique_vehicles,
                COUNT(DISTINCT customer_id)  AS unique_customers,
                COUNT(DISTINCT location_id)  AS active_locations
            FROM silver_fact
            GROUP BY city, entry_year, entry_month
        ),
        with_prev AS (
            SELECT *,
                LAG(total_revenue_pkr) OVER (
                    PARTITION BY city ORDER BY year, month
                ) AS prev_month_revenue
            FROM monthly_base
        )
        SELECT
            *,
            CASE
                WHEN prev_month_revenue IS NULL OR prev_month_revenue = 0 THEN NULL
                ELSE ROUND(
                    (total_revenue_pkr - prev_month_revenue)
                    / prev_month_revenue * 100,
                    2
                )
            END AS mom_revenue_growth_pct
        FROM with_prev
        ORDER BY city, year, month
    """).df()
    monthly.to_parquet(_gold("gold_monthly_trends"), index=False)
    log.info("  gold_monthly_trends: %d rows", len(monthly))

    # ── Catalog registration ──────────────────────────────────────────────────
    gold_tables = {
        "gold_daily_revenue":        (daily_rev,      ["silver_fact"]),
        "gold_hourly_occupancy":     (hourly_occ,     ["silver_fact"]),
        "gold_peak_analysis":        (peak_analysis,  ["silver_fact"]),
        "gold_location_performance": (loc_perf,       ["silver_fact", "silver_violations"]),
        "gold_customer_rfm":         (rfm,            ["silver_fact", "silver_customers"]),
        "gold_violation_summary":    (viol_summary,   ["silver_violations", "silver_fact"]),
        "gold_monthly_trends":       (monthly,        ["silver_fact"]),
    }

    for name, (df, sources) in gold_tables.items():
        register_from_parquet(
            _gold(name), name, "Gold",
            source_datasets=sources,
            transformations=["aggregate", "join", "kpi_compute"],
        )

    # Reconciliation check: Silver total vs Gold daily total
    silver_total = con.execute(
        "SELECT SUM(fee_pkr) FROM silver_fact"
    ).fetchone()[0]
    gold_total   = daily_rev["total_revenue_pkr"].sum()
    diff_pct     = abs(silver_total - gold_total) / silver_total * 100
    if diff_pct > 0.01:
        log.warning(
            "Revenue reconciliation mismatch: Silver=%.0f vs Gold=%.0f (%.4f%%)",
            silver_total, gold_total, diff_pct,
        )
    else:
        log.info(
            "✓ Revenue reconciliation: Silver ≈ Gold (diff %.6f%%)", diff_pct
        )

    con.close()
    elapsed = time.time() - t0
    log.info("Silver → Gold complete in %.1f seconds", elapsed)
    print(f"\n✅  Silver → Gold complete ({elapsed:.0f}s)")
    print(f"\nTop 5 locations by revenue:")
    print(loc_perf[["location_name", "city", "total_revenue_pkr", "total_transactions"]]
          .head(5).to_string(index=False))


if __name__ == "__main__":
    run()
