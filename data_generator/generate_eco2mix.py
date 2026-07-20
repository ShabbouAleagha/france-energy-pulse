"""S1 — RTE éCO2mix simulator.

Two output modes, mirroring how RTE really publishes:

1. archive : yearly, semicolon-separated CSV per region, 15-minute steps.
             -> landing/eco2mix/archive/{year}/eco2mix_{region}_{year}.csv
2. api     : "live" JSON pulls (one file per simulated poll), including
             ~5% late/duplicate re-sent points -> the streaming dedup story.
             -> landing/eco2mix/api/{pull_ts}/pull.json

Volume: 12 regions x 35 040 quarter-hours/year x N years  (~1.3M rows/year
at any SCALE — time series length is driven by dates, not SCALE).
"""

import csv
import json
import math
import os
from datetime import date, datetime, timedelta

import config
from common import REGIONS, rng


def _point(r, region_name: str, ts: datetime) -> dict:
    """One 15-min grid measurement with plausible daily/seasonal shape."""
    hour = ts.hour + ts.minute / 60
    day_of_year = ts.timetuple().tm_yday
    seasonal = 1 + 0.35 * math.cos(2 * math.pi * (day_of_year - 15) / 365)
    daily = 1 + 0.25 * math.sin(2 * math.pi * (hour - 7) / 24)
    base = 4500 * seasonal * daily * r.uniform(0.95, 1.05)

    nucleaire = base * r.uniform(0.55, 0.7)
    eolien = base * r.uniform(0.02, 0.18)
    solaire = max(0.0, base * 0.15 * math.sin(math.pi * (hour - 6) / 12)) \
        if 6 <= hour <= 18 else 0.0
    hydraulique = base * r.uniform(0.08, 0.14)
    thermique = max(0.0, base - nucleaire - eolien - solaire - hydraulique)

    return {
        "date_heure": ts.strftime("%Y-%m-%dT%H:%M:%S+01:00"),
        "libelle_region": region_name,
        "consommation": round(base, 1),
        "nucleaire": round(nucleaire, 1),
        "eolien": round(eolien, 1),
        "solaire": round(solaire, 1),
        "hydraulique": round(hydraulique, 1),
        "thermique": round(thermique, 1),
        "taux_co2": round(20 + thermique / base * 400, 1),
    }


def generate_archives(out_root: str) -> None:
    r = rng("eco2mix-archive")
    year_start, year_end = config.HISTORY_START.year, config.HISTORY_END.year
    for year in range(year_start, year_end + 1):
        folder = os.path.join(out_root, "eco2mix", "archive", str(year))
        os.makedirs(folder, exist_ok=True)
        for _, region_name in REGIONS:
            path = os.path.join(
                folder, f"eco2mix_{region_name.replace(' ', '_')}_{year}.csv")
            ts = datetime(year, 1, 1)
            end = datetime(year + 1, 1, 1)
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = None
                while ts < end:
                    row = _point(r, region_name, ts)
                    if writer is None:  # RTE uses ';' as separator
                        writer = csv.DictWriter(f, row.keys(), delimiter=";")
                        writer.writeheader()
                    writer.writerow(row)
                    ts += timedelta(minutes=15)
        print(f"  eco2mix archive {year}: done")


def generate_api_pulls(out_root: str) -> None:
    """Simulate polling the live API every 15 min for API_DAYS days.

    Each pull returns the last hour of points for all regions; consecutive
    pulls therefore overlap (duplicates), and P_LATE_EVENT points are
    corrected values re-sent later — exactly what breaks naive pipelines.
    """
    r = rng("eco2mix-api")
    start = datetime.combine(config.HISTORY_END + timedelta(days=1),
                             datetime.min.time())
    pulls = config.API_DAYS * 96
    for i in range(pulls):
        pull_ts = start + timedelta(minutes=15 * i)
        folder = os.path.join(out_root, "eco2mix", "api",
                              pull_ts.strftime("%Y-%m-%dT%H-%M"))
        os.makedirs(folder, exist_ok=True)
        records = []
        for _, region_name in REGIONS:
            for back in range(4):  # last hour -> 4 points, overlapping pulls
                ts = pull_ts - timedelta(minutes=15 * back)
                records.append(_point(r, region_name, ts))
            if r.random() < config.P_LATE_EVENT:  # late corrected point
                late_ts = pull_ts - timedelta(hours=r.randint(2, 6))
                p = _point(r, region_name, late_ts)
                p["consommation"] = round(p["consommation"] * 1.002, 1)
                records.append(p)
        with open(os.path.join(folder, "pull.json"), "w") as f:
            json.dump({"pull_timestamp": pull_ts.isoformat(),
                       "records": records}, f)
    print(f"  eco2mix api: {pulls} pulls")


def main(out_root: str) -> None:
    generate_archives(out_root)
    generate_api_pulls(out_root)
