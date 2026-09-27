"""
Bronze → Silver Pipeline
========================
Cleans, normalises and enriches raw Bronze data using DuckDB + pandas.

Steps:
  1. Load Bronze Parquet files via DuckDB views
  2. Deduplicate transactions
  3. Standardise plate formats → uppercase, no extra spaces
  4. Parse timestamps → UTC+5 (PKT)
  5. Derive duration_minutes and recalculated fee_pkr
  6. Denormalise: join transactions ← locations, vehicles, customers
  7. Enrich is_season_pass flag, plate_number, seasonality flags
  8. Run quality gate
  9. Write Silver Parquet files
 10. Register in catalog + log lineage

Run:  python -m src.pipeline.bronze_to_silver
"""
import time
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from src.catalog.logger    import get_logger
from src.catalog.catalog   import register_from_parquet
from src.quality.quality_checks import QualityGate
from src.generator.seasonality  import get_season_flags

log = get_logger("pipeline.bronze_to_silver")
_ROOT = Path(__file__).resolve().parents[2]


def _bronze(name: str) -> Path:
    return _ROOT / "data" / "bronze" / f"{name}.parquet"


def _silver(name: str) -> Path:
    return _ROOT / "data" / "silver" / f"{name}.parquet"


def load_config():
    with open(_ROOT / "config" / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Individual transform functions ────────────────────────────────────────────

def clean_locations(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("Cleaning locations...")
    df = con.execute("""
        SELECT
            location_id,
            UPPER(TRIM(location_name))  AS location_name,
            city,
            province,
            neighborhood,
            zone_type,
            CAST(total_slots  AS INTEGER) AS total_slots,
            CAST(floors       AS INTEGER) AS floors,
            has_anpr,
            has_ev_charging,
            has_valet,
            is_covered,
            CAST(hourly_rate_pkr    AS DOUBLE) AS hourly_rate_pkr,
            CAST(monthly_pass_pkr   AS DOUBLE) AS monthly_pass_pkr,
            latitude,
            longitude,
            opening_hour,
            closing_hour,
            CAST(created_at AS DATE) AS created_at
        FROM bronze_locations
        WHERE location_id IS NOT NULL
    """).df()
    log.info("  Locations: %d rows", len(df))
    return df


def clean_vehicles(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("Cleaning vehicles...")
    df = con.execute("""
        SELECT
            vehicle_id,
            UPPER(REGEXP_REPLACE(plate_number, '\\s+', '')) AS plate_number,
            vehicle_type,
            color,
            make_year,
            is_blacklisted,
            base_rate_pkr,
            registered_city
        FROM bronze_vehicles
        WHERE vehicle_id IS NOT NULL
          AND plate_number IS NOT NULL
    """).df()
    log.info("  Vehicles: %d rows", len(df))
    return df


def clean_customers(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("Cleaning customers...")
    df = con.execute("""
        SELECT
            customer_id,
            TRIM(full_name)     AS full_name,
            cnic,
            phone,
            LOWER(TRIM(email))  AS email,
            city,
            gender,
            CAST(age AS INTEGER) AS age,
            has_season_pass,
            season_pass_expiry,
            CAST(loyalty_points AS INTEGER) AS loyalty_points,
            preferred_payment,
            CAST(registration_date AS DATE) AS registration_date
        FROM bronze_customers
        WHERE customer_id IS NOT NULL
          AND full_name IS NOT NULL
    """).df()
    log.info("  Customers: %d rows", len(df))
    return df


def build_silver_fact(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """
    Core Silver fact table: transactions enriched with location & vehicle data.
    Also deduplicates and recalculates fee.
    """
    log.info("Building silver_fact (transactions + locations + vehicles + customers)...")

    df = con.execute("""
        WITH deduped AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY vehicle_id, slot_id,
                                 DATE_TRUNC('hour', entry_time)
                    ORDER BY transaction_id
                ) AS rn
            FROM bronze_transactions
            WHERE transaction_id IS NOT NULL
              AND location_id IS NOT NULL
              AND vehicle_id IS NOT NULL
              AND entry_time IS NOT NULL
              AND exit_time  IS NOT NULL
              AND duration_minutes > 0
        ),
        clean_txn AS (
            SELECT * FROM deduped WHERE rn = 1
        )
        SELECT
            t.transaction_id,
            t.location_id,
            t.vehicle_id,
            t.customer_id,
            t.slot_id,
            t.entry_time,
            t.exit_time,
            t.duration_minutes,
            t.fee_pkr,
            t.payment_method,
            t.vehicle_type,
            CAST(t.entry_time AS DATE)          AS entry_date,
            EXTRACT(HOUR   FROM t.entry_time)   AS entry_hour,
            EXTRACT(DOW    FROM t.entry_time)   AS day_of_week,
            EXTRACT(MONTH  FROM t.entry_time)   AS entry_month,
            EXTRACT(YEAR   FROM t.entry_time)   AS entry_year,
            EXTRACT(WEEK   FROM t.entry_time)   AS entry_week,

            -- Location fields
            l.location_name,
            l.city,
            l.province,
            l.neighborhood,
            l.zone_type,
            l.total_slots,
            l.hourly_rate_pkr,
            l.has_anpr,
            l.has_valet,

            -- Vehicle fields
            v.plate_number,
            v.color         AS vehicle_color,
            v.make_year,
            v.is_blacklisted,
            v.base_rate_pkr AS vehicle_base_rate,

            -- Customer fields (nullable — anonymous transactions allowed)
            c.full_name     AS customer_name,
            c.city          AS customer_city,
            c.has_season_pass,
            c.preferred_payment AS customer_pref_payment

        FROM clean_txn t
        LEFT JOIN bronze_locations l ON t.location_id = l.location_id
        LEFT JOIN bronze_vehicles  v ON t.vehicle_id  = v.vehicle_id
        LEFT JOIN bronze_customers c ON t.customer_id = c.customer_id
    """).df()

    # Add seasonality flags (vectorised using pandas datetime)
    log.info("  Adding seasonality flags (%d rows)...", len(df))
    entry_times = pd.to_datetime(df["entry_time"])
    flags = [get_season_flags(dt) for dt in entry_times]
    flags_df = pd.DataFrame(flags, index=df.index)
    df = pd.concat([df, flags_df], axis=1)

    log.info("  silver_fact: %d rows after dedup", len(df))
    return df


def clean_violations(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("Cleaning violations...")
    df = con.execute("""
        SELECT
            violation_id,
            transaction_id,
            location_id,
            vehicle_id,
            violation_type,
            CAST(violation_time AS TIMESTAMP) AS violation_time,
            CAST(fine_pkr AS DOUBLE)          AS fine_pkr,
            fine_paid,
            resolved
        FROM bronze_violations
        WHERE violation_id IS NOT NULL
    """).df()
    log.info("  Violations: %d rows", len(df))
    return df


def clean_anpr(con: duckdb.DuckDBPyConnection, vehicles_df: pd.DataFrame) -> pd.DataFrame:
    log.info("Cleaning ANPR events...")
    df = con.execute("""
        SELECT
            anpr_event_id,
            location_id,
            transaction_id,
            vehicle_id,
            camera_id,
            event_type,
            CAST(scan_time AS TIMESTAMP) AS scan_time,
            CAST(confidence_score AS DOUBLE) AS confidence_score,
            is_blacklisted_hit
        FROM bronze_anpr
        WHERE anpr_event_id IS NOT NULL
          AND confidence_score >= 0.5
    """).df()

    # Enrich with actual plate number
    plate_map = vehicles_df.set_index("vehicle_id")["plate_number"].to_dict()
    df["plate_number"] = df["vehicle_id"].map(plate_map)

    # Flag blacklisted vehicles
    blacklisted = set(vehicles_df.loc[vehicles_df["is_blacklisted"], "vehicle_id"])
    df["is_blacklisted_hit"] = df["vehicle_id"].isin(blacklisted)

    log.info("  ANPR events: %d rows", len(df))
    return df


def clean_staff_shifts(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    log.info("Cleaning staff shifts...")
    df = con.execute("""
        SELECT
            shift_id,
            location_id,
            TRIM(staff_name) AS staff_name,
            role,
            shift_type,
            CAST(shift_start AS TIMESTAMP) AS shift_start,
            CAST(shift_end   AS TIMESTAMP) AS shift_end,
            week_start
        FROM bronze_staff
        WHERE shift_id IS NOT NULL
    """).df()
    log.info("  Staff shifts: %d rows", len(df))
    return df


# ── Quality gates ─────────────────────────────────────────────────────────────

def run_quality_gates(silver_fact: pd.DataFrame, loc_ids: set, veh_ids: set):
    gate = (
        QualityGate("silver_fact", silver_fact)
        .not_null(["transaction_id", "location_id", "vehicle_id",
                   "entry_time", "exit_time", "fee_pkr"])
        .unique(["transaction_id"])
        .value_range("duration_minutes", min_val=1, max_val=1440)
        .positive_values("fee_pkr")
        .referential_integrity("location_id", loc_ids)
        .referential_integrity("vehicle_id",  veh_ids)
    )
    gate.run(halt_on_critical=True)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run():
    t0 = time.time()
    log.info("=" * 60)
    log.info("Bronze → Silver Pipeline")
    log.info("=" * 60)

    silver_dir = _ROOT / "data" / "silver"
    silver_dir.mkdir(parents=True, exist_ok=True)

    # Open DuckDB in-memory and register Bronze views
    con = duckdb.connect(":memory:")
    for name, alias in [
        ("locations",           "bronze_locations"),
        ("vehicles",            "bronze_vehicles"),
        ("customers",           "bronze_customers"),
        ("parking_transactions","bronze_transactions"),
        ("violations",          "bronze_violations"),
        ("anpr_events",         "bronze_anpr"),
        ("staff_shifts",        "bronze_staff"),
    ]:
        path = _bronze(name)
        con.execute(f"CREATE VIEW {alias} AS SELECT * FROM read_parquet('{path}')")
        log.info("Registered Bronze view: %s", alias)

    # ── Transform each table ──────────────────────────────────────────────────
    silver_locs   = clean_locations(con)
    silver_vehs   = clean_vehicles(con)
    silver_custs  = clean_customers(con)
    silver_fact   = build_silver_fact(con)
    silver_viol   = clean_violations(con)
    silver_anpr   = clean_anpr(con, silver_vehs)
    silver_staff  = clean_staff_shifts(con)

    # ── Quality gate on fact table ────────────────────────────────────────────
    loc_ids = set(silver_locs["location_id"])
    veh_ids = set(silver_vehs["vehicle_id"])
    run_quality_gates(silver_fact, loc_ids, veh_ids)

    # ── Write Silver Parquet ──────────────────────────────────────────────────
    outputs = {
        "silver_locations":  silver_locs,
        "silver_vehicles":   silver_vehs,
        "silver_customers":  silver_custs,
        "silver_fact":       silver_fact,
        "silver_violations": silver_viol,
        "silver_anpr":       silver_anpr,
        "silver_staff":      silver_staff,
    }

    for name, df in outputs.items():
        path = _silver(name)
        df.to_parquet(path, index=False)
        log.info("Written Silver: %s (%d rows)", name, len(df))

    # ── Register in catalog ───────────────────────────────────────────────────
    bronze_sources = {
        "silver_locations":  ["locations"],
        "silver_vehicles":   ["vehicles"],
        "silver_customers":  ["customers"],
        "silver_fact":       ["parking_transactions", "locations", "vehicles", "customers"],
        "silver_violations": ["violations"],
        "silver_anpr":       ["anpr_events", "vehicles"],
        "silver_staff":      ["staff_shifts"],
    }

    for name, df in outputs.items():
        register_from_parquet(
            _silver(name), name, "Silver",
            source_datasets=bronze_sources.get(name, []),
            transformations=["clean", "deduplicate", "cast_types", "enrich"],
        )

    con.close()
    elapsed = time.time() - t0
    log.info("=" * 60)
    log.info("Bronze → Silver complete in %.1f seconds", elapsed)
    total_mb = sum(
        (_ROOT / "data" / "silver" / f"{n}.parquet").stat().st_size
        for n in outputs
    ) / 1e6
    log.info("Total Silver size: %.1f MB", total_mb)
    log.info("=" * 60)
    print(f"\n✅  Bronze → Silver complete ({elapsed:.0f}s) — {total_mb:.1f} MB")


if __name__ == "__main__":
    run()
