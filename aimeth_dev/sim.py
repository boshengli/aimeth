"""Offline developmental simulator for AIMeth P1.

Lightweight computational cells live on a 2-D lattice. Every cell carries the
same small artificial genome; its expression vector is regulated by local
signals it senses. Division, differentiation and an expensive "large-model"
gene are all controlled by expression. No language model is called: the
expensive gene only records how often a real model call *would* happen, so
the cost structure of the two-tier design can be measured before any spend.

Everything is deterministic given ``seed``.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import numpy as np

GENES = ("GROW", "EMIT_A", "EMIT_I", "BORDER", "WORK", "EXPENSIVE")
G = {name: i for i, name in enumerate(GENES)}

CONDITIONS = (
    "full",               # local rules, real signals, division, task field
    "shuffled_signal",    # sensed signal values permuted among cells each step
    "fixed_population",   # same cell count placed at once, no division
    "frozen_expression",  # expression never updated after birth
    "task_blind",         # uniform task field (no task conditioning)
)


@dataclass
class Params:
    size: int = 96
    steps: int = 300
    max_cells: int = 5000          # resource ceiling on living cells
    seed_radius: int = 2
    alpha: float = 0.25            # expression relaxation rate
    noise: float = 0.02
    inherit_noise: float = 0.05
    # signal fields (Gierer-Meinhardt style: short-range A, long-range I)
    d_a: float = 0.02
    d_i: float = 0.20
    decay_a: float = 0.08
    decay_i: float = 0.04
    prod_a: float = 0.30
    prod_i: float = 0.40
    substeps: int = 4
    refractory: int = 4
    grow_threshold: float = 0.6
    expensive_threshold: float = 0.5
    call_refractory: int = 30      # steps between large-model calls of one cell
    cost_cheap: float = 1.0        # cost units per cell update
    cost_expensive: float = 1000.0 # cost units per large-model call
    lesion_step: int | None = None
    lesion_fraction_side: str = "right"
    condition: str = "full"
    vectorized_division: bool = False  # True for tissue-scale runs (one random direction per attempt)


@dataclass
class State:
    alive: np.ndarray
    x: np.ndarray        # (H, W, n_genes) expression in [0, 1]
    a: np.ndarray        # activator field
    i: np.ndarray        # inhibitor field
    clone: np.ndarray    # founder id, -1 when empty
    birth: np.ndarray    # step of birth
    last_div: np.ndarray
    task: np.ndarray     # task demand field in [0, 1]
    last_call: np.ndarray = None
    log: list = field(default_factory=list)
    expensive_calls: int = 0
    cheap_updates: int = 0
    births: int = 0
    deaths: int = 0


def _sig(z):
    return 1.0 / (1.0 + np.exp(-z))


def _lap(f):
    p = np.pad(f, 1, mode="edge")
    return p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:] - 4.0 * f


def _neigh_count(mask):
    p = np.pad(mask.astype(np.int8), 1)
    s = np.zeros(mask.shape, dtype=np.int8)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            if dy == 1 and dx == 1:
                continue
            s += p[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return s


def task_field(size: int, blind: bool) -> np.ndarray:
    """Two demand regions of different strength; uniform when blind."""
    if blind:
        return np.full((size, size), 0.5)
    yy, xx = np.mgrid[0:size, 0:size]
    c = size / 2
    f1 = np.exp(-(((yy - c) ** 2 + (xx - (c + size * 0.22)) ** 2) / (2 * (size * 0.10) ** 2)))
    f2 = 0.6 * np.exp(-(((yy - (c - size * 0.20)) ** 2 + (xx - (c - size * 0.15)) ** 2) / (2 * (size * 0.08) ** 2)))
    return np.clip(f1 + f2, 0, 1)


def init_state(p: Params, rng: np.random.Generator, fixed_n: int | None = None) -> State:
    n = p.size
    alive = np.zeros((n, n), dtype=bool)
    yy, xx = np.mgrid[0:n, 0:n]
    c = n // 2
    r2 = (yy - c) ** 2 + (xx - c) ** 2
    if fixed_n:
        order = np.argsort(r2 + rng.random(r2.shape) * 0.5, axis=None)[:fixed_n]
        alive.flat[order] = True
    else:
        alive[r2 <= p.seed_radius ** 2] = True
    x = np.zeros((n, n, len(GENES)))
    x[alive] = rng.random((alive.sum(), len(GENES))) * 0.3
    clone = np.full((n, n), -1, dtype=np.int32)
    clone[alive] = np.arange(alive.sum())
    birth = np.zeros((n, n), dtype=np.int32)
    return State(alive=alive, x=x, a=np.zeros((n, n)), i=np.zeros((n, n)),
                 clone=clone, birth=birth, last_div=np.full((n, n), -99, dtype=np.int32),
                 task=task_field(n, p.condition == "task_blind"),
                 last_call=np.full((n, n), -10**6, dtype=np.int64))


def _update_fields(s: State, p: Params):
    dt = 1.0 / p.substeps
    ea = s.x[..., G["EMIT_A"]] * s.alive
    ei = s.x[..., G["EMIT_I"]] * s.alive
    for _ in range(p.substeps):
        s.a += dt * (p.d_a * _lap(s.a) - p.decay_a * s.a + p.prod_a * ea * ea / (0.05 + s.i))
        s.i += dt * (p.d_i * _lap(s.i) - p.decay_i * s.i + p.prod_i * ea * ei)
        np.clip(s.a, 0, 50, out=s.a)
        np.clip(s.i, 0, 50, out=s.i)


def _targets(s: State, p: Params, rng: np.random.Generator):
    alive = s.alive
    dens = _neigh_count(alive) / 8.0
    edge = 1.0 - dens
    a, i = s.a.copy(), s.i.copy()
    if p.condition == "shuffled_signal":
        idx = np.flatnonzero(alive)
        perm = rng.permutation(idx)
        a.flat[idx] = s.a.flat[perm]
        i.flat[idx] = s.i.flat[perm]
    a_n = a / (1.0 + a)
    i_n = i / (1.0 + i)
    x = s.x
    t = np.zeros_like(x)
    t[..., G["EMIT_A"]] = _sig(10 * (a_n - i_n) + 4 * x[..., G["EMIT_A"]] - 2)
    t[..., G["EMIT_I"]] = _sig(8 * x[..., G["EMIT_A"]] - 4)
    t[..., G["BORDER"]] = _sig(12 * (edge - 0.35))
    t[..., G["WORK"]] = _sig(6 * s.task + 6 * a_n - 6 * x[..., G["BORDER"]] - 4)
    t[..., G["GROW"]] = _sig(7 * s.task + 6 * edge - 6 * dens - 1.5)
    # organizer-gated: only activator centres inside demand regions express it
    t[..., G["EXPENSIVE"]] = _sig(10 * x[..., G["EMIT_A"]] + 6 * s.task - 6 * x[..., G["BORDER"]] - 9)
    return t


def _divide_vec(s: State, p: Params, rng: np.random.Generator, step: int):
    """Vectorised division: each candidate tries one random neighbour; target conflicts
    are resolved by a random priority; births are truncated at the living-cell ceiling."""
    n = p.size
    cand = s.alive & (s.x[..., G["GROW"]] > p.grow_threshold) & (step - s.last_div >= p.refractory)
    ys, xs = np.nonzero(cand)
    room = p.max_cells - int(s.alive.sum())
    if len(ys) == 0 or room <= 0:
        return
    order = rng.permutation(len(ys))
    ys, xs = ys[order], xs[order]
    d = rng.integers(0, 4, len(ys))
    ny = ys + np.array([1, -1, 0, 0])[d]
    nx = xs + np.array([0, 0, 1, -1])[d]
    ok = (ny >= 0) & (ny < n) & (nx >= 0) & (nx < n)
    ys, xs, ny, nx = ys[ok], xs[ok], ny[ok], nx[ok]
    ok = ~s.alive[ny, nx]
    ys, xs, ny, nx = ys[ok], xs[ok], ny[ok], nx[ok]
    _, first = np.unique(ny * n + nx, return_index=True)
    first = np.sort(first)[:room]
    ys, xs, ny, nx = ys[first], xs[first], ny[first], nx[first]
    s.alive[ny, nx] = True
    s.x[ny, nx] = np.clip(s.x[ys, xs] + rng.normal(0, p.inherit_noise, (len(ys), len(GENES))), 0, 1)
    s.clone[ny, nx] = s.clone[ys, xs]
    s.birth[ny, nx] = step
    s.last_div[ny, nx] = step
    s.last_div[ys, xs] = step
    s.last_call[ny, nx] = s.last_call[ys, xs]
    s.births += len(ys)


def _divide(s: State, p: Params, rng: np.random.Generator, step: int):
    if p.condition == "fixed_population":
        return
    if p.vectorized_division:
        return _divide_vec(s, p, rng, step)
    n = p.size
    cand = s.alive & (s.x[..., G["GROW"]] > p.grow_threshold) & (step - s.last_div >= p.refractory)
    ys, xs = np.nonzero(cand)
    if len(ys) == 0:
        return
    order = rng.permutation(len(ys))
    dirs = np.array([(1, 0), (-1, 0), (0, 1), (0, -1)])
    living = int(s.alive.sum())
    for k in order:
        if living >= p.max_cells:
            break
        y, x0 = ys[k], xs[k]
        for d in rng.permutation(4):
            ny, nx = y + dirs[d][0], x0 + dirs[d][1]
            if 0 <= ny < n and 0 <= nx < n and not s.alive[ny, nx]:
                s.alive[ny, nx] = True
                s.x[ny, nx] = np.clip(s.x[y, x0] + rng.normal(0, p.inherit_noise, len(GENES)), 0, 1)
                s.clone[ny, nx] = s.clone[y, x0]
                s.birth[ny, nx] = step
                s.last_div[ny, nx] = step
                s.last_div[y, x0] = step
                s.last_call[ny, nx] = s.last_call[y, x0]
                s.births += 1
                living += 1
                break


def lesion(s: State, side: str = "right"):
    ys, xs = np.nonzero(s.alive)
    cx = xs.mean()
    kill = s.alive.copy()
    kill &= (np.arange(s.alive.shape[1])[None, :] > cx) if side == "right" else (np.arange(s.alive.shape[1])[None, :] < cx)
    s.deaths += int(kill.sum())
    s.alive[kill] = False
    s.x[kill] = 0
    s.clone[kill] = -1
    s.a[kill] = 0
    s.i[kill] = 0


def step_once(s: State, p: Params, rng: np.random.Generator, step: int):
    if p.lesion_step is not None and step == p.lesion_step:
        lesion(s, p.lesion_fraction_side)
    _update_fields(s, p)
    if p.condition != "frozen_expression":
        t = _targets(s, p, rng)
        upd = s.x + p.alpha * (t - s.x) + rng.normal(0, p.noise, s.x.shape)
        s.x = np.where(s.alive[..., None], np.clip(upd, 0, 1), 0)
    s.cheap_updates += int(s.alive.sum())
    fire = s.alive & (s.x[..., G["EXPENSIVE"]] > p.expensive_threshold) & (step - s.last_call >= p.call_refractory)
    s.last_call[fire] = step
    s.expensive_calls += int(fire.sum())
    _divide(s, p, rng, step)


def run(p: Params, seed: int, fixed_n: int | None = None, snapshots: tuple[int, ...] = ()):
    rng = np.random.default_rng(seed)
    s = init_state(p, rng, fixed_n=fixed_n)
    snaps = {}
    for step in range(p.steps):
        step_once(s, p, rng, step)
        if step + 1 in snapshots:
            snaps[step + 1] = {"alive": s.alive.copy(), "x": s.x.copy(), "clone": s.clone.copy()}
    return s, snaps


def params_dict(p: Params) -> dict:
    return asdict(p)
