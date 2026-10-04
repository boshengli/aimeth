"""Build, solve (baselines) and grade callus spatial-imputation tasks.

Task = (reference section with all genes visible, target section with a gene set
masked). Solvers see the target's visible genes + coordinates and the reference;
the masked target expression (the key) is written to a separate directory.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from .xenium import load_section, normalize_by_visible

MIN_VISIBLE_COUNTS = 10


def gene_annotation(path: Path) -> dict[str, dict]:
    with open(path, encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))[1:]
    return {r[0]: {"symbol": r[1], "group": r[2].strip(), "category": r[3].strip()} for r in rows}


def mask_sets(genes: list[str], ann: dict[str, dict], seed: int = 0) -> dict[str, list[str]]:
    imm = [g for g in genes if ann.get(g, {}).get("category") in ("Immunity&Regeneration", "PIN2")]
    cal = [g for g in genes if ann.get(g, {}).get("category") == "Callus_development"]
    rest = sorted(set(genes) - set(imm) - set(cal))
    rnd = sorted(np.random.default_rng(seed).choice(rest, 50, replace=False).tolist())
    return {"immunity_regeneration": imm, "callus_development": cal, "random50": rnd}


def _prep(ref, tgt, masked):
    gi = {g: i for i, g in enumerate(ref.genes)}
    assert ref.genes == tgt.genes
    m = np.array([gi[g] for g in masked])
    v = np.setdiff1d(np.arange(len(ref.genes)), m)
    R, rt = normalize_by_visible(ref.counts, v)
    T, tt = normalize_by_visible(tgt.counts, v)
    rk, tk = rt >= MIN_VISIBLE_COUNTS, tt >= MIN_VISIBLE_COUNTS
    return R[rk], T[tk], tgt.xy[tk], v, m, np.array(tgt.cell_ids)[tk]


def build_task(ref_dir, tgt_dir, masked, task_id, out_tasks: Path, out_keys: Path, meta: dict):
    ref, tgt = load_section(ref_dir), load_section(tgt_dir)
    R, T, xy, v, m, cells = _prep(ref, tgt, masked)
    out_tasks.mkdir(parents=True, exist_ok=True)
    out_keys.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_tasks / f"{task_id}.npz", ref_visible=R[:, v], ref_masked=R[:, m],
                        tgt_visible=T[:, v], tgt_xy=xy, tgt_cells=cells,
                        visible_genes=np.array(ref.genes)[v], masked_genes=np.array(ref.genes)[m])
    np.savez_compressed(out_keys / f"{task_id}.key.npz", tgt_masked=T[:, m], masked_genes=np.array(ref.genes)[m])
    info = dict(meta, task_id=task_id, n_ref_cells=int(len(R)), n_tgt_cells=int(len(T)),
                n_visible=int(len(v)), n_masked=int(len(m)))
    (out_tasks / f"{task_id}.json").write_text(json.dumps(info, indent=1))
    return info


# ---------- solvers (no language model) ----------

def solve_ridge(t, alpha: float = 10.0):
    X, Y = t["ref_visible"], t["ref_masked"]
    mu_x, mu_y = X.mean(0), Y.mean(0)
    Xc = X - mu_x
    W = np.linalg.solve(Xc.T @ Xc + alpha * np.eye(X.shape[1]), Xc.T @ (Y - mu_y))
    return (t["tgt_visible"] - mu_x) @ W + mu_y


def solve_knn_expression(t, k: int = 15, n_pc: int = 30):
    X = t["ref_visible"]
    mu = X.mean(0)
    _, _, vt = np.linalg.svd(X - mu, full_matrices=False)
    P = vt[:n_pc].T
    _, idx = cKDTree((X - mu) @ P).query((t["tgt_visible"] - mu) @ P, k=k)
    return t["ref_masked"][idx].mean(1)


def spatial_smooth(pred, xy, k: int = 10):
    _, idx = cKDTree(xy).query(xy, k=k)
    return pred[idx].mean(1)


SOLVERS = {
    "ridge": lambda t: solve_ridge(t),
    "knn_expr": lambda t: solve_knn_expression(t),
    "ridge+spatial": lambda t: spatial_smooth(solve_ridge(t), t["tgt_xy"]),
}


# ---------- grading ----------

def _corr_cols(a, b):
    a = a - a.mean(0)
    b = b - b.mean(0)
    den = np.sqrt((a * a).sum(0) * (b * b).sum(0))
    out = np.where(den > 0, (a * b).sum(0) / np.where(den > 0, den, 1), 0.0)
    return out


def grade(pred, key, xy, k_pattern: int = 10):
    truth = key["tgt_masked"]
    informative = truth.std(0) > 0
    cell_r = _corr_cols(pred, truth)
    pat_r = _corr_cols(spatial_smooth(pred, xy, k_pattern), spatial_smooth(truth, xy, k_pattern))
    genes = key["masked_genes"]
    return {
        "n_genes": int(len(genes)), "n_informative": int(informative.sum()),
        "cell_r_mean": float(cell_r[informative].mean()) if informative.any() else 0.0,
        "pattern_r_mean": float(pat_r[informative].mean()) if informative.any() else 0.0,
        "per_gene": {str(g): {"cell_r": float(c), "pattern_r": float(p), "informative": bool(i)}
                     for g, c, p, i in zip(genes, cell_r, pat_r, informative)},
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
