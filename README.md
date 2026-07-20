# ⚡ France Energy Pulse

**A production-style lakehouse on Databricks: 5 sources, 3 file formats,
2 ingestion modes, 1 question — where does France's energy actually go?**

> Data engineering portfolio project. The dataset is **synthetic but
> realistic**: a reproducible generator simulates France's real open-data
> energy sources (RTE éCO2mix, ADEME DPE, Enedis, Météo, INSEE) — including
> their real-world defects: schema drift, duplicates, late events, invalid
> codes, and heavy skew. Generating the mess on purpose means every
> pipeline pattern here is demonstrated against a documented failure mode.

## Why synthetic sources?
Real portfolios die on "download this 40GB file first". Here, one command
produces the full multi-source landing zone at any size:

```bash
FEP_SCALE=10 python data_generator/run_all.py --out /Volumes/energy_pulse/landing
#  SCALE 0.01 ≈ 800MB (laptop) · 1 ≈ 8GB · 10 ≈ 50GB+ (Databricks target)
```

Deterministic seeds → identical data on every machine → reviewable results.

## Sources (see `docs/sources/` for full contracts)
| # | Source | Format | Cadence | Injected problems |
|---|---|---|---|---|
| S1 | éCO2mix grid data | CSV `;` + JSON API | 15 min | overlapping pulls, late corrected events |
| S2 | DPE housing diagnostics | CSV weekly | weekly | schema drift, duplicates, invalid codes, re-diagnoses (SCD2) |
| S3 | Enedis consumption | CSV yearly drop | yearly | population skew (Paris ≫ villages) |
| S4 | Weather | nested JSON | daily | nested arrays to normalize |
| S5 | INSEE reference | Parquet | static | conformed dimension |

## Architecture
```
landing/ (immutable raw)        ── Auto Loader ──►  Bronze (Delta, 1:1 + audit cols)
   ├ batch: archives, weekly, yearly                    │ quarantine metrics
   └ stream: API pulls (Structured Streaming)           ▼
                                              Silver (dedup, conformed, SCD2)
                                                        ▼
                                     Gold (star schema, renovation-urgency score)
                                                        ▼
                                         Power BI · forecast model · monitoring
```

## Roadmap
- [x] Phase 1 — Data generator (5 sources, 3 formats, scale knob)
- [x] Phase 2 — Bronze: Auto Loader batch + streaming, schema evolution, DQ metrics
- [ ] Phase 3 — Silver: dedup rules, SCD2 on DPE, quarantine tables, tests
- [ ] Phase 4 — Streaming hardening: watermarks, late-event handling, exactly-once
- [ ] Phase 5 — Gold: star schema, skew handling (salting/AQE), liquid clustering
- [ ] Phase 6 — Ops: Asset Bundles CI/CD, SLA monitoring, cost notes, forecast model

## Repo map
```
data_generator/   the synthetic multi-source generator (start here)
src/ingestion/    Bronze notebooks (Auto Loader, streaming, quarantine)
docs/sources/     one data contract per source
docs/decisions/   ADRs — why each pattern was chosen
tests/            pytest + data-quality checks
```
