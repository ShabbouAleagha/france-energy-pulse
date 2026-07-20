"""Shared reference data + helpers for all generators.

Everything is deterministic given a seed, so the dataset is reproducible —
a property you can brag about in the README (recruiters like "reproducible").
"""

import os
import random
from dataclasses import dataclass

import config

# The 12 metropolitan regions RTE actually reports on (+ national roll-up).
REGIONS = [
    ("11", "Ile-de-France"),
    ("24", "Centre-Val de Loire"),
    ("27", "Bourgogne-Franche-Comte"),
    ("28", "Normandie"),
    ("32", "Hauts-de-France"),
    ("44", "Grand Est"),
    ("52", "Pays de la Loire"),
    ("53", "Bretagne"),
    ("75", "Nouvelle-Aquitaine"),
    ("76", "Occitanie"),
    ("84", "Auvergne-Rhone-Alpes"),
    ("93", "Provence-Alpes-Cote d'Azur"),
]

SECTORS = ["RESIDENTIEL", "TERTIAIRE", "INDUSTRIE", "AGRICULTURE"]
DPE_CLASSES = ["A", "B", "C", "D", "E", "F", "G"]
BUILDING_TYPES = ["Maison", "Appartement", "Immeuble collectif", "Tertiaire"]


def get_scale() -> float:
    """SCALE from env var FEP_SCALE, else config.SCALE."""
    return float(os.environ.get("FEP_SCALE", config.SCALE))


def rng(seed_suffix: str) -> random.Random:
    """Deterministic per-generator RNG so sources can run independently."""
    return random.Random(f"france-energy-pulse::{seed_suffix}")


@dataclass(frozen=True)
class Commune:
    code: str
    name: str
    region_code: str
    population: int


def make_communes(r: random.Random, n: int) -> list[Commune]:
    """Synthesize a realistic commune reference set.

    Population is heavily skewed (a few huge cities, a long tail of villages)
    — this is what later produces genuine Spark skew in joins/aggregations.
    """
    communes = []
    syllables = ["mont", "ville", "saint", "bourg", "clair", "neuf", "sur",
                 "lac", "pre", "champ", "roche", "val", "haut", "bois"]
    for i in range(n):
        region_code, _ = REGIONS[i % len(REGIONS)]
        code = f"{region_code[0]}{i:04d}"[:5].zfill(5)
        name = ("-".join(r.sample(syllables, 2))).capitalize()
        # Zipf-ish population: rank-based power law.
        population = max(80, int(2_200_000 / ((i % n) + 1) ** 0.82))
        communes.append(Commune(code, f"{name}-{i}", region_code, population))
    return communes


def maybe_null(r: random.Random, value, p: float | None = None):
    p = config.P_NULL_FIELD if p is None else p
    return None if r.random() < p else value
