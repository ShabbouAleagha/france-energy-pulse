"""Tests for the France Energy Pulse data generator.

These tests protect the *contract* between the generator and the pipeline:
if the generator stops producing the defects the Bronze/Silver notebooks are
written to handle, the pipeline silently stops being tested. They run in
seconds at a tiny SCALE and need no Databricks, no Spark, no cloud.

Run locally:   pytest -q
Run in CI:     see .github/workflows/ci.yml
"""

import csv
import json
import os
import sys
from pathlib import Path

import pytest

# Make the generator importable regardless of where pytest is invoked from.
GEN_DIR = Path(__file__).resolve().parents[1] / "data_generator"
sys.path.insert(0, str(GEN_DIR))

import common
import config
import generate_dpe
import generate_eco2mix
import generate_others


@pytest.fixture(scope="session")
def landing(tmp_path_factory):
    """Generate a tiny landing zone once, reuse it across all tests."""
    os.environ["FEP_SCALE"] = "0.001"
    out = tmp_path_factory.mktemp("landing")
    generate_dpe.main(str(out))
    generate_others.main(str(out))
    return out


# --------------------------------------------------------------- structure --
def test_all_sources_produce_a_folder(landing):
    for source in ["dpe", "enedis", "meteo", "insee"]:
        assert (landing / source).is_dir(), f"missing source folder: {source}"


def test_three_file_formats_are_present(landing):
    suffixes = {p.suffix for p in landing.rglob("*") if p.is_file()}
    assert {".csv", ".json", ".parquet"} <= suffixes, suffixes


def test_dpe_produces_one_extract_per_week(landing):
    weeks = list((landing / "dpe" / "weekly").iterdir())
    assert len(weeks) == config.DPE_WEEKS
    for week in weeks:
        assert (week / "dpe_extract.csv").is_file()


# ------------------------------------------------------------ determinism ---
def test_generator_is_deterministic():
    """Same seed -> same communes. This is what makes the dataset shareable."""
    a = common.make_communes(common.rng("insee"), 50)
    b = common.make_communes(common.rng("insee"), 50)
    assert a == b


# ------------------------------------- the defects the pipeline handles -----
def _read_all_dpe(landing):
    rows = []
    for path in (landing / "dpe" / "weekly").rglob("dpe_extract.csv"):
        with open(path, newline="", encoding="utf-8") as f:
            rows.extend(csv.DictReader(f))
    return rows


def test_dpe_contains_invalid_commune_codes(landing):
    """Silver quarantines these — if they vanish, the rule goes untested."""
    rows = _read_all_dpe(landing)
    bad = [r for r in rows
           if not (r["code_commune"].isdigit() and len(r["code_commune"]) == 5)]
    assert bad, "expected some malformed commune codes"


def test_dpe_contains_negative_surfaces(landing):
    rows = _read_all_dpe(landing)
    negative = [r for r in rows if float(r["surface_habitable"]) < 0]
    assert negative, "expected some impossible surface values"


def test_dpe_contains_duplicate_ids(landing):
    """Duplicates + re-diagnoses are why Silver deduplicates by latest date."""
    ids = [r["numero_dpe"] for r in _read_all_dpe(landing)]
    assert len(ids) > len(set(ids)), "expected repeated numero_dpe values"


def test_dpe_schema_drifts_partway_through_history(landing):
    """New columns appear at a known week — Auto Loader must evolve."""
    def header(week_idx):
        weeks = sorted((landing / "dpe" / "weekly").iterdir())
        with open(weeks[week_idx] / "dpe_extract.csv", encoding="utf-8") as f:
            return set(next(csv.reader(f)))

    early = header(0)
    late = header(config.P_SCHEMA_DRIFT_WEEK + 5)
    new_columns = late - early
    assert new_columns, "expected schema drift"
    assert {"etiquette_ges", "cout_chauffage"} <= late


# -------------------------------------------------------- other sources -----
def test_meteo_json_has_24_hourly_values(landing):
    any_file = next((landing / "meteo").rglob("*.json"))
    payload = json.loads(any_file.read_text())
    assert len(payload["hourly"]["time"]) == 24
    assert len(payload["hourly"]["temperature_2m"]) == 24


def test_enedis_covers_every_sector(landing):
    any_file = next((landing / "enedis").rglob("*.csv"))
    with open(any_file, newline="", encoding="utf-8") as f:
        sectors = {row["secteur"] for row in csv.DictReader(f)}
    assert sectors == set(common.SECTORS)


def test_insee_reference_is_unique_by_commune(landing):
    pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    table = pq.read_table(landing / "insee" / "communes_reference.parquet")
    codes = table.column("code_commune").to_pylist()
    assert len(codes) == len(set(codes)), "commune codes must be unique"


# ------------------------------------------------------------- eco2mix ------
def test_eco2mix_api_pulls_overlap(tmp_path):
    """Consecutive pulls resend recent points — that's the dedup story."""
    os.environ["FEP_SCALE"] = "0.001"
    generate_eco2mix.generate_api_pulls(str(tmp_path))
    pulls = sorted((tmp_path / "eco2mix" / "api").iterdir())
    assert len(pulls) >= 2

    def keys(pull):
        data = json.loads((pull / "pull.json").read_text())
        return {(r["date_heure"], r["libelle_region"]) for r in data["records"]}

    assert keys(pulls[0]) & keys(pulls[1]), "expected overlapping measurements"
