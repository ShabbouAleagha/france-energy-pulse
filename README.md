# ⚡ France Energy Pulse
[![CI](https://github.com/ShabbouAleagha/france-energy-pulse/actions/workflows/ci.yml/badge.svg)](https://github.com/ShabbouAleagha/france-energy-pulse/actions/workflows/ci.yml)

**A production-style lakehouse on Azure Databricks: 5 sources, 3 file formats,
2 ingestion modes, ~49M rows — where does France's energy actually go?**

Data engineering portfolio project. The dataset is **synthetic but realistic**: a
reproducible generator simulates France's open-data energy sources (RTE éCO2mix,
ADEME DPE, Enedis, Météo, INSEE) — including their real-world defects: schema
drift, duplicate records, late-arriving events, invalid commune codes, impossible
values, and heavy population skew. Generating the mess on purpose means every
pipeline pattern here is demonstrated against a documented failure mode.

## Why a synthetic generator?

Most portfolio projects die on "download this 40GB file first". Here, one command
produces the full multi-source landing zone at any size:

```bash
FEP_SCALE=1 python data_generator/run_all.py --out /Volumes/<catalog>/landing
#  SCALE 0.01 ≈ 500MB (laptop) · 1 ≈ 49M rows (the run below) · 5 ≈ ~250M rows
```

Deterministic seeds → identical data on every machine → reviewable, reproducible
results.

## Sources

| # | Source | Format | Cadence | Injected problems | Rows @ SCALE=1 |
|---|---|---|---|---|---|
| S1 | éCO2mix grid archive | CSV `;` | yearly files | — | 1,262,592 |
| S1b | éCO2mix live API | nested JSON | every 15 min | overlapping pulls, late corrected events | 14,024 |
| S2 | DPE housing diagnostics | CSV | weekly extracts | schema drift, duplicates, invalid codes, re-diagnoses | ~47,000,000 |
| S3 | Enedis consumption | CSV | yearly drop | value skew in consumption (row counts are uniform — verified, skew ratio 2.9) | 420,000 |
| S4 | Weather | nested JSON | daily | nested hourly arrays to flatten | 315,648 |
| S5 | INSEE communes | Parquet | static | — | 35,000 |

## Architecture

```
landing/ (immutable raw, Unity Catalog Volume)
   ├ batch : yearly archives, weekly extracts, annual drops
   └ stream: API pulls
                    │  Auto Loader (cloudFiles)
                    ▼
   BRONZE  — 1:1 with source + audit columns (_ingested_at, _source_file,
             _extract_week), schema evolution, _rescued_data, DQ metrics table
                    ▼
   SILVER  — deduplication, conformed values, quarantine table for bad records
                    ▼
   GOLD    — business tables answering real questions
```

## What each layer actually does

**Bronze — keep everything, change nothing.** Auto Loader ingests both the batch
archives and the JSON API pulls into Delta tables. Duplicates and late events are
*deliberately kept*: Bronze is an immutable audit log of what the source sent.
Schema evolution (`addNewColumns`) handles the DPE extracts that gain two new
columns partway through history; unparseable fields land in `_rescued_data`
rather than being silently dropped. A `dpe_dq_metrics` table counts the damage
per weekly extract — you cannot fix what you do not measure.

**Silver — decide and clean.** Deduplication uses a window function per business
key: for éCO2mix, keep the record from the latest API pull (later pulls may carry
corrections); for DPE, keep the latest diagnosis per `numero_dpe` (buildings get
re-assessed after renovation). Energy classes are normalised (`"g "` → `"G"`).
Records failing business rules — non-positive surface area, malformed commune
codes — are **quarantined, not deleted**, so they remain auditable.

**Gold — answer questions.**
- `gold.renovation_priority` — % of dwellings in energy class F/G per commune
  ("passoires thermiques"), joined to INSEE population, filtered to communes with
  ≥20 diagnoses.
- `gold.conso_vs_temperature` — hourly grid consumption joined to regional
  temperature (315k × 1.26M row join).

## An honest finding

The temperature/consumption join runs correctly, but shows **no meaningful
correlation** — because the generator produces temperature and consumption
independently. With real RTE data this relationship is strong (cold → electric
heating → demand spike). Documenting this rather than presenting a spurious
result was a deliberate choice: a pipeline that runs is not the same as a result
that means something.

## Roadmap

- [x] Phase 1 — Data generator (5 sources, 3 formats, scale knob, deterministic)
- [x] Phase 2 — Bronze: Auto Loader, schema evolution, rescued data, DQ metrics
- [x] Phase 3 — Silver: window-function dedup, normalisation, quarantine tables
- [x] Phase 4 — Gold: renovation priority + consumption vs temperature
- [ ] Phase 5 — Performance: partitioning, liquid clustering, skew handling on
      the population-skewed joins
- [ ] Phase 6 — Ops: Databricks Asset Bundles, CI/CD with GitHub Actions,
      pytest + data quality tests, SLA monitoring

## Repo map

```
data_generator/          the synthetic multi-source generator (start here)
src/ingestion/           Bronze notebooks — Auto Loader, schema evolution
src/transformations/     Silver + Gold notebooks
docs/sources/            one data contract per source
docs/decisions/          ADRs — why each pattern was chosen
```

## Stack

Azure Databricks (Serverless) · PySpark · Delta Lake · Unity Catalog (catalogs,
schemas, volumes) · Auto Loader · Structured Streaming · Python

## Notes

Run in a Unity Catalog workspace. Create a catalog, a `landing` schema with a
`landing` volume and a `_checkpoints` volume, then run the generator followed by
the notebooks in numeric order. All notebooks read their catalog name from a
single constant at the top.
