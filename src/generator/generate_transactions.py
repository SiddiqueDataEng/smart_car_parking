"""
Generate ~500 K parking transactions with hyper-realistic Pakistan seasonality.
Output: data/bronze/parking_transactions.parquet
"""
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from tqdm import tqdm

from src.catalog.logger import get_logger
from src.generator.seasonality import get_demand_multiplier

log = get_logger("generator.transactions")


def load_config():
    cfg_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _weighted_hour(rng: random.Random, dt: datetime) -> int:
    """Sample an hour-of-day weighted by demand profile."""
    weights = []
    for h in range(24):
        probe = dt.replace(hour=h, minute=0, second=0)
        weights.append(get_demand_multiplier(probe))
    total = sum(weights)
    r = rng.random() * total
    cum = 0.0
    for h, w in enumerate(weights):
        cum += w
        if r <= cum:
            return h
    return 12


def generate_transactions(
    locations_df: pd.DataFrame,
    vehicles_df:  pd.DataFrame,
    customers_df: pd.DataFrame,
    target: int = 500_000,
    seed: int = 42,
) -> pd.DataFrame:
    cfg = load_config()
    rng = random.Random(seed)
    np.random.seed(seed)

    start_dt = datetime.fromisoformat(cfg["generation"]["start_date"])
    end_dt   = datetime.fromisoformat(cfg["generation"]["end_date"])
    total_days = (end_dt - start_dt).days

    pay_methods = [p["method"] for p in cfg["payment_methods"]]
    pay_weights = [p["weight"] for p in cfg["payment_methods"]]

    loc_ids   = locations_df["location_id"].tolist()
    loc_rates = locations_df.set_index("location_id")["hourly_rate_pkr"].to_dict()
    loc_slots = locations_df.set_index("location_id")["total_slots"].to_dict()

    veh_ids   = vehicles_df["vehicle_id"].tolist()
    veh_types = vehicles_df.set_index("vehicle_id")["vehicle_type"].to_dict()
    veh_rates = vehicles_df.set_index("vehicle_id")["base_rate_pkr"].to_dict()

    cust_ids  = customers_df["customer_id"].tolist()

    # Avg transactions per day
    daily_target = target / total_days

    rows = []
    txn_idx = 1

    log.info("Generating ~%d transactions over %d days...", target, total_days)

    for day_offset in tqdm(range(total_days), desc="Generating transactions"):
        day_dt = start_dt + timedelta(days=day_offset)

        # Day-level multiplier from a mid-day probe
        midday = day_dt.replace(hour=14)
        day_mult = get_demand_multiplier(midday)
        # Clamp day multiplier so individual hours still vary
        n_today = max(1, int(rng.gauss(daily_target * day_mult, daily_target * 0.15)))

        for _ in range(n_today):
            hour   = _weighted_hour(rng, day_dt)
            minute = rng.randint(0, 59)
            second = rng.randint(0, 59)
            entry_dt = day_dt.replace(hour=hour, minute=minute, second=second)

            # Duration: most 30 min–4 h; tail up to 12 h
            if rng.random() < 0.70:
                duration_min = int(rng.gauss(90, 45))
            elif rng.random() < 0.90:
                duration_min = int(rng.gauss(240, 60))
            else:
                duration_min = int(rng.gauss(480, 120))
            duration_min = max(5, min(duration_min, 720))

            exit_dt = entry_dt + timedelta(minutes=duration_min)

            loc_id  = rng.choice(loc_ids)
            veh_id  = rng.choice(veh_ids)
            cust_id = rng.choice(cust_ids) if rng.random() > 0.15 else None

            # Fee calculation: hourly rate × hours, minimum 1-hour charge
            hourly_rate = max(loc_rates.get(loc_id, 50), veh_rates.get(veh_id, 50))
            hours_billed = max(1, duration_min / 60)
            fee_pkr = round(hourly_rate * hours_billed, 0)
            # Add surcharge for Eid/IndependenceDay
            entry_probe = entry_dt
            mult = get_demand_multiplier(entry_probe)
            if mult > 1.8:
                fee_pkr = round(fee_pkr * 1.25, 0)  # 25% surge

            slot_id = f"{loc_id}-S{rng.randint(1, loc_slots.get(loc_id, 100)):03d}"

            rows.append({
                "transaction_id":  f"TXN-{txn_idx:07d}",
                "location_id":     loc_id,
                "vehicle_id":      veh_id,
                "customer_id":     cust_id,
                "slot_id":         slot_id,
                "entry_time":      entry_dt,
                "exit_time":       exit_dt,
                "duration_minutes": duration_min,
                "fee_pkr":         fee_pkr,
                "payment_method":  rng.choices(pay_methods, weights=pay_weights, k=1)[0],
                "is_season_pass":  False,  # Will be enriched in Silver
                "vehicle_type":    veh_types.get(veh_id, "Unknown"),
                "entry_date":      entry_dt.date(),
                "entry_hour":      hour,
                "day_of_week":     entry_dt.weekday(),
            })
            txn_idx += 1

            if txn_idx % 100_000 == 0:
                log.info("  Progress: %d transactions generated", txn_idx)

    df = pd.DataFrame(rows)
    log.info(
        "Generated %d transactions | %.1f M PKR total revenue",
        len(df), df["fee_pkr"].sum() / 1_000_000,
    )
    return df


def save(df: pd.DataFrame):
    out = Path(__file__).resolve().parents[2] / "data" / "bronze" / "parking_transactions.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("Saved → %s (%d rows, %.1f MB)", out, len(df), out.stat().st_size / 1e6)


if __name__ == "__main__":
    from src.generator.generate_locations import generate_locations
    from src.generator.generate_vehicles  import generate_vehicles
    from src.generator.generate_customers import generate_customers

    locs  = generate_locations()
    vehs  = generate_vehicles()
    custs = generate_customers()
    df    = generate_transactions(locs, vehs, custs)
    save(df)
    print(df.head(3).to_string())
