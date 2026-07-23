# Source contract — S5 INSEE (commune reference)

| Field | Value |
|---|---|
| Publisher (simulated) | INSEE — référentiel des communes |
| Access | Single bulk file |
| Format | Parquet |
| Grain | 1 row = 1 commune |
| Volume | 35,000 rows @ SCALE=1 |
| Cadence & SLA | Static reference; refreshed at most yearly |
| Business key | `code_commune` — unique |
| Dedup rule | None needed |

## Role in the model
This is the **conformed dimension**: the single source of truth for commune
codes, names, population and median income. Every other source (S2 DPE, S3
Enedis) joins to it on `code_commune`. If a code does not exist here, the record
is by definition invalid — this is what the Silver quarantine rules check
against.

## Known issues
- None injected. Parquet is typed and clean, which is exactly why it is used as
  the reference: the third file format in the project also happens to be the one
  that needs no cleaning.
- `population` is deliberately power-law distributed (a few very large communes,
  a long tail of villages) — the root cause of join skew downstream.

## Handling
- Read straight from Parquet into `silver.communes`; no Bronze stage, since
  there is nothing to audit or rescue.

## Schema snapshot (v1)
`code_commune` string(5) · `nom_commune` string · `code_region` string(2) ·
`population` int · `revenu_median` int (EUR/year)

## Change log
- 2026-07: initial contract

> Synthetic data — generator: `data_generator/generate_others.py`
