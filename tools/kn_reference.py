"""Measured gene-gene co-expression reference for scoring language-model knowledge priors.

Usage: python tools/kn_reference.py DATA_ROOT OUT.npz
Uses the eight single-sample wild-type callus slices of the imputation benchmark (3, 12, 15 days).
Per slice: cells with >= 10 panel counts, log1p(count / total * 100); Pearson correlation across cells
("cell") and after averaging each cell with its 10 nearest spatial neighbours ("smooth", tissue pattern
scale). Slice matrices are averaged with equal weight; per-slice matrices are kept for split-half checks.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_bio.xenium import load_section  # noqa: E402

WT = {
    "WT-3D-1": "output-XETG00521__0032595__WT-3D-1__20251101__091015",
    "WT-3D-2": "output-XETG00521__0032587__WT-3D-2__20251101__091015",
    "WT-12D-1": "output-XETG00521__0032595__WT-12D-1__20251101__091015",
    "WT-12D-2": "output-XETG00521__0032595__WT-12D-2__20251101__091015",
    "WT-12D-3": "output-XETG00521__0032587__WT-12D-3__20251101__091015",
    "WT-15D-1": "output-XETG00521__0032595__WT-15D-1__20251101__091015",
    "WT-15D-2": "output-XETG00521__0032595__WT-15D-2__20251101__091015",
    "WT-15D-3": "output-XETG00521__0032587__WT-15D-3__20251101__091015",
}


def corr(X: np.ndarray) -> np.ndarray:
    X = X.astype(np.float64)
    X = X - X.mean(0)
    s = np.sqrt((X ** 2).sum(0))
    s[s == 0] = np.nan
    return (X.T @ X) / np.outer(s, s)


def smooth(X: np.ndarray, xy: np.ndarray, k: int = 10, chunk: int = 20000) -> np.ndarray:
    _, idx = cKDTree(xy).query(xy, k=k)
    out = np.empty_like(X)
    for a in range(0, len(X), chunk):
        out[a:a + chunk] = X[idx[a:a + chunk]].mean(1)
    return out


def main(data_root: Path, out: Path):
    genes, names, Rc, Rs, ncell = None, [], [], [], []
    for name, d in WT.items():
        t0 = time.time()
        sec = load_section(data_root / d, name)
        if genes is None:
            genes = sec.genes
        assert sec.genes == genes, name
        tot = sec.counts.sum(1)
        keep = tot >= 10
        X = np.log1p(sec.counts[keep] / tot[keep, None] * 100.0).astype(np.float32)
        xy = sec.xy[keep]
        Rc.append(corr(X))
        Rs.append(corr(smooth(X, xy)))
        names.append(name)
        ncell.append(int(keep.sum()))
        print(name, ncell[-1], f"{time.time() - t0:.0f}s", flush=True)
    Rc, Rs = np.stack(Rc), np.stack(Rs)
    np.savez_compressed(out, genes=np.array(genes), slices=np.array(names), n_cells=np.array(ncell),
                        R_cell=np.nanmean(Rc, 0), R_smooth=np.nanmean(Rs, 0), R_cell_slices=Rc.astype(np.float32),
                        R_smooth_slices=Rs.astype(np.float32))
    print(json.dumps({"out": str(out), "genes": len(genes), "slices": names, "n_cells": ncell}))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
