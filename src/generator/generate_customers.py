"""
Generate Pakistani customer profiles with CNIC-style IDs, 03xx phone numbers.
Output: data/bronze/customers.parquet
"""
import random
from pathlib import Path

import pandas as pd
from faker import Faker

from src.catalog.logger import get_logger

log = get_logger("generator.customers")

# Faker with English locale (ur_PK not supported; we use our own name pools)
_faker_en = Faker("en_US")

# Pakistani first and last names pool (romanised Urdu)
PK_FIRST = [
    "Ahmed", "Ali", "Usman", "Hassan", "Bilal", "Hamza", "Omar", "Zain",
    "Tariq", "Asif", "Kamran", "Imran", "Adnan", "Fahad", "Shoaib",
    "Fatima", "Zainab", "Ayesha", "Sana", "Maryam", "Hira", "Nadia",
    "Amna", "Sara", "Rabia", "Mehwish", "Anum", "Maham", "Saba", "Noor",
    "Muhammad", "Abdul", "Khalid", "Rizwan", "Faisal", "Naeem", "Waseem",
    "Sajid", "Irfan", "Shakeel",
]
PK_LAST = [
    "Khan", "Ahmed", "Malik", "Sheikh", "Raza", "Hussain", "Ali", "Baig",
    "Qureshi", "Siddiqui", "Ansari", "Mirza", "Chaudhry", "Butt", "Awan",
    "Javed", "Iqbal", "Haider", "Aslam", "Nawaz", "Abbasi", "Niazi",
    "Rajput", "Bhatti", "Gillani", "Baloch", "Afridi", "Shinwari", "Shah",
]

CITIES = ["Karachi", "Lahore", "Islamabad", "Rawalpindi", "Peshawar",
          "Quetta", "Multan", "Faisalabad", "Sialkot", "Hyderabad"]

MOBILE_PREFIXES = [
    "0300", "0301", "0302", "0303",   # Mobilink/Jazz
    "0310", "0311", "0312", "0313",   # Warid/Jazz
    "0320", "0321", "0322",           # Zong
    "0330", "0331", "0332", "0333",   # Ufone
    "0340", "0341", "0342",           # Telenor
]


def _cnic(rng: random.Random) -> str:
    """Generate a plausible CNIC: PPPPP-NNNNNNN-C (13 digits with dashes)."""
    province = rng.randint(10000, 54999)
    serial   = rng.randint(1000000, 9999999)
    check    = rng.randint(1, 9)
    return f"{province}-{serial}-{check}"


def _phone(rng: random.Random) -> str:
    prefix = rng.choice(MOBILE_PREFIXES)
    number = rng.randint(1000000, 9999999)
    return f"{prefix}-{number}"


def generate_customers(n: int = 15000, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []

    for i in range(1, n + 1):
        first = rng.choice(PK_FIRST)
        last  = rng.choice(PK_LAST)
        city  = rng.choice(CITIES)
        has_pass = rng.random() < 0.20   # 20% season-pass holders

        rows.append({
            "customer_id":        f"CUST-{i:05d}",
            "full_name":          f"{first} {last}",
            "cnic":               _cnic(rng),
            "phone":              _phone(rng),
            "email":              f"{first.lower()}.{last.lower()}{rng.randint(1,999)}@gmail.com",
            "city":               city,
            "gender":             rng.choice(["Male", "Female"]),
            "age":                rng.randint(18, 65),
            "has_season_pass":    has_pass,
            "season_pass_expiry": (
                f"202{rng.randint(3,5)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"
                if has_pass else None
            ),
            "loyalty_points":     rng.randint(0, 5000),
            "preferred_payment":  rng.choice(["Cash", "JazzCash", "EasyPaisa", "Card"]),
            "registration_date":  f"202{rng.randint(1,3)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
        })

    df = pd.DataFrame(rows)
    log.info(
        "Generated %d customers | season-pass: %d (%.1f%%)",
        len(df), df["has_season_pass"].sum(),
        100 * df["has_season_pass"].mean(),
    )
    return df


def save(df: pd.DataFrame):
    out = Path(__file__).resolve().parents[2] / "data" / "bronze" / "customers.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    log.info("Saved → %s (%d rows)", out, len(df))


if __name__ == "__main__":
    df = generate_customers()
    save(df)
    print(df.head(3).to_string())
