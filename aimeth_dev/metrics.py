"""Structure, regulation and cost measurements for P1 populations.

Structure is always compared against a permutation null that keeps the
shape of the population and its type composition but shuffles which cell
holds which type, so a pattern only counts when it is spatially organised
beyond what composition and outline alone would produce.
"""
from __future__ import annotations

import numpy as np

from .sim import G, State, Params

TYPE_NAMES = ("border", "worker", "expensive", "other")


def cell_types(s: State, p: Params) -> np.ndarray:
    """Discrete type per lattice site (-1 = empty)."""
    x = s.x
    t = np.full(s.alive.shape, 3, dtype=np.int8)
    t[x[..., G["WORK"]] > 0.5] = 1
    t[x[..., G["EXPENSIVE"]] > p.expensive_threshold] = 2
    t[x[..., G["BORDER"]] > 0.5] = 0
    t[~s.alive] = -1
    return t


def _pairs(alive: np.ndarray):
    h = alive[:, :-1] & alive[:, 1:]
    v = alive[:-1, :] & alive[1:, :]
    return h, v


def same_label_fraction(labels: np.ndarray, alive: np.ndarray) -> float:
    h, v = _pairs(alive)
    same = (labels[:, :-1] == labels[:, 1:])[h].sum() + (labels[:-1, :] == labels[1:, :])[v].sum()
    total = h.sum() + v.sum()
    return float(same / total) if total else float("nan")


def permutation_z(labels: np.ndarray, alive: np.ndarray, rng: np.random.Generator, n_perm: int = 200):
    obs = same_label_fraction(labels, alive)
    idx = np.flatnonzero(alive)
    vals = labels.flat[idx].copy()
    null = np.empty(n_perm)
    shuffled = labels.copy()
    for k in range(n_perm):
        shuffled.flat[idx] = rng.permutation(vals)
        null[k] = same_label_fraction(shuffled, alive)
    sd = null.std()
    z = (obs - null.mean()) / sd if sd > 0 else 0.0
    return {"observed": obs, "null_mean": float(null.mean()), "null_sd": float(sd), "z": float(z)}


def radial_mutual_information(types: np.ndarray, alive: np.ndarray, n_bins: int = 6) -> float:
    ys, xs = np.nonzero(alive)
    if len(ys) < 10:
        return float("nan")
    r = np.hypot(ys - ys.mean(), xs - xs.mean())
    bins = np.minimum((r / (r.max() + 1e-9) * n_bins).astype(int), n_bins - 1)
    t = types[ys, xs]
    joint = np.zeros((n_bins, 4))
    np.add.at(joint, (bins, t), 1)
    joint /= joint.sum()
    pb, pt = joint.sum(1, keepdims=True), joint.sum(0, keepdims=True)
    nz = joint > 0
    return float((joint[nz] * np.log2(joint[nz] / (pb @ pt)[nz])).sum())


def task_alignment(s: State) -> float:
    """Correlation between worker expression and local task demand."""
    if not s.alive.any():
        return float("nan")
    w = s.x[..., G["WORK"]][s.alive]
    d = s.task[s.alive]
    if w.std() == 0 or d.std() == 0:
        return 0.0
    return float(np.corrcoef(w, d)[0, 1])


def demand_coverage(s: State) -> float:
    """Share of total task demand that sits under a worker cell."""
    workers = s.alive & (s.x[..., G["WORK"]] > 0.5)
    return float(s.task[workers].sum() / s.task.sum())


def organizer_pattern(s: State, rng: np.random.Generator, n_perm: int = 200) -> dict:
    """Self-organised activator centres among interior (non-border) cells.

    Border and task-driven worker identity follow external cues (edge density,
    task field). Activator centres can only arise from cell-cell signalling,
    so their clustering is the cleanest read-out of self-organised structure.
    """
    interior = s.alive & (s.x[..., G["BORDER"]] < 0.5)
    on = (s.x[..., G["EMIT_A"]] > 0.5).astype(np.int8)
    n_int = int(interior.sum())
    frac = float(on[interior].mean()) if n_int else float("nan")
    if n_int < 20 or frac in (0.0, 1.0):
        return {"interior_cells": n_int, "on_fraction": frac, "z": 0.0}
    z = permutation_z(on, interior, rng, n_perm)["z"]
    return {"interior_cells": n_int, "on_fraction": frac, "z": float(z)}


def summarize(s: State, p: Params, rng: np.random.Generator, n_perm: int = 200) -> dict:
    types = cell_types(s, p)
    alive = s.alive
    n = int(alive.sum())
    comp = {name: int((types == k).sum()) for k, name in enumerate(TYPE_NAMES)}
    struct = permutation_z(types, alive, rng, n_perm) if n > 20 else None
    clone = permutation_z(s.clone, alive, rng, n_perm) if n > 20 else None
    cost_cheap = s.cheap_updates * p.cost_cheap
    cost_exp = s.expensive_calls * p.cost_expensive
    return {
        "cells": n,
        "clones": int(len(np.unique(s.clone[alive]))) if n else 0,
        "births": s.births,
        "deaths": s.deaths,
        "composition": comp,
        "type_assortativity": struct,
        "organizer": organizer_pattern(s, rng, n_perm),
        "expensive_calls_per_1000_cell_steps": 1000.0 * s.expensive_calls / s.cheap_updates if s.cheap_updates else float("nan"),
        "clone_coherence": clone,
        "radial_type_mi_bits": radial_mutual_information(types, alive) if n > 20 else None,
        "task_alignment_r": task_alignment(s),
        "demand_coverage": demand_coverage(s),
        "expensive_fraction_final": comp["expensive"] / n if n else float("nan"),
        "expensive_calls": s.expensive_calls,
        "cheap_updates": s.cheap_updates,
        "expensive_cost_share": cost_exp / (cost_exp + cost_cheap) if (cost_exp + cost_cheap) else float("nan"),
        "all_expensive_equivalent_calls": s.cheap_updates,
    }
