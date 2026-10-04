"""Score gene expression-profile priors (time trend, pi2 effect) against pseudo-bulk Xenium changes.

Usage: python tools/pf_score.py DATA_ROOT ANNOT.csv ANSWER_DIR OUT_DIR
Measured calls (fixed before scoring): per slice, mean of count/total*100 over cells with >= 10 panel counts.
time: WT 15 d (3 slices) vs WT 3 d (2 slices); pi2: pi2-3D-1 vs WT-3D-1 (chip 0032595) and pi2-3D-2 vs WT-3D-2
(chip 0032587), paired by chip. "up" = log2 ratio >= log2(1.5) and every replicate comparison agrees in sign;
"down" symmetric; "flat" = |log2 ratio| < log2(1.2) for the mean; otherwise ambiguous (not scored).
Primary read-out: accuracy on genes with a measured up/down call (random guessing among up/down/flat: 1/3).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_bio.xenium import load_section  # noqa: E402

S = {
    "WT-3D-1": "output-XETG00521__0032595__WT-3D-1__20251101__091015",
    "WT-3D-2": "output-XETG00521__0032587__WT-3D-2__20251101__091015",
    "WT-15D-1": "output-XETG00521__0032595__WT-15D-1__20251101__091015",
    "WT-15D-2": "output-XETG00521__0032595__WT-15D-2__20251101__091015",
    "WT-15D-3": "output-XETG00521__0032587__WT-15D-3__20251101__091015",
    "pi2-3D-1": "output-XETG00521__0032595__pi2-3D-1__20251101__091015",
    "pi2-3D-2": "output-XETG00521__0032587__pi2-3D-2__20251101__091015",
}
UP, FLAT, EPS = np.log2(1.5), np.log2(1.2), 0.01
NORM = {"up": "up", "down": "down", "flat": "flat", "unchanged": "flat", "no change": "flat", "stable": "flat"}


def pseudobulk(data_root: Path):
    genes, m, n = None, {}, {}
    for name, d in S.items():
        sec = load_section(data_root / d, name)
        genes = genes or sec.genes
        assert sec.genes == genes
        tot = sec.counts.sum(1)
        keep = tot >= 10
        m[name] = (sec.counts[keep] / tot[keep, None] * 100.0).mean(0)
        n[name] = int(keep.sum())
    return genes, m, n


def call(lfc_mean: float, reps: list[float]) -> str:
    if lfc_mean >= UP and all(r > 0 for r in reps):
        return "up"
    if lfc_mean <= -UP and all(r < 0 for r in reps):
        return "down"
    if abs(lfc_mean) < FLAT:
        return "flat"
    return "ambiguous"


def parse(text: str):
    for mm in re.finditer(r"\{.*?\}", text or "", flags=re.S):
        try:
            o = json.loads(mm.group(0))
        except Exception:
            continue
        t = NORM.get(str(o.get("time_trend", "")).strip().lower())
        p = NORM.get(str(o.get("pi2_effect", "")).strip().lower())
        return t, p, o.get("time_conf"), o.get("pi2_conf")
    return None, None, None, None


def main(data_root, annot, ans_dir, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    genes, m, ncell = pseudobulk(Path(data_root))
    lg = {k: np.log2(v + EPS) for k, v in m.items()}
    t_mean = np.log2(np.mean([m[k] for k in ("WT-15D-1", "WT-15D-2", "WT-15D-3")], 0) + EPS) - \
        np.log2(np.mean([m[k] for k in ("WT-3D-1", "WT-3D-2")], 0) + EPS)
    t_reps = [lg[a] - lg[b] for a in ("WT-15D-1", "WT-15D-2", "WT-15D-3") for b in ("WT-3D-1", "WT-3D-2")]
    p_reps = [lg["pi2-3D-1"] - lg["WT-3D-1"], lg["pi2-3D-2"] - lg["WT-3D-2"]]
    p_mean = np.mean(p_reps, 0)
    meas = {}
    for i, g in enumerate(genes):
        meas[g] = {"time_lfc": float(t_mean[i]), "time": call(t_mean[i], [r[i] for r in t_reps]),
                   "pi2_lfc": float(p_mean[i]), "pi2": call(p_mean[i], [r[i] for r in p_reps]),
                   "mean_wt3": float((m["WT-3D-1"][i] + m["WT-3D-2"][i]) / 2)}
    json.dump({"n_cells": ncell, "genes": meas}, open(out_dir / "measured.json", "w"), indent=0)
    dist = {k: dict(zip(*np.unique([v[k] for v in meas.values()], return_counts=True))) for k in ("time", "pi2")}
    dist = {k: {a: int(b) for a, b in d.items()} for k, d in dist.items()}

    per = defaultdict(lambda: defaultdict(list))  # arm -> gene -> list of (t, p, tc, pc)
    for fp in sorted(Path(ans_dir).glob("*.json")):
        gid, model, mode, s = fp.stem.split("__")
        if gid in meas:
            per[f"{model}:{mode}"][gid].append(parse(fp.read_text()))
    res = {"measured_distribution": dist, "n_cells": ncell, "arms": {}}
    for arm, gd in per.items():
        r = {}
        for key, ix in (("time", 0), ("pi2", 1)):
            acc_dir, acc_all, n_dir, n_all, parsed, total = [], [], 0, 0, 0, 0
            pred_sign, true_lfc = [], []
            for g, answers in gd.items():
                preds = [a[ix] for a in answers]
                total += len(preds)
                preds = [p for p in preds if p]
                parsed += len(preds)
                if not preds:
                    continue
                vote = max(set(preds), key=preds.count)
                truth = meas[g][key]
                if truth in ("up", "down"):
                    acc_dir.append(np.mean([p == truth for p in preds]))
                if truth != "ambiguous":
                    acc_all.append(np.mean([p == truth for p in preds]))
                pred_sign.append(np.mean([{"up": 1, "down": -1, "flat": 0}[p] for p in preds]))
                true_lfc.append(meas[g][f"{key}_lfc"])
            from scipy.stats import spearmanr
            rho = spearmanr(pred_sign, true_lfc).correlation if len(pred_sign) > 5 else float("nan")
            r[key] = {"genes": len(gd), "answers": total, "parse_rate": parsed / max(total, 1),
                      "acc_on_up_down": float(np.mean(acc_dir)) if acc_dir else float("nan"), "n_up_down": len(acc_dir),
                      "acc_3class": float(np.mean(acc_all)) if acc_all else float("nan"), "n_3class": len(acc_all),
                      "spearman_pred_vs_lfc": float(rho)}
        res["arms"][arm] = r
    json.dump(res, open(out_dir / "summary.json", "w"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
