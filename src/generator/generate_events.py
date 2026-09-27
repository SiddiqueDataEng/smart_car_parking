"""
Generate supporting event tables:
  - anpr_events          : ANPR plate-scan logs
  - sensor_events        : Slot occupancy sensor pings
  - violations           : Parking violations
  - staff_shifts         : Staff scheduling per location

Outputs go to data/bronze/
"""
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
from tqdm import tqdm

from src.catalog.logger import get_logger

log = get_logger("generator.events")


# ── ANPR Events ───────────────────────────────────────────────────────────────

def generate_anpr_events(
    transactions_df: pd.DataFrame,
    locations_df: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """One ANPR entry scan + one exit scan per transaction (with noise)."""
    rng = random.Random(seed)

    loc_anpr = locations_df.set_index("location_id")["has_anpr"].to_dict()
    rows = []
    anpr_idx = 1

    for _, txn in tqdm(transactions_df.iterrows(), total=len(transactions_df),
                       desc="ANPR events"):
        if not loc_anpr.get(txn["location_id"], False):
            continue

        for event_type, timestamp in [("ENTRY", txn["entry_time"]), ("EXIT", txn["exit_time"])]:
            # Occasionally simulate a re-scan or miss
            confidence = round(rng.gauss(0.93, 0.06), 3)
            confidence = max(0.50, min(1.0, confidence))
            plate = None
            if isinstance(txn.get("vehicle_id"), str):
                # Will be enriched with plate in Silver
                plate = txn["vehicle_id"]  # placeholder — Silver joins this

            rows.append({
                "anpr_event_id":   f"ANPR-{anpr_idx:08d}",
                "location_id":     txn["location_id"],
                "transaction_id":  txn["transaction_id"],
                "vehicle_id":      txn["vehicle_id"],
                "camera_id":       f"CAM-{txn['location_id']}-{rng.randint(1, 4):02d}",
                "event_type":      event_type,
                "scan_time":       timestamp + timedelta(seconds=rng.randint(-10, 10)),
                "confidence_score": confidence,
                "is_blacklisted_hit": False,  # enriched in Silver
            })
            anpr_idx += 1

    # Add some spurious blacklist hits
    for i in range(200):
        loc = rng.choice(locations_df["location_id"].tolist())
        rows.append({
            "anpr_event_id":    f"ANPR-{anpr_idx:08d}",
            "location_id":      loc,
            "transaction_id":   None,
            "vehicle_id":       None,
            "camera_id":        f"CAM-{loc}-01",
            "event_type":       "ENTRY",
            "scan_time":        datetime(2023, rng.randint(1, 12), rng.randint(1, 28),
                                         rng.randint(0, 23), rng.randint(0, 59)),
            "confidence_score": round(rng.uniform(0.75, 0.99), 3),
            "is_blacklisted_hit": True,
        })
        anpr_idx += 1

    df = pd.DataFrame(rows)
    log.info("Generated %d ANPR events", len(df))
    return df


# ── Sensor Events ─────────────────────────────────────────────────────────────

def generate_sensor_events(
    transactions_df: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """Simulate slot occupancy sensor pings (1 ping on entry, 1 on exit + heartbeats)."""
    rng = random.Random(seed)
    np.random.seed(seed)

    rows = []
    ev_idx = 1

    sample = transactions_df.sample(min(50_000, len(transactions_df)),
                                    random_state=seed)

    for _, txn in tqdm(sample.iterrows(), total=len(sample), desc="Sensor events"):
        slot_id = txn["slot_id"]

        # Entry ping
        rows.append({
            "sensor_event_id": f"SEN-{ev_idx:08d}",
            "slot_id":         slot_id,
            "location_id":     txn["location_id"],
            "status":          "OCCUPIED",
            "timestamp":       txn["entry_time"],
            "battery_pct":     rng.randint(60, 100),
        })
        ev_idx += 1

        # Heartbeat pings every 30 min during occupancy
        duration = txn["duration_minutes"]
        for offset in range(30, int(duration), 30):
            rows.append({
                "sensor_event_id": f"SEN-{ev_idx:08d}",
                "slot_id":         slot_id,
                "location_id":     txn["location_id"],
                "status":          "OCCUPIED",
                "timestamp":       txn["entry_time"] + timedelta(minutes=offset),
                "battery_pct":     rng.randint(60, 100),
            })
            ev_idx += 1

        # Exit ping
        rows.append({
            "sensor_event_id": f"SEN-{ev_idx:08d}",
            "slot_id":         slot_id,
            "location_id":     txn["location_id"],
            "status":          "FREE",
            "timestamp":       txn["exit_time"],
            "battery_pct":     rng.randint(60, 100),
        })
        ev_idx += 1

    df = pd.DataFrame(rows)
    log.info("Generated %d sensor events", len(df))
    return df


# ── Violations ────────────────────────────────────────────────────────────────

def generate_violations(
    transactions_df: pd.DataFrame,
    vehicles_df: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """~2% of transactions result in a violation of some kind."""
    rng = random.Random(seed)

    viol_types = ["Overstay", "No Ticket", "Blacklisted Plate",
                  "Wrong Zone", "Unauthorized Parking", "Double Parking"]
    fine_map = {
        "Overstay": 500,
        "No Ticket": 1000,
        "Blacklisted Plate": 5000,
        "Wrong Zone": 800,
        "Unauthorized Parking": 1500,
        "Double Parking": 1200,
    }

    sample = transactions_df.sample(
        frac=0.02, random_state=seed
    ).reset_index(drop=True)

    rows = []
    for i, txn in sample.iterrows():
        vtype = rng.choice(viol_types)
        rows.append({
            "violation_id":    f"VIO-{i+1:06d}",
            "transaction_id":  txn["transaction_id"],
            "location_id":     txn["location_id"],
            "vehicle_id":      txn["vehicle_id"],
            "violation_type":  vtype,
            "violation_time":  txn["entry_time"] + timedelta(
                minutes=rng.randint(0, max(1, txn["duration_minutes"]))
            ),
            "fine_pkr":        fine_map[vtype],
            "fine_paid":       rng.random() > 0.35,
            "resolved":        rng.random() > 0.25,
        })

    df = pd.DataFrame(rows)
    log.info("Generated %d violations", len(df))
    return df


# ── Staff Shifts ──────────────────────────────────────────────────────────────

def generate_staff_shifts(
    locations_df: pd.DataFrame,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate 2 years of staff shifts (3 shifts/day × 50 locations)."""
    rng = random.Random(seed)

    roles = ["Security Guard", "Cashier", "Valet", "Supervisor"]
    shift_types = [("Morning", 6, 14), ("Evening", 14, 22), ("Night", 22, 6)]

    first_names = ["Ahmed", "Ali", "Omar", "Bilal", "Hassan", "Fatima",
                   "Sara", "Nadia", "Kamran", "Usman"]
    last_names  = ["Khan", "Malik", "Raza", "Shah", "Hussain", "Ahmed"]

    rows = []
    shift_idx = 1

    start_dt = datetime(2023, 1, 1)
    end_dt   = datetime(2024, 12, 31)
    total_days = (end_dt - start_dt).days

    for _, loc in locations_df.iterrows():
        for day_offset in range(0, total_days, 7):  # weekly schedule
            day_dt = start_dt + timedelta(days=day_offset)
            for shift_name, s_start, s_end in shift_types:
                n_staff = rng.randint(2, 6)
                for s in range(n_staff):
                    role = rng.choice(roles)
                    rows.append({
                        "shift_id":     f"SHF-{shift_idx:07d}",
                        "location_id":  loc["location_id"],
                        "staff_name":   f"{rng.choice(first_names)} {rng.choice(last_names)}",
                        "role":         role,
                        "shift_type":   shift_name,
                        "shift_start":  day_dt.replace(hour=s_start),
                        "shift_end":    day_dt.replace(hour=s_end) + timedelta(
                            days=1 if s_end < s_start else 0
                        ),
                        "week_start":   day_dt.date(),
                    })
                    shift_idx += 1

    df = pd.DataFrame(rows)
    log.info("Generated %d staff shift records", len(df))
    return df


# ── Save helpers ──────────────────────────────────────────────────────────────

def save(df: pd.DataFrame, name: str):
    out = Path(__file__).resolve().parents[2] / "data" / "bronze" / f"{name}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("Saved → %s (%d rows, %.1f MB)", out, len(df), out.stat().st_size / 1e6)


if __name__ == "__main__":
    import pandas as pd
    from src.generator.generate_locations    import generate_locations
    from src.generator.generate_vehicles     import generate_vehicles
    from src.generator.generate_transactions import generate_transactions
    from src.generator.generate_customers    import generate_customers

    locs   = generate_locations()
    vehs   = generate_vehicles()
    custs  = generate_customers()
    txns   = generate_transactions(locs, vehs, custs)

    anpr   = generate_anpr_events(txns, locs)
    sens   = generate_sensor_events(txns)
    viol   = generate_violations(txns, vehs)
    staff  = generate_staff_shifts(locs)

    save(anpr,  "anpr_events")
    save(sens,  "sensor_events")
    save(viol,  "violations")
    save(staff, "staff_shifts")
