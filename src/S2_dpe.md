# Source contract — S2 DPE (housing energy diagnostics)

| Field | Value |
|---|---|
| Publisher (simulated) | ADEME — Diagnostic de Performance Énergétique |
| Access | Weekly bulk CSV extracts |
| Format | CSV, comma-separated, UTF-8, header row |
| Grain | 1 row = 1 energy diagnosis of 1 dwelling |
| Volume | 156 weekly extracts × ~300,000 rows ≈ 47M rows @ SCALE=1 |
| Cadence & SLA | New extract every Sunday; available in Silver by 06:00 Monday |
| Business key | `numero_dpe` — **not unique** in Bronze (re-diagnoses + duplicates) |
| Dedup rule (Silver) | Keep the row with the latest `date_etablissement` per `numero_dpe` |

## Known issues
- ~1.5% exact duplicate rows within a single extract
- ~2% of rows are **re-diagnoses**: same `numero_dpe`, later date, different class
  (a dwelling re-assessed after renovation) — this is the SCD-style history
- ~1% malformed `code_commune`: empty, `"99ZZZ"`, `"0"`, or a trailing letter
- ~0.4% negative `surface_habitable` (data entry errors)
- ~2% mixed-case / padded enum values: `"g "` instead of `"G"`
- `annee_construction` is polymorphic: an integer year OR the string `"ANCIEN"`
- **Schema drift**: from extract week 100 onwards, two new columns appear —
  `etiquette_ges` and `cout_chauffage`

## Handling
- Bronze: `cloudFiles.schemaEvolutionMode=addNewColumns` + `rescuedDataColumn`;
  stream restarts once on first sight of the new columns (expected, wrapped in
  a retry). Nothing is dropped.
- Bronze: `bronze.dpe_dq_metrics` counts rows, duplicates, negative surfaces,
  bad commune codes and rescued rows **per extract week**.
- Silver: latest diagnosis per `numero_dpe`; `classe_dpe` upper-cased and
  trimmed; rows failing business rules go to `silver.dpe_quarantine`, never
  deleted.

## Schema snapshot (v1)
`numero_dpe` string · `date_etablissement` date · `code_commune` string(5) ·
`type_batiment` string · `annee_construction` string · `surface_habitable`
double (m²) · `classe_dpe` string(A–G) · `conso_kwh_m2_an` double

## Schema snapshot (v2, from week 100)
v1 + `etiquette_ges` string(A–G) · `cout_chauffage` double (EUR/year)

## Change log
- 2026-07: initial contract
- 2026-07: v2 schema documented after schema drift observed in ingestion

> Synthetic data — generator: `data_generator/generate_dpe.py`
