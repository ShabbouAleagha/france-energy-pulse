"""Run every source generator into a landing/ tree.

Usage:
    python run_all.py --out /path/to/data            # uses config.SCALE
    FEP_SCALE=10 python run_all.py --out /dbfs/...   # Databricks, ~50 GB

On Databricks: upload this folder, point --out at a Volume
(/Volumes/<catalog>/<schema>/landing) and run with FEP_SCALE=10.
"""

import argparse
import os
import time

import config
import generate_dpe
import generate_eco2mix
import generate_others
from common import get_scale


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".")
    parser.add_argument("--only", choices=["eco2mix", "dpe", "others"],
                        help="run a single generator")
    args = parser.parse_args()

    out_root = os.path.join(args.out, config.OUTPUT_ROOT)
    os.makedirs(out_root, exist_ok=True)
    print(f"SCALE={get_scale()}  ->  {out_root}")

    steps = {
        "eco2mix": generate_eco2mix.main,
        "dpe": generate_dpe.main,
        "others": generate_others.main,
    }
    if args.only:
        steps = {args.only: steps[args.only]}

    for name, fn in steps.items():
        t0 = time.time()
        print(f"[{name}]")
        fn(out_root)
        print(f"[{name}] {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
