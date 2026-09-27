"""
Generate parking locations across 10 Pakistani cities.
Output: data/bronze/locations.parquet
"""
import random
import uuid
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from src.catalog.logger import get_logger

log = get_logger("generator.locations")


def load_config():
    cfg_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_locations(seed: int = 42) -> pd.DataFrame:
    cfg = load_config()
    rng = random.Random(seed)
    np.random.seed(seed)

    zone_types = cfg["zone_types"]
    cities = cfg["cities"]
    n_locations = cfg["generation"]["locations_count"]

    rows = []
    loc_idx = 1

    # Distribute locations across cities by weight
    for city in cities:
        city_count = max(2, round(n_locations * city["weight"]))
        for _ in range(city_count):
            neighborhood = rng.choice(city["neighborhoods"])
            zone = rng.choice(zone_types)
            total_slots = rng.randint(20, 300)
            floors = rng.randint(1, 5) if zone in ("Corporate", "Market", "Commercial") else 1

            rows.append({
                "location_id":   f"LOC-{loc_idx:03d}",
                "location_name": f"{neighborhood} Parking Plaza {loc_idx}",
                "city":          city["name"],
                "province":      city["province"],
                "neighborhood":  neighborhood,
                "zone_type":     zone,
                "total_slots":   total_slots,
                "floors":        floors,
                "has_anpr":      rng.random() > 0.4,
                "has_ev_charging": rng.random() > 0.7,
                "has_valet":     rng.random() > 0.6,
                "is_covered":    rng.random() > 0.5,
                "hourly_rate_pkr": rng.choice([30, 40, 50, 60, 80, 100, 120]),
                "monthly_pass_pkr": rng.choice([1500, 2000, 2500, 3000, 4000, 5000]),
                "latitude":      round(rng.uniform(24.0, 34.0), 6),
                "longitude":     round(rng.uniform(62.0, 74.0), 6),
                "opening_hour":  rng.choice([0, 6, 7, 8]),
                "closing_hour":  rng.choice([22, 23, 0]),  # 0 = 24h
                "created_at":    "2022-01-01",
            })
            loc_idx += 1

    df = pd.DataFrame(rows)
    log.info("Generated %d locations across %d cities", len(df), df["city"].nunique())
    return df


def save(df: pd.DataFrame):
    out = Path(__file__).resolve().parents[2] / "data" / "bronze" / "locations.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("Saved → %s (%d rows)", out, len(df))


if __name__ == "__main__":
    df = generate_locations()
    save(df)
    print(df.head(3).to_string())
