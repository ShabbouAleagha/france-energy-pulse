# Source contract — S3 Enedis (electricity consumption per commune)

| Field | Value |
|---|---|
| Publisher (simulated) | Enedis — consommation annuelle par commune et secteur |
| Access | Annual bulk CSV drop, one file per year |
| Format | CSV, comma-separated, header row |
| Grain | 1 row = 1 commune × 1 sector × 1 year |
| Volume | 35,000 communes × 4 sectors × 3 years = 420,000 rows @ SCALE=1 |
| Cadence & SLA | One file per year, delivered irregularly; ingested on arrival |
| Business key | (`annee`, `code_commune`, `secteur`) — unique |
| Dedup rule | None needed; a re-delivered year replaces the previous file |

## Known issues
- **Heavy population skew**: consumption scales with commune population, which
  follows a power law. A handful of large communes account for a large share of
  total volume — this is the main source of partition skew in Gold aggregations
  and joins.
- Sector values are a closed enum but are not validated upstream.
- Files arrive in per-year subfolders, so ingestion needs
  `recursiveFileLookup=true`.

## Handling
- Bronze: read with `inferSchema` + `recursiveFileLookup`, add `_ingested_at`.
- Gold: joins on `code_commune` against the INSEE reference (S5). Skew handling
  (salting / AQE) is a Phase 5 item.

## Schema snapshot (v1)
`annee` int · `code_commune` string(5) · `secteur` string
(RESIDENTIEL | TERTIAIRE | INDUSTRIE | AGRICULTURE) · `nb_sites` int ·
`conso_totale_mwh` double

## Change log
- 2026-07: initial contract

> Synthetic data — generator: `data_generator/generate_others.py`
