"""S3 Enedis (yearly CSV vendor drops), S4 Open-Meteo (hourly JSON),
S5 INSEE reference (Parquet) — three more formats, three more cadences.

Enedis : landing/enedis/annual/{year}/conso_communes_{year}.csv
         one row per commune x sector x year. Skew: consumption follows
         commune population, so Paris-sized communes dominate aggregates.
Meteo  : landing/meteo/daily/{date}/{region}.json — hourly temperatures,
         API-response shaped (nested arrays), one file per region per day.
INSEE  : landing/insee/communes_reference.parquet — the conformed dim,
         written in Parquet to add the third file format.
"""

import csv
import json
import math
import os
from datetime import timedelta

import config
from common import REGIONS, SECTORS, get_scale, make_communes, rng

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover
    pa = pq = None


def _communes():
    r = rng("insee")
    n = max(100, int(config.N_COMMUNES * min(get_scale(), 1)))
    return make_communes(r, n)


def generate_enedis(out_root: str) -> None:
    r = rng("enedis")
    communes = _communes()
    sector_share = {"RESIDENTIEL": 0.36, "TERTIAIRE": 0.30,
                    "INDUSTRIE": 0.27, "AGRICULTURE": 0.07}
    for year in range(config.HISTORY_START.year, config.HISTORY_END.year + 1):
        folder = os.path.join(out_root, "enedis", "annual", str(year))
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"conso_communes_{year}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["annee", "code_commune", "secteur",
                        "nb_sites", "conso_totale_mwh"])
            for c in communes:
                base_mwh = c.population * r.uniform(2.1, 2.6)  # skewed by pop
                for s in SECTORS:
                    w.writerow([year, c.code, s,
                                max(1, int(c.population * 0.5)),
                                round(base_mwh * sector_share[s], 2)])
        print(f"  enedis {year}: {len(communes) * len(SECTORS)} rows")


def generate_meteo(out_root: str) -> None:
    r = rng("meteo")
    day = config.HISTORY_START
    n_days = (config.HISTORY_END - config.HISTORY_START).days + 1
    for d in range(n_days):
        current = day + timedelta(days=d)
        folder = os.path.join(out_root, "meteo", "daily", current.isoformat())
        os.makedirs(folder, exist_ok=True)
        seasonal = 12 + 9 * math.cos(
            2 * math.pi * (current.timetuple().tm_yday - 200) / 365)
        for code, name in REGIONS:
            temps = [round(seasonal
                           + 5 * math.sin(2 * math.pi * (h - 9) / 24)
                           + r.uniform(-1.5, 1.5), 1) for h in range(24)]
            payload = {
                "region_code": code,
                "region_name": name,
                "date": current.isoformat(),
                "hourly": {
                    "time": [f"{current}T{h:02d}:00" for h in range(24)],
                    "temperature_2m": temps,
                },
            }
            with open(os.path.join(folder, f"{code}.json"), "w") as f:
                json.dump(payload, f)
    print(f"  meteo: {n_days} days x {len(REGIONS)} regions")


def generate_insee(out_root: str) -> None:
    communes = _communes()
    folder = os.path.join(out_root, "insee")
    os.makedirs(folder, exist_ok=True)
    if pq is None:
        raise RuntimeError("pyarrow required: pip install pyarrow")
    r = rng("insee-income")
    table = pa.table({
        "code_commune": [c.code for c in communes],
        "nom_commune": [c.name for c in communes],
        "code_region": [c.region_code for c in communes],
        "population": [c.population for c in communes],
        "revenu_median": [round(r.uniform(17_000, 34_000)) for _ in communes],
    })
    pq.write_table(table, os.path.join(folder, "communes_reference.parquet"))
    print(f"  insee: {len(communes)} communes (parquet)")


def main(out_root: str) -> None:
    generate_enedis(out_root)
    generate_meteo(out_root)
    generate_insee(out_root)
