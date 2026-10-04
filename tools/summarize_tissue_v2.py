"""Evaluate the P1 v2 pre-specified predictions M1-M6 from run_tissue_v2 records.
Usage: python tools/summarize_tissue_v2.py OUT_DIR > summary.json
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

out = Path(sys.argv[1])
R = defaultdict(dict)
for f in sorted(out.glob("rec-*.json")):
    r = json.loads(f.read_text())
    R[r["arm"]][r["seed"]] = r["metrics"]
seeds = sorted(R["two_scale"])


def d(arm, seed, k, default=float("nan")):
    return R[arm].get(seed, {}).get("domains", {}).get(k, default)


table = {}
for arm in R:
    table[arm] = {s: {"units": d(arm, s, "units", 0), "size_median": d(arm, s, "size_median"),
                      "largest_fraction": d(arm, s, "largest_fraction"), "on_fraction": d(arm, s, "on_fraction"),
                      "R": d(arm, s, "R"), "R_null_p95": d(arm, s, "R_null_p95"),
                      "cells": R[arm][s].get("n_alive", R[arm][s].get("cells"))} for s in sorted(R[arm])}

m1 = [table["two_scale"][s]["units"] >= 20 for s in seeds]
m2 = [table["community"][s]["largest_fraction"] >= 0.8 for s in seeds]
m3 = [table["two_scale+shuffled"][s]["units"] == 0 for s in seeds]
m4 = [bool(table["two_scale"][s]["R"] > table["two_scale"][s]["R_null_p95"]) for s in seeds]
m5r = [table["two_scale_L50"][s]["size_median"] / table["two_scale"][s]["size_median"]
       if table["two_scale"][s]["size_median"] else float("nan") for s in seeds]
m5 = [bool(x >= 2.5) for x in m5r]
m6 = [table["two_scale+lesion"][s]["units"] / table["two_scale"][s]["units"] if table["two_scale"][s]["units"] else float("nan")
      for s in seeds]
res = {
    "seeds": seeds,
    "M1_two_scale_ge20_units": {"per_seed": m1, "met": sum(m1) == len(seeds)},
    "M2_community_runaway": {"per_seed": m2, "met": sum(m2) >= 4},
    "M3_shuffled_zero_units": {"per_seed": m3, "met": sum(m3) == len(seeds)},
    "M4_regular_spacing": {"per_seed": m4, "met": sum(m4) >= 4},
    "M5_size_ratio_L50": {"ratio": m5r, "per_seed": m5, "met": sum(m5) >= 4},
    "M6_lesion_units_rel_intact": {"ratio": m6, "claim": "exploratory, none"},
    "table": table,
}
print(json.dumps(res, indent=1, default=float))
