"""Summarise tissue-scale records against protocol criteria T1-T6."""
import glob, json, sys
import numpy as np
d = sys.argv[1]
R = [json.load(open(f)) for f in sorted(glob.glob(f"{d}/rec-*.json"))]
def col(arm, f):
    return np.array([f(r["metrics"]) for r in sorted(R, key=lambda r: r["seed"]) if r["arm"] == arm], float)
g = {
    "cells": lambda m: m["cells"], "orgZ": lambda m: m["organizer"]["z"], "units": lambda m: m["tissue"]["units"],
    "R": lambda m: m["tissue"]["R"], "Rp95": lambda m: m["tissue"]["R_null_p95"], "cov": lambda m: m["demand_coverage"],
    "calls1k": lambda m: m["expensive_calls_per_1000_cell_steps"], "unit_med": lambda m: m["tissue"]["unit_size_median"],
    "sim_min": lambda m: m["sim_seconds"] / 60,
}
arms = sorted({r["arm"] for r in R})
for a in arms:
    print(a.ljust(16), " ".join(f"{k}={np.round(col(a, f), 2).tolist()}" for k, f in g.items()))
out = {}
if "full" in arms:
    z = col("full", g["orgZ"]); out["T1_full_z_gt3"] = int((z > 3).sum())
    if "shuffled_signal" in arms: out["T1_shuffled_z_lt1"] = int((col("shuffled_signal", g["orgZ"]) < 1).sum())
    out["T2_units_ge20"] = int((col("full", g["units"]) >= 20).sum())
    out["T3_R_gt_null95"] = int((col("full", g["R"]) > col("full", g["Rp95"])).sum())
    out["T4_calls_le5"] = int((col("full", g["calls1k"]) <= 5).sum())
    if "task_blind" in arms: out["T5_cov_gt_blind"] = int((col("full", g["cov"]) > col("task_blind", g["cov"])).sum())
    if "full+lesion" in arms: out["T6_lesion_ratio"] = np.round(col("full+lesion", g["cells"]) / col("full", g["cells"]), 3).tolist()
print(json.dumps(out, indent=1))
