"""Minimal Xenium loader (cell_feature_matrix.h5 + cells.csv.gz)."""
from __future__ import annotations

import csv
import gzip
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class Section:
    name: str
    genes: list[str]          # Solyc ids, Gene Expression features only
    counts: np.ndarray        # cells x genes, float32 raw counts
    xy: np.ndarray            # cells x 2, microns
    cell_ids: list[str]


def load_section(path: Path, name: str | None = None) -> Section:
    import h5py

    path = Path(path)
    with h5py.File(path / "cell_feature_matrix.h5", "r") as f:
        m = f["matrix"]
        n_feat, n_cell = (int(v) for v in m["shape"][:])
        data, ind, ptr = m["data"][:], m["indices"][:], m["indptr"][:]
        ftype = [t.decode() for t in m["features/feature_type"][:]]
        fid = [t.decode() for t in m["features/id"][:]]
        barcodes = [b.decode() for b in m["barcodes"][:]]
    dense = np.zeros((n_cell, n_feat), dtype=np.float32)
    for j in range(n_cell):  # CSC: columns are cells
        dense[j, ind[ptr[j]:ptr[j + 1]]] = data[ptr[j]:ptr[j + 1]]
    keep = [i for i, t in enumerate(ftype) if t == "Gene Expression"]
    pos = {}
    with gzip.open(path / "cells.csv.gz", "rt") as fh:
        for row in csv.DictReader(fh):
            pos[row["cell_id"]] = (float(row["x_centroid"]), float(row["y_centroid"]))
    xy = np.array([pos[b] for b in barcodes], dtype=np.float32)
    return Section(name or path.name, [fid[i] for i in keep], dense[:, keep], xy, barcodes)


def normalize_by_visible(counts: np.ndarray, visible: np.ndarray, scale: float = 100.0):
    """log1p(count / visible_total * scale). Library size uses visible genes only, so
    masked genes cannot leak through the normalisation factor."""
    tot = counts[:, visible].sum(1, keepdims=True)
    return np.log1p(counts / np.maximum(tot, 1.0) * scale), tot.ravel()
