"""
Pakistan-specific seasonality helpers.
Returns demand multipliers for any given datetime based on:
  - Ramadan (reduced daytime, Iftar surge)
  - Eid-ul-Fitr / Eid-ul-Adha
  - Independence Day (Aug 14)
  - Jummah Friday dip (12-2 pm)
  - Monsoon season (July-Sept)
  - General public holidays
"""
from datetime import date, datetime
from typing import Union
import yaml
from pathlib import Path


def _load_cfg():
    cfg_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        return yaml.safe_load(f)["seasonality"]


_CFG = _load_cfg()

# Pre-process date sets for fast lookup
_EID_FITR   = {date.fromisoformat(d) for d in _CFG["eid_ul_fitr"]["dates"]}
_EID_ADHA   = {date.fromisoformat(d) for d in _CFG["eid_ul_adha"]["dates"]}
_INDEP_DAY  = {date.fromisoformat(d) for d in _CFG["independence_day"]["dates"]}
_HOLIDAYS   = {date.fromisoformat(d) for d in _CFG["public_holidays"]["dates"]}

# Ramadan periods as (start, end) date tuples
_RAMADAN = [
    (date.fromisoformat(p["start"]), date.fromisoformat(p["end"]))
    for p in _CFG["ramadan"]["periods"]
]


def is_ramadan(dt: Union[datetime, date]) -> bool:
    d = dt.date() if isinstance(dt, datetime) else dt
    return any(s <= d <= e for s, e in _RAMADAN)


def is_eid(dt: Union[datetime, date]) -> bool:
    d = dt.date() if isinstance(dt, datetime) else dt
    return d in _EID_FITR or d in _EID_ADHA


def is_eid_fitr(dt: Union[datetime, date]) -> bool:
    d = dt.date() if isinstance(dt, datetime) else dt
    return d in _EID_FITR


def is_eid_adha(dt: Union[datetime, date]) -> bool:
    d = dt.date() if isinstance(dt, datetime) else dt
    return d in _EID_ADHA


def is_independence_day(dt: Union[datetime, date]) -> bool:
    d = dt.date() if isinstance(dt, datetime) else dt
    return d in _INDEP_DAY


def is_public_holiday(dt: Union[datetime, date]) -> bool:
    d = dt.date() if isinstance(dt, datetime) else dt
    return d in _HOLIDAYS


def is_monsoon(dt: Union[datetime, date]) -> bool:
    m = dt.month if isinstance(dt, datetime) else dt.month
    return m in _CFG["monsoon"]["months"]


def is_jummah_dip(dt: datetime) -> bool:
    """True if it's Friday 12:00–13:59 (Jummah prayer time)."""
    return dt.weekday() == 4 and dt.hour in _CFG["jummah"]["dip_hours"]


def get_demand_multiplier(dt: datetime) -> float:
    """
    Return an overall demand multiplier for the given datetime.
    Multiple factors compound multiplicatively; individual caps applied.
    """
    mult = 1.0
    hour = dt.hour

    # Eid: high footfall
    if is_eid(dt):
        if dt.date() in _EID_FITR:
            mult *= _CFG["eid_ul_fitr"]["factor"]
        else:
            mult *= _CFG["eid_ul_adha"]["factor"]
        return min(mult, 3.5)

    # Independence Day
    if is_independence_day(dt):
        mult *= _CFG["independence_day"]["factor"]
        return min(mult, 3.0)

    # Public holidays (non-Eid)
    if is_public_holiday(dt):
        mult *= _CFG["public_holidays"]["factor"]

    # Ramadan
    if is_ramadan(dt):
        if hour in _CFG["ramadan"]["iftar_hours"]:
            mult *= _CFG["ramadan"]["iftar_surge_factor"]
        else:
            mult *= _CFG["ramadan"]["daytime_factor"]

    # Monsoon
    if is_monsoon(dt):
        mult *= _CFG["monsoon"]["factor"]

    # Jummah dip
    if is_jummah_dip(dt):
        mult *= _CFG["jummah"]["factor"]

    # Night-time general dip (midnight–6 am)
    if 0 <= hour < 6:
        mult *= 0.15

    # Morning ramp-up 6–9 am
    elif 6 <= hour < 9:
        mult *= 0.5

    # Peak office hours 9 am–12 pm & 2–6 pm
    elif (9 <= hour < 12) or (14 <= hour < 18):
        mult *= 1.3

    # Evening peak 6–9 pm
    elif 18 <= hour < 21:
        mult *= 1.5

    return max(0.05, mult)


def get_season_flags(dt: datetime) -> dict:
    """Return a dict of all boolean season flags for feature engineering."""
    return {
        "is_ramadan":         int(is_ramadan(dt)),
        "is_eid":             int(is_eid(dt)),
        "is_eid_fitr":        int(is_eid_fitr(dt)),
        "is_eid_adha":        int(is_eid_adha(dt)),
        "is_independence_day":int(is_independence_day(dt)),
        "is_public_holiday":  int(is_public_holiday(dt)),
        "is_monsoon":         int(is_monsoon(dt)),
        "is_jummah":          int(dt.weekday() == 4),
        "is_weekend":         int(dt.weekday() in (5, 6)),  # Sat/Sun
    }
