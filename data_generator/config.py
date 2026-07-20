"""Central configuration for the France Energy Pulse synthetic data generators.

SCALE is the single knob that controls total volume.
Rough output sizes (raw, uncompressed):

    SCALE = 0.01  -> ~50 MB   (local smoke test)
    SCALE = 1     -> ~5 GB    (laptop-friendly full run)
    SCALE = 10    -> ~50 GB   (Databricks run — the portfolio target)
    SCALE = 50    -> ~250 GB  (stress test)

Every generator reads SCALE and the date ranges below, so one change
re-sizes the whole dataset consistently.
"""

from datetime import date

# ---------------------------------------------------------------- scale ----
SCALE: float = 0.01  # override with env var FEP_SCALE (see common.get_scale)

# ---------------------------------------------------------- date ranges ----
HISTORY_START = date(2023, 1, 1)   # backfill start for time-series sources
HISTORY_END = date(2025, 12, 31)   # backfill end
API_DAYS = 3                       # days of "live" API pulls to simulate

# --------------------------------------------------------------- volumes ---
# Base values at SCALE = 1; generators multiply by SCALE.
N_COMMUNES = 35_000            # France has ~34 935 communes
DPE_ROWS_PER_WEEK = 60_000     # new diagnostics per weekly extract
DPE_WEEKS = 156                # 3 years of weekly extracts
METEO_STATIONS_PER_REGION = 8

# ------------------------------------------------------------ messiness ----
# Probabilities of injected data-quality problems (the fun part).
P_DUPLICATE_ROW = 0.015        # exact duplicates
P_NULL_FIELD = 0.03            # random nulls in nullable columns
P_BAD_COMMUNE_CODE = 0.01      # commune codes that don't exist / malformed
P_NEGATIVE_SURFACE = 0.004     # impossible values
P_MIXED_CASE_ENUM = 0.02       # "g" instead of "G", "Maison " with spaces
P_LATE_EVENT = 0.05            # éCO2mix points re-sent in a later API pull
P_SCHEMA_DRIFT_WEEK = 100      # DPE week index where new columns appear

# ---------------------------------------------------------------- output ---
OUTPUT_ROOT = "landing"        # relative to --out; mirrors the ADLS layout
