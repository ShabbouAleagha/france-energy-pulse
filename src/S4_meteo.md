# Source contract — S4 Météo (hourly temperature by region)

| Field | Value |
|---|---|
| Publisher (simulated) | Open-Meteo — hourly forecast/history API |
| Access | REST API, one call per region per day |
| Format | Nested JSON (API response shape) |
| Grain | 1 file = 1 region × 1 day, containing 24 hourly values |
| Volume | 1,096 days × 12 regions = 13,152 files → 315,648 rows @ SCALE=1 |
| Cadence & SLA | Daily pull; available in Silver same day |
| Business key | (`region_code`, `heure`) — unique after flattening |
| Dedup rule | None needed; one file per region-day |

## Known issues
- **Many small files**: ~13k files of a few KB each. This is the classic small-file
  problem — it slows listing and reading, and is why the ingestion warns about
  converting to Delta + `OPTIMIZE`. A Phase 5 item.
- Hourly values arrive as **parallel arrays** (`hourly.time`,
  `hourly.temperature_2m`) rather than an array of objects, so they must be
  zipped and exploded, not simply flattened.
- Files sit in per-date subfolders → `recursiveFileLookup=true` required.

## Handling
- Silver: `arrays_zip("hourly.time", "hourly.temperature_2m")` then `explode`,
  producing one row per region-hour. Written directly to Silver because the
  source has no data quality defects to quarantine.

## Schema snapshot (v1, raw)
```
region_code   string
region_name   string
date          string (ISO date)
hourly.time              array<string>   (24 entries)
hourly.temperature_2m    array<double>   (24 entries, °C)
```

## Schema snapshot (Silver, flattened)
`region_code` string · `region_name` string · `date` string · `heure` string ·
`temperature` double (°C)

## Change log
- 2026-07: initial contract

> Synthetic data — generator: `data_generator/generate_others.py`
