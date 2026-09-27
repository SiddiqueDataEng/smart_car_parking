"""
Master data generation script.
Run:  python src/generator/generate_all.py

Generates all Bronze-layer Parquet files:
  data/bronze/locations.parquet
  data/bronze/vehicles.parquet
  data/bronze/customers.parquet
  data/bronze/parking_transactions.parquet
  data/bronze/anpr_events.parquet
  data/bronze/sensor_events.parquet
  data/bronze/violations.parquet
  data/bronze/staff_shifts.parquet
"""
import time
from pathlib import Path

import yaml

from src.catalog.logger import get_logger
from src.generator.generate_locations    import generate_locations,    save as save_locs
from src.generator.generate_vehicles     import generate_vehicles,     save as save_vehs
from src.generator.generate_customers    import generate_customers,    save as save_custs
from src.generator.generate_transactions import generate_transactions, save as save_txns
from src.generator.generate_events       import (
    generate_anpr_events, generate_sensor_events,
    generate_violations,  generate_staff_shifts,
    save as save_event,
)

log = get_logger("generator.main")


def load_config():
    cfg_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    cfg  = load_config()
    seed = cfg["generation"]["seed"]
    n_vehicles  = cfg["generation"]["vehicles_count"]
    n_customers = cfg["generation"]["customers_count"]
    n_target    = cfg["generation"]["target_transactions"]

    t0 = time.time()
    log.info("=" * 60)
    log.info("SMART Parking Solutions — Bronze Data Generation")
    log.info("=" * 60)

    # ── Step 1: Reference tables ──────────────────────────────────────────────
    log.info("[1/8] Generating locations...")
    locs = generate_locations(seed=seed)
    save_locs(locs)
    log.info("      ✓ %d locations", len(locs))

    log.info("[2/8] Generating vehicles...")
    vehs = generate_vehicles(n=n_vehicles, seed=seed)
    save_vehs(vehs)
    log.info("      ✓ %d vehicles", len(vehs))

    log.info("[3/8] Generating customers...")
    custs = generate_customers(n=n_customers, seed=seed)
    save_custs(custs)
    log.info("      ✓ %d customers", len(custs))

    # ── Step 2: Transactions ──────────────────────────────────────────────────
    log.info("[4/8] Generating parking transactions (~%d)...", n_target)
    txns = generate_transactions(locs, vehs, custs, target=n_target, seed=seed)
    save_txns(txns)
    log.info("      ✓ %d transactions", len(txns))

    # ── Step 3: Event tables ──────────────────────────────────────────────────
    log.info("[5/8] Generating ANPR events...")
    anpr = generate_anpr_events(txns, locs, seed=seed)
    save_event(anpr, "anpr_events")
    log.info("      ✓ %d ANPR events", len(anpr))

    log.info("[6/8] Generating sensor events...")
    sens = generate_sensor_events(txns, seed=seed)
    save_event(sens, "sensor_events")
    log.info("      ✓ %d sensor events", len(sens))

    log.info("[7/8] Generating violations...")
    viol = generate_violations(txns, vehs, seed=seed)
    save_event(viol, "violations")
    log.info("      ✓ %d violations", len(viol))

    log.info("[8/8] Generating staff shifts...")
    staff = generate_staff_shifts(locs, seed=seed)
    save_event(staff, "staff_shifts")
    log.info("      ✓ %d shift records", len(staff))

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    bronze_dir = Path(__file__).resolve().parents[2] / "data" / "bronze"
    total_mb = sum(f.stat().st_size for f in bronze_dir.glob("*.parquet")) / 1e6

    log.info("=" * 60)
    log.info("Bronze generation complete in %.1f seconds", elapsed)
    log.info("Total Bronze size: %.1f MB", total_mb)
    log.info("Files in data/bronze/:")
    for f in sorted(bronze_dir.glob("*.parquet")):
        rows = len(__import__("pandas").read_parquet(f))
        log.info("  %-40s %8d rows  %.1f MB", f.name, rows, f.stat().st_size / 1e6)
    log.info("=" * 60)

    print(f"\n✅  Bronze data generation complete — {elapsed:.0f}s")
    print(f"   Total: {total_mb:.1f} MB across {len(list(bronze_dir.glob('*.parquet')))} files")


if __name__ == "__main__":
    main()
