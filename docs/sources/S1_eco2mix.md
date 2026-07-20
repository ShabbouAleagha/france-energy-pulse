# Source contract — S1 éCO2mix (grid production/consumption)

| Field | Value |
|---|---|
| Publisher (simulated) | RTE — éCO2mix |
| Access | Yearly CSV archives (backfill) + JSON API pulls every 15 min (live) |
| Format | CSV `;`-separated (archive) / nested JSON (API) |
| Grain | 1 row = 1 region × 1 quarter-hour |
| Volume | ~1.26M rows/region-year set; API adds ~50 records/pull |
| Cadence & SLA | Live data available in Silver ≤ 30 min after pull |
| Keys | (`libelle_region`, `date_heure`) — NOT unique in Bronze (late resends) |
| Known issues | Overlapping API pulls (duplicates by design); ~5% late corrected points up to 6h old; `taux_co2` derived, not additive |
| Dedup rule (Silver) | Keep record from the LATEST pull per key (`pull_timestamp` desc) |
| Contact / license | Synthetic data — generator: `data_generator/generate_eco2mix.py` |

## Schema snapshot (v1)
`date_heure` string(ISO+01:00) · `libelle_region` string · `consommation`,
`nucleaire`, `eolien`, `solaire`, `hydraulique`, `thermique` double (MW) ·
`taux_co2` double (g/kWh)

## Change log
- 2026-07: initial contract

> Template: copy this file for S2–S5. One contract per source, updated
> whenever the schema or cadence changes. PRs that change a generator
> MUST update its contract — enforced by convention, mentioned in reviews.
