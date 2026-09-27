"""
Generate Pakistani vehicles with authentic plate format (ABC-123).
Output: data/bronze/vehicles.parquet
"""
import random
import string
from pathlib import Path

import pandas as pd
import yaml

from src.catalog.logger import get_logger

log = get_logger("generator.vehicles")


def load_config():
    cfg_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _generate_plate(rng: random.Random) -> str:
    """Pakistani plate format: LLL-NNNN or LL-NNNN (e.g., ABC-1234, KR-1234)."""
    styles = [
        # New format: 3 letters + 4 digits
        lambda: "".join(rng.choices(string.ascii_uppercase, k=3))
              + "-"
              + "".join(rng.choices(string.digits, k=4)),
        # Old format: city prefix 2-3 letters + 3-4 digits
        lambda: rng.choice(["KHI", "LHR", "ISB", "RWP", "PEW", "QTA", "MUL", "FSD"])
              + "-"
              + "".join(rng.choices(string.digits, k=3)),
    ]
    return rng.choice(styles)()


def generate_vehicles(n: int = 30000, seed: int = 42) -> pd.DataFrame:
    cfg = load_config()
    rng = random.Random(seed)

    vtype_cfg = cfg["vehicle_types"]
    vtypes   = [v["type"]          for v in vtype_cfg]
    weights  = [v["weight"]        for v in vtype_cfg]
    base_rates = {v["type"]: v["base_rate_pkr"] for v in vtype_cfg}

    colors = ["White", "Silver", "Black", "Red", "Blue", "Grey", "Green", "Gold"]

    plates_seen: set = set()
    rows = []

    for i in range(1, n + 1):
        # Ensure unique plate
        plate = _generate_plate(rng)
        while plate in plates_seen:
            plate = _generate_plate(rng)
        plates_seen.add(plate)

        vtype = rng.choices(vtypes, weights=weights, k=1)[0]
        rows.append({
            "vehicle_id":       f"VEH-{i:05d}",
            "plate_number":     plate,
            "vehicle_type":     vtype,
            "color":            rng.choice(colors),
            "make_year":        rng.randint(2005, 2024),
            "is_blacklisted":   rng.random() < 0.005,    # 0.5% blacklisted
            "base_rate_pkr":    base_rates[vtype],
            "registered_city":  rng.choice(
                ["Karachi", "Lahore", "Islamabad", "Rawalpindi",
                 "Peshawar", "Quetta", "Multan", "Faisalabad"]
            ),
        })

    df = pd.DataFrame(rows)
    log.info("Generated %d vehicles | unique plates: %d", len(df), df["plate_number"].nunique())
    return df


def save(df: pd.DataFrame):
    out = Path(__file__).resolve().parents[2] / "data" / "bronze" / "vehicles.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("Saved → %s (%d rows)", out, len(df))


if __name__ == "__main__":
    df = generate_vehicles()
    save(df)
    print(df.head(3).to_string())
