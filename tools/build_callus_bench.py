"""Build the callus spatial-imputation benchmark v1 and score non-LLM baselines.

Usage: python tools/build_callus_bench.py DATA_ROOT OUT_ROOT
Writes OUT_ROOT/tasks (solver-visible), OUT_ROOT/keys (answer keys, 0700), OUT_ROOT/results.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_bio.bench import gene_annotation, mask_sets, build_task, SOLVERS, grade, sha256  # noqa: E402
from aimeth_bio.xenium import load_section  # noqa: E402

S = {
    "WT-3D-1": "output-XETG00521__0032595__WT-3D-1__20251101__091015",
    "WT-3D-2": "output-XETG00521__0032587__WT-3D-2__20251101__091015",
    "WT-12D-1": "output-XETG00521__0032595__WT-12D-1__20251101__091015",
    "WT-12D-2": "output-XETG00521__0032595__WT-12D-2__20251101__091015",
    "WT-12D-3": "output-XETG00521__0032587__WT-12D-3__20251101__091015",
    "WT-15D-1": "output-XETG00521__0032595__WT-15D-1__20251101__091015",
    "WT-15D-2": "output-XETG00521__0032595__WT-15D-2__20251101__091015",
    "WT-15D-3": "output-XETG00521__0032587__WT-15D-3__20251101__091015",
    "pi2-3D-1": "output-XETG00521__0032595__pi2-3D-1__20251101__091015",
    "pi2-3D-2": "output-XETG00521__0032587__pi2-3D-2__20251101__091015",
}
PAIRS = [  # (tier, reference, target)
    ("same_time", "WT-3D-1", "WT-3D-2"), ("same_time", "WT-3D-2", "WT-3D-1"),
    ("same_time", "WT-12D-1", "WT-12D-2"), ("same_time", "WT-12D-2", "WT-12D-3"),
    ("same_time", "WT-15D-1", "WT-15D-2"), ("same_time", "WT-15D-2", "WT-15D-3"),
    ("cross_time", "WT-3D-1", "WT-12D-1"), ("cross_time", "WT-12D-1", "WT-15D-1"),
    ("cross_time", "WT-3D-1", "WT-15D-1"), ("cross_time", "WT-15D-1", "WT-3D-1"),
    ("mutant", "WT-3D-1", "pi2-3D-1"), ("mutant", "WT-3D-2", "pi2-3D-2"),
]


def main(data_root: Path, out: Path):
    t0 = time.time()
    tasks_dir, keys_dir, res_dir = out / "tasks", out / "keys", out / "results"
    for d in (tasks_dir, keys_dir, res_dir):
        d.mkdir(parents=True, exist_ok=True)
    os.chmod(keys_dir, 0o700)
    ann = gene_annotation(data_root / "Gene group2.csv")
    genes = load_section(data_root / S["WT-3D-1"]).genes
    sets = mask_sets(genes, ann, seed=0)
    (out / "mask_sets.json").write_text(json.dumps(
        {k: [{"id": g, **ann.get(g, {})} for g in v] for k, v in sets.items()}, indent=1, ensure_ascii=False))
    rows = []
    for tier, ref, tgt in PAIRS:
        for set_name, masked in sets.items():
            tid = f"{tier}__{ref}__{tgt}__{set_name}"
            info = build_task(data_root / S[ref], data_root / S[tgt], masked, tid, tasks_dir, keys_dir,
                              {"tier": tier, "reference": ref, "target": tgt, "mask_set": set_name})
            t = np.load(tasks_dir / f"{tid}.npz")
            k = np.load(keys_dir / f"{tid}.key.npz")
            for solver, f in SOLVERS.items():
                g = grade(f(t), k, t["tgt_xy"])
                rows.append({**info, "solver": solver, **{x: g[x] for x in ("cell_r_mean", "pattern_r_mean", "n_informative")}})
                (res_dir / f"{tid}__{solver}.json").write_text(json.dumps(g))
            print(f"{tid}: " + " ".join(f"{r['solver']}={r['pattern_r_mean']:.3f}" for r in rows[-3:]), flush=True)
    (res_dir / "baseline_summary.json").write_text(json.dumps(rows, indent=1))
    manifest = {"elapsed_s": time.time() - t0, "data_root": str(data_root),
                "inputs_sha256": {n: sha256(data_root / d / "cell_feature_matrix.h5") for n, d in S.items()},
                "source_sha256": {str(p.relative_to(ROOT)): sha256(p) for p in sorted((ROOT / "aimeth_bio").glob("*.py"))
                                  + [ROOT / "tools/build_callus_bench.py"]}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
