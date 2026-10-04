"""Run the P1 offline developmental experiment and write results.

Usage: python3 tools/run_p1.py OUTDIR
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aimeth_dev.sim import Params, run, params_dict  # noqa: E402
from aimeth_dev.metrics import summarize, cell_types  # noqa: E402

SEEDS = list(range(1, 11))
FIXED_N = 3000
LESION_STEP = 200
ARMS = [
    ("full", {}, None),
    ("shuffled_signal", {"condition": "shuffled_signal"}, None),
    ("fixed_population", {"condition": "fixed_population"}, FIXED_N),
    ("frozen_expression", {"condition": "frozen_expression"}, None),
    ("task_blind", {"condition": "task_blind"}, None),
    ("full+lesion", {"lesion_step": LESION_STEP}, None),
    ("fixed_population+lesion", {"condition": "fixed_population", "lesion_step": LESION_STEP}, FIXED_N),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    base = Params()
    records, snaps_keep = [], {}
    t0 = time.time()
    for arm, overrides, fixed_n in ARMS:
        p = replace(base, **overrides)
        for seed in SEEDS:
            want = (100, 200, 201, 300) if seed == 1 else ()
            s, snaps = run(p, seed, fixed_n=fixed_n, snapshots=want)
            m = summarize(s, p, np.random.default_rng(10_000 + seed), 200)
            records.append({"arm": arm, "seed": seed, "params": params_dict(p), "fixed_n": fixed_n, "metrics": m})
            if seed == 1:
                snaps_keep[arm] = {k: cell_types(type("S", (), {"x": v["x"], "alive": v["alive"]})(), p).tolist()
                                   for k, v in snaps.items()}
    elapsed = time.time() - t0
    (out / "p1-records.json").write_text(json.dumps(records, indent=1, default=float))
    (out / "p1-snapshots-seed1.json").write_text(json.dumps(snaps_keep))
    manifest = {
        "created_unix": time.time(),
        "elapsed_seconds": elapsed,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform": platform.platform(),
        "source_sha256": {str(f.relative_to(ROOT)): sha256(f) for f in sorted((ROOT / "aimeth_dev").glob("*.py"))
                          + [ROOT / "tools/run_p1.py", ROOT / "docs/p1-offline-development-protocol-v1.md"]},
        "seeds": SEEDS,
        "arms": [a for a, _, _ in ARMS],
    }
    (out / "p1-manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"done {len(records)} runs in {elapsed:.1f}s -> {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "runs/p1-offline-v1"))
