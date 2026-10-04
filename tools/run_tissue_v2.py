"""Tissue-scale P1 runs on a multi-core node.

Usage: python tools/run_tissue.py OUTDIR [N_PROCS]
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
import time
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aimeth_dev.sim import Params, run, params_dict  # noqa: E402
from aimeth_dev.metrics import summarize, cell_types  # noqa: E402
from aimeth_dev.tissue import clark_evans, domain_units  # noqa: E402

BASE = Params(size=1100, steps=5000, max_cells=1_000_000, vectorized_division=True)
ARMS = {
    "v1_rules": {},
    "community": {"domain_mechanism": "community"},
    "two_scale": {"domain_mechanism": "two_scale"},
    "two_scale_L50": {"domain_mechanism": "two_scale", "sigma_l": 50.0},
    "two_scale+shuffled": {"domain_mechanism": "two_scale", "condition": "shuffled_signal"},
    "two_scale+lesion": {"domain_mechanism": "two_scale", "lesion_step": 4000},
}
SEEDS = [11, 12, 13, 14, 15]  # tuning used seed 1 only


def one(job):
    arm, seed, out = job
    p = replace(BASE, **ARMS[arm])
    t = time.time()
    s, _ = run(p, seed)
    sim_s = time.time() - t
    rng = np.random.default_rng(20_000 + seed)
    m = summarize(s, p, rng, 100)
    m["tissue"] = clark_evans(s, rng, 200)
    m["domains"] = domain_units(s, rng, 100, 200)
    m["sim_seconds"] = sim_s
    if seed == SEEDS[0]:
        np.savez_compressed(Path(out) / f"types-{arm}-seed{seed}.npz", types=cell_types(s, p), dom=(s.dom > 0.5))
    rec = {"arm": arm, "seed": seed, "params": params_dict(p), "metrics": m}
    (Path(out) / f"rec-{arm}-seed{seed}.json").write_text(json.dumps(rec, default=float))
    return arm, seed, sim_s


def main(out: Path, procs: int):
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(a, sd, str(out)) for a in ARMS for sd in SEEDS]
    manifest = {
        "started_unix": time.time(), "python": platform.python_version(), "numpy": np.__version__,
        "host": platform.node(),
        "source_sha256": {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
                          for f in sorted((ROOT / "aimeth_dev").glob("*.py")) + [ROOT / "tools/run_tissue_v2.py",
                                                                                  ROOT / "docs/p1-v2-mesoscopic-domains-protocol.md"]},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    with Pool(procs) as pool:
        for arm, seed, sim_s in pool.imap_unordered(one, jobs):
            print(f"{time.strftime('%H:%M:%S')} done {arm} seed {seed} sim {sim_s:.0f}s", flush=True)
    manifest["finished_unix"] = time.time()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 20)
