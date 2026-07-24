"""S2 — ADEME DPE simulator: the big, dirty, evolving source.

Weekly CSV extracts -> landing/dpe/weekly/{year}-W{week}/dpe_extract.csv

Injected real-world problems (all counted in a manifest for later checks):
  * exact duplicate rows                       (P_DUPLICATE_ROW)
  * nulls in nullable columns                  (P_NULL_FIELD)
  * malformed / unknown commune codes          (P_BAD_COMMUNE_CODE)
  * negative or absurd surfaces                (P_NEGATIVE_SURFACE)
  * mixed-case / padded enum values ("g ")     (P_MIXED_CASE_ENUM)
  * ~2% of each week's rows are RE-DIAGNOSES of existing dpe ids with a new
    date and class -> this is what makes SCD2 in Silver meaningful
  * schema drift: from week P_SCHEMA_DRIFT_WEEK, two new columns appear
    (etiquette_ges, cout_chauffage) -> Auto Loader schema evolution story

Volume: DPE_WEEKS x DPE_ROWS_PER_WEEK x SCALE rows.
"""

import csv
import json
import os
from datetime import timedelta

import config
from common import (
    BUILDING_TYPES,
    DPE_CLASSES,
    Commune,
    get_scale,
    make_communes,
    maybe_null,
    rng,
)


def _row(r, communes: list[Commune], dpe_id: str, diag_date, drifted: bool):
    c = r.choice(communes)
    code = c.code
    if r.random() < config.P_BAD_COMMUNE_CODE:
        code = r.choice(["99ZZZ", "", "0", code + "X"])
    surface = round(r.lognormvariate(4.2, 0.5), 1)
    if r.random() < config.P_NEGATIVE_SURFACE:
        surface = -surface
    classe = r.choice(DPE_CLASSES)
    if r.random() < config.P_MIXED_CASE_ENUM:
        classe = classe.lower() + " "
    row = {
        "numero_dpe": dpe_id,
        "date_etablissement": diag_date.isoformat(),
        "code_commune": code,
        "type_batiment": maybe_null(r, r.choice(BUILDING_TYPES)),
        "annee_construction": maybe_null(
            r, r.choice([r.randint(1850, 2025), "ANCIEN"])),
        "surface_habitable": surface,
        "classe_dpe": classe,
        "conso_kwh_m2_an": maybe_null(r, round(r.uniform(40, 550), 1)),
    }
    if drifted:
        row["etiquette_ges"] = r.choice(DPE_CLASSES)
        row["cout_chauffage"] = round(surface * r.uniform(8, 25), 2)
    return row


def main(out_root: str) -> None:
    r = rng("dpe")
    scale = get_scale()
    rows_per_week = max(50, int(config.DPE_ROWS_PER_WEEK * scale))
    n_communes = max(100, int(config.N_COMMUNES * min(scale, 1)))
    communes = make_communes(r, n_communes)

    manifest = {"weeks": [], "injected": {"duplicates": 0, "rediagnoses": 0}}
    issued_ids: list[str] = []
    next_id = 0

    for week_idx in range(config.DPE_WEEKS):
        week_date = config.HISTORY_START + timedelta(weeks=week_idx)
        iso = week_date.isocalendar()
        folder = os.path.join(out_root, "dpe", "weekly",
                              f"{iso.year}-W{iso.week:02d}")
        os.makedirs(folder, exist_ok=True)
        drifted = week_idx >= config.P_SCHEMA_DRIFT_WEEK
        path = os.path.join(folder, "dpe_extract.csv")

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = None
            for _ in range(rows_per_week):
                if issued_ids and r.random() < 0.02:  # re-diagnosis -> SCD2
                    dpe_id = r.choice(issued_ids)
                    manifest["injected"]["rediagnoses"] += 1
                else:
                    dpe_id = f"DPE{next_id:010d}"
                    next_id += 1
                    if len(issued_ids) < 500_000:
                        issued_ids.append(dpe_id)
                row = _row(r, communes, dpe_id, week_date, drifted)
                if writer is None:
                    writer = csv.DictWriter(f, row.keys())
                    writer.writeheader()
                writer.writerow(row)
                if r.random() < config.P_DUPLICATE_ROW:
                    writer.writerow(row)
                    manifest["injected"]["duplicates"] += 1
        manifest["weeks"].append(f"{iso.year}-W{iso.week:02d}")
        if week_idx % 26 == 0:
            print(f"  dpe week {week_idx + 1}/{config.DPE_WEEKS}")

    with open(os.path.join(out_root, "dpe", "_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"  dpe: {config.DPE_WEEKS} weeks x ~{rows_per_week} rows")
