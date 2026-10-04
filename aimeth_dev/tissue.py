"""Tissue-scale read-outs: mesoscopic units built from organiser domains.

A mesoscopic unit is a 4-connected component of interior activator-on cells
(an organiser domain). A tissue is a population containing many such units.
Spacing regularity uses the Clark-Evans ratio R (mean nearest-neighbour
distance over its expectation for random points at the same density), with a
null that places the same number of points on random living cells.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from .sim import G, State


def organizer_units(s: State, min_size: int = 3):
    interior = s.alive & (s.x[..., G["BORDER"]] < 0.5)
    on = interior & (s.x[..., G["EMIT_A"]] > 0.5)
    lab, n = ndimage.label(on)
    if n == 0:
        return np.zeros((0, 2)), np.zeros(0, int)
    sizes = ndimage.sum_labels(on, lab, index=np.arange(1, n + 1)).astype(int)
    cents = np.array(ndimage.center_of_mass(on, lab, index=np.arange(1, n + 1)))
    keep = sizes >= min_size
    return cents[keep], sizes[keep]


def _mean_nn(points: np.ndarray) -> float:
    d, _ = cKDTree(points).query(points, k=2)
    return float(d[:, 1].mean())


def clark_evans(s: State, rng: np.random.Generator, n_null: int = 200, min_size: int = 3) -> dict:
    cents, sizes = organizer_units(s, min_size)
    k = len(cents)
    area = float(s.alive.sum())
    out = {"units": int(k), "unit_size_median": float(np.median(sizes)) if k else 0.0,
           "unit_size_p90": float(np.quantile(sizes, 0.9)) if k else 0.0}
    if k < 5:
        out.update({"R": float("nan"), "R_null_p95": float("nan"), "R_null_mean": float("nan")})
        return out
    expected = 0.5 / np.sqrt(k / area)
    r_obs = _mean_nn(cents) / expected
    ys, xs = np.nonzero(s.alive)
    null = np.empty(n_null)
    for j in range(n_null):
        pick = rng.choice(len(ys), size=k, replace=False)
        null[j] = _mean_nn(np.c_[ys[pick], xs[pick]].astype(float)) / expected
    out.update({"R": float(r_obs), "R_null_mean": float(null.mean()), "R_null_p95": float(np.quantile(null, 0.95)),
                "R_exceeds_null_fraction": float((null < r_obs).mean())})
    return out


def domain_units(s: State, rng: np.random.Generator, min_size: int = 100, n_null: int = 200) -> dict:
    """Mesoscopic domains (P1 v2): 4-connected components of living domain-on cells (dom > 0.5)
    with at least `min_size` cells, plus Clark-Evans spacing of their centroids."""
    if s.dom is None:
        return {"units": 0}
    on = s.alive & (s.dom > 0.5)
    lab, n = ndimage.label(on)
    out = {"on_fraction": float(on.sum() / max(s.alive.sum(), 1))}
    if n == 0:
        out.update(units=0, size_median=0.0, size_p90=0.0, largest_fraction=0.0, R=float("nan"),
                   R_null_p95=float("nan"))
        return out
    sizes = ndimage.sum_labels(on, lab, index=np.arange(1, n + 1)).astype(int)
    keep = np.flatnonzero(sizes >= min_size)
    out["largest_fraction"] = float(sizes.max() / max(s.alive.sum(), 1))
    out["units"] = int(len(keep))
    out["size_median"] = float(np.median(sizes[keep])) if len(keep) else 0.0
    out["size_p90"] = float(np.quantile(sizes[keep], 0.9)) if len(keep) else 0.0
    if len(keep) < 5:
        out.update(R=float("nan"), R_null_p95=float("nan"))
        return out
    cents = np.array(ndimage.center_of_mass(on, lab, index=keep + 1))
    k, area = len(cents), float(s.alive.sum())
    expected = 0.5 / np.sqrt(k / area)
    r_obs = _mean_nn(cents) / expected
    ys, xs = np.nonzero(s.alive)
    null = np.array([_mean_nn(np.c_[ys[p], xs[p]].astype(float)) / expected
                     for p in (rng.choice(len(ys), size=k, replace=False) for _ in range(n_null))])
    out.update(R=float(r_obs), R_null_mean=float(null.mean()), R_null_p95=float(np.quantile(null, 0.95)))
    return out
