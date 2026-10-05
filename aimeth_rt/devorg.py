"""Developmental organisation arm for ARC (P2, DevOrg-ARC v0).

A population of program-cells grows on a small lattice from two founder cells. Cells are cheap: their state is a
candidate `transform` program and its training-pair results; their genes are rule-based and run without a model:

  TRANSFER  copy a strictly better program from a neighbour (diffusion of good solutions)
  MUTATE    colour-literal substitution, output re-orientation (explorer behaviour, low fitness)
  REFINE    learn a colour remap from the program's own training outputs; compose with a neighbour's program
  DIVIDE    a variant that beats its parent is placed in a daughter cell (empty neighbour slot, or replaces a
            weaker neighbour); lineage is recorded
  DIE       a cell stuck at zero fitness next to better cells for several steps is removed
  EXPENSIVE the language model, expressed only at organiser cells - local maxima of a short-range activator
            (neighbourhood fitness) minus a long-range inhibitor - whose neighbourhood has stagnated, with a
            refractory period. The model sees the cell's program, its failures, and up to two neighbouring programs
            chosen to cover training pairs the cell fails (complementary specialists).

Budget contract (same as every P2 arm): at most `calls` model calls and `tokens` completion tokens; per-call
max_tokens = min(per_call_cap, tokens left). Stops early on a train-perfect program. Final answer = highest training
fitness, ties broken by clone size then age. Only visible information is used (training pairs; test outputs never
leave the evaluation service).

Knock-outs for H2 (mechanism): no_division, no_cheap, shuffled_organiser (expensive gene at a random cell),
well_mixed (every cell is every other cell's neighbour).
"""
from __future__ import annotations

import hashlib
import json
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import re

import numpy as np

from . import cheap_genes as CG
from .workflows import ARC_SYSTEM, arc_user_prompt, extract_arc, _g


@dataclass
class Params:
    size: int = 6
    founders: int = 2
    calls: int = 8
    tokens: int = 262_144
    per_call_cap: int = 32_768
    max_steps: int = 40
    stagnation: int = 2
    refractory: int = 3
    max_inflight: int = 2
    die_after: int = 4
    sigma_a: float = 1.0
    sigma_i: float = 2.5
    k_inhib: float = 0.5
    wall_s: float = 3600.0
    knockout: str = "none"   # none | no_division | no_cheap | shuffled_organiser | well_mixed
    seed: int = 1000


@dataclass
class Cell:
    cid: int
    parent: int | None
    pos: tuple
    born: int
    program: str | None = None
    sha: str | None = None
    origin: str = ""
    last_improve: int = 0
    refractory_until: int = 0
    zero_steps: int = 0


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _blur(grid: np.ndarray, sigma: float) -> np.ndarray:
    n = grid.shape[0]
    ys, xs = np.mgrid[0:n, 0:n]
    out = np.zeros_like(grid, dtype=float)
    w = np.zeros_like(grid, dtype=float)
    for y in range(n):
        for x in range(n):
            k = np.exp(-((ys - y) ** 2 + (xs - x) ** 2) / (2 * sigma ** 2))
            out[y, x] = (k * grid).sum()
            w[y, x] = k.sum()
    return out / w


class DevOrg:
    def __init__(self, task_id: str, task: dict, llm, ev, p: Params, *, provider: str, model: str,
                 extra: dict | None, arc_dir: str, tag: dict):
        self.task_id, self.task, self.llm, self.ev, self.p = task_id, task, llm, ev, p
        self.provider, self.model, self.extra, self.arc_dir, self.tag = provider, model, extra, arc_dir, tag
        self.rng = random.Random(p.seed)
        self.grid: dict[tuple, Cell] = {}
        self.next_id = 0
        self.step = 0
        self.evals: dict[str, dict] = {}          # sha -> visible eval result
        self.calls_used, self.tokens_used = 0, 0
        self.inflight: dict[int, object] = {}     # cell id -> future
        self.events, self.snapshots = [], []
        self.lock = threading.Lock()
        self.palette = CG.task_palette(task)
        self.npairs = len(task["train"])
        self.pool = ThreadPoolExecutor(p.max_inflight)

    # ------------------------------------------------------------------ helpers
    def fit(self, c: Cell) -> float:
        e = self.evals.get(c.sha) if c.sha else None
        return e["train_frac"] if e and e.get("status") == "ok" else (-0.01 if c.program else -0.02)

    def ok_vec(self, c: Cell) -> list[bool]:
        e = self.evals.get(c.sha) if c.sha else None
        return [t["ok"] for t in e["train"]] if e and e.get("status") == "ok" else [False] * self.npairs

    def neighbours(self, pos, radius=1):
        if self.p.knockout == "well_mixed":
            return [q for q in self.grid if q != pos]
        y, x = pos
        out = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                q = (y + dy, x + dx)
                if q != pos and q in self.grid:
                    out.append(q)
        return out

    def empty_neighbour(self, pos):
        y, x = pos
        n = self.p.size
        free = [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy or dx) and 0 <= y + dy < n and 0 <= x + dx < n and (y + dy, x + dx) not in self.grid]
        if self.p.knockout == "well_mixed":
            free = [(a, b) for a in range(n) for b in range(n) if (a, b) not in self.grid]
        return self.rng.choice(free) if free else None

    def new_cell(self, pos, parent, program, origin) -> Cell:
        c = Cell(self.next_id, parent, pos, self.step, program, sha(program) if program else None, origin,
                 last_improve=self.step)
        self.next_id += 1
        self.grid[pos] = c
        return c

    def evaluate(self, programs: list[str]):
        todo = {}
        for s in programs:
            h = sha(s)
            if h not in self.evals and h not in todo:
                todo[h] = s
        ids = {h: self.ev.submit("arc", self.task_id, s, arc_dir=self.arc_dir) for h, s in todo.items()}
        for h, jid in ids.items():
            r = self.ev.wait(jid)
            r["eval_id"] = jid
            self.evals[h] = r

    # ------------------------------------------------------------------ expensive gene
    def _prompt(self, c: Cell) -> tuple[list[dict], str, list[str]]:
        base = [{"role": "system", "content": ARC_SYSTEM}, {"role": "user", "content": arc_user_prompt(self.task)}]
        if not c.program or c.sha not in self.evals:
            return base, "fresh", []
        mine = self.ok_vec(c)
        cand = []
        for q in self.neighbours(c.pos, radius=2):
            d = self.grid[q]
            if d.program and d.sha != c.sha and d.sha in self.evals and self.evals[d.sha].get("status") == "ok":
                gain = sum(a and not b for a, b in zip(self.ok_vec(d), mine))
                cand.append((gain, self.fit(d), d))
        cand.sort(key=lambda t: (-t[0], -t[1]))
        chosen, seen = [], set()
        for gain, f, d in cand:
            if d.sha in seen:
                continue
            chosen.append(d)
            seen.add(d.sha)
            if len(chosen) == 2:
                break
        parts = ["Candidate programs from this region of the population, with their results on the training pairs:"]
        for label, d in [("A (this cell)", c)] + [(f"{chr(66 + i)} (neighbour)", d) for i, d in enumerate(chosen)]:
            e = self.evals[d.sha]
            parts.append(f"\n--- Program {label} ---\n```python\n{d.program}\n```")
            if e.get("status") != "ok":
                parts.append(f"Result: could not run ({e.get('status')}: {str(e.get('detail', ''))[:300]})")
                continue
            res = []
            for i, (pair, t) in enumerate(zip(self.task["train"], e["train"]), 1):
                if t["ok"]:
                    res.append(f"pair {i}: correct")
                elif t.get("error"):
                    res.append(f"pair {i}: raised {t['error'][:200]}")
                else:
                    res.append(f"pair {i}: wrong")
            parts.append("Result: " + "; ".join(res))
        own = self.evals[c.sha]
        if own.get("status") == "ok":
            for i, (pair, t) in enumerate(zip(self.task["train"], own["train"]), 1):
                if not t["ok"] and t.get("got") is not None:
                    parts.append(f"\nProgram A on pair {i}: expected {_g(pair['output'])}\n  got {_g(t['got'])}")
                    break
        parts.append("\nUsing what each candidate gets right, write ONE new general program that solves every "
                     "training pair. Return only the complete Python program.")
        msgs = [base[0], {"role": "user", "content": base[1]["content"] + "\n\n" + "\n".join(parts)}]
        return msgs, "integrate", [d.sha for d in chosen]

    def _call(self, cell_id: int, msgs: list[dict], kind: str, max_tokens: int):
        rec = self.llm.call(self.provider, self.model, msgs, workload="rt_arc_devorg", max_tokens=max_tokens,
                            extra=self.extra, tag={**self.tag, "cell": cell_id, "kind": kind, "step": self.step})
        content = rec.get("content") if rec.get("ok") else None
        if rec.get("ok") and not (content or "").strip() and rec.get("reasoning_content"):
            blocks = [b for b in re.findall(r"```(?:python)?\s*\n(.*?)```", rec["reasoning_content"], flags=re.S)
                      if "def transform" in b]
            if blocks:
                content = "```python\n" + blocks[-1] + "```"
        return rec, extract_arc(content)

    def express_expensive(self):
        if self.calls_used >= self.p.calls or self.tokens_used >= self.p.tokens:
            return
        if len(self.inflight) >= self.p.max_inflight:
            return
        cells = list(self.grid.values())
        n = self.p.size
        F = np.zeros((n, n))
        occ = np.zeros((n, n))
        for c in cells:
            F[c.pos] = max(self.fit(c), 0.0)
            occ[c.pos] = 1
        A = _blur(F, self.p.sigma_a)
        I = _blur(F, self.p.sigma_i)
        O = A - self.p.k_inhib * I
        busy = {self.grid_pos_of(cid) for cid in self.inflight}
        cand = []
        for c in cells:
            if c.refractory_until > self.step or c.cid in self.inflight:
                continue
            if any(q in busy for q in self.neighbours(c.pos)) or c.pos in busy:
                continue
            nb = self.neighbours(c.pos)
            stagn = self.step - max([c.last_improve] + [self.grid[q].last_improve for q in nb]) >= self.p.stagnation
            local_max = all(O[c.pos] >= O[q] for q in nb)
            if (stagn and local_max) or c.program is None:
                cand.append(c)
        if self.p.knockout == "shuffled_organiser" and cand:
            cand = [self.rng.choice(cells)]
        if not cand:
            return
        c = max(cand, key=lambda c: (c.program is None, O[c.pos], self.fit(c)))
        msgs, kind, partners = self._prompt(c)
        max_tokens = min(self.p.per_call_cap, self.p.tokens - self.tokens_used)
        self.calls_used += 1
        self.tokens_used += max_tokens  # reserve; corrected when the call returns
        c.refractory_until = self.step + self.p.refractory
        fut = self.pool.submit(self._call, c.cid, msgs, kind, max_tokens)
        self.inflight[c.cid] = (fut, max_tokens, kind, partners, self.step)
        self.events.append({"step": self.step, "event": "expensive_start", "cell": c.cid, "pos": c.pos, "kind": kind,
                            "partners": [p[:8] for p in partners], "max_tokens": max_tokens})

    def grid_pos_of(self, cid):
        for pos, c in self.grid.items():
            if c.cid == cid:
                return pos
        return None

    def collect_expensive(self) -> list[str]:
        new = []
        for cid, (fut, reserved, kind, partners, s0) in list(self.inflight.items()):
            if not fut.done():
                continue
            del self.inflight[cid]
            rec, prog = fut.result()
            used = (rec.get("usage") or {}).get("completion_tokens")
            self.tokens_used += (used if used is not None else reserved) - reserved
            pos = self.grid_pos_of(cid)
            ev = {"step": self.step, "event": "expensive_done", "cell": cid, "kind": kind,
                  "receipt_id": rec.get("receipt_id"), "ok": rec.get("ok"), "completion_tokens": used,
                  "finish": rec.get("finish_reason"), "program": sha(prog)[:12] if prog else None}
            self.events.append(ev)
            if prog and pos is not None:
                new.append((pos, cid, prog))
        if not new:
            return []
        self.evaluate([p for _, _, p in new])
        placed = []
        for pos, cid, prog in new:
            parent = self.grid.get(pos)
            pf = self.fit(parent) if parent and parent.cid == cid else -1
            nf = self.evals[sha(prog)].get("train_frac", -0.01) if self.evals[sha(prog)].get("status") == "ok" else -0.01
            if parent is not None and parent.cid == cid and (parent.program is None or nf > pf):
                parent.program, parent.sha, parent.origin = prog, sha(prog), "llm"
                parent.last_improve = self.step
                placed.append(parent.cid)
            else:
                slot = self.empty_neighbour(pos) if parent else pos
                if slot is not None and self.p.knockout != "no_division":
                    d = self.new_cell(slot, cid, prog, "llm")
                    placed.append(d.cid)
        return placed

    # ------------------------------------------------------------------ cheap genes
    def propose_cheap(self, c: Cell) -> list[tuple[str, str]]:
        if self.p.knockout == "no_cheap" or not c.program or c.sha not in self.evals:
            return []
        e = self.evals[c.sha]
        f = self.fit(c)
        out = []
        if e.get("status") == "ok" and 0 <= f < 1:
            m = CG.learn_color_map(c.program, self.task, e["train"])
            if m:
                out.append((m, "colormap"))
            if f == 0:
                for s in CG.color_literals(c.program, self.palette, self.rng, k=1):
                    out.append((s, "color"))
                op = self.rng.choice(list(CG.WRAPS))
                w = CG.wrap_output(c.program, op)
                if w:
                    out.append((w, "wrap:" + op))
            nb = [self.grid[q] for q in self.neighbours(c.pos) if self.grid[q].program and self.grid[q].sha != c.sha]
            nb = [d for d in nb if self.fit(d) > 0]
            if nb:
                d = self.rng.choice(nb)
                comp = CG.compose(d.program, c.program) if self.rng.random() < 0.5 else CG.compose(c.program, d.program)
                if comp:
                    out.append((comp, "compose"))
        return out[:2]

    def transfer(self):
        moved = 0
        for c in list(self.grid.values()):
            nb = [self.grid[q] for q in self.neighbours(c.pos)]
            better = [d for d in nb if d.program and self.fit(d) > self.fit(c) + 1e-9]
            if better and self.rng.random() < 0.5:
                d = max(better, key=self.fit)
                c.program, c.sha, c.origin = d.program, d.sha, f"transfer:{d.cid}"
                moved += 1  # copying an existing program is not a neighbourhood improvement
        return moved

    def divide_and_die(self, proposals):
        placed = 0
        for c, prog, op in proposals:
            h = sha(prog)
            e = self.evals.get(h)
            if not e or e.get("status") != "ok" or e["train_frac"] <= self.fit(c):
                continue
            if self.p.knockout == "no_division":
                c.program, c.sha, c.origin = prog, h, op
                c.last_improve = self.step
                placed += 1
                continue
            slot = self.empty_neighbour(c.pos)
            if slot is None:
                nb = [self.grid[q] for q in self.neighbours(c.pos)]
                weak = [d for d in nb if self.fit(d) < e["train_frac"] and d.cid not in self.inflight]
                if not weak:
                    continue
                victim = min(weak, key=self.fit)
                slot = victim.pos
                del self.grid[slot]
            self.new_cell(slot, c.cid, prog, op)
            c.last_improve = self.step
            placed += 1
        for c in list(self.grid.values()):
            c.zero_steps = c.zero_steps + 1 if self.fit(c) <= 0 and c.program else 0
            if c.zero_steps >= self.p.die_after and c.cid not in self.inflight:
                if any(self.fit(self.grid[q]) > 0 for q in self.neighbours(c.pos)):
                    del self.grid[c.pos]
        return placed

    # ------------------------------------------------------------------ main loop
    def best(self):
        cells = [c for c in self.grid.values() if c.program and c.sha in self.evals]
        if not cells:
            return None
        clone = {}
        for c in cells:
            clone[c.sha] = clone.get(c.sha, 0) + 1
        return max(cells, key=lambda c: (self.fit(c), clone[c.sha], -c.born))

    def snapshot(self):
        self.snapshots.append({"step": self.step, "cells": [
            [c.cid, c.parent, list(c.pos), (c.sha or "")[:8], round(self.fit(c), 3), c.origin.split(":")[0]]
            for c in self.grid.values()], "calls": self.calls_used, "tokens": self.tokens_used,
            "inflight": len(self.inflight)})

    def run(self) -> dict:
        t0 = time.time()
        n = self.p.size
        centre = (n // 2, n // 2)
        self.new_cell(centre, None, None, "founder")
        spots = [(centre[0], centre[1] - 2), (centre[0] - 2, centre[1]), (centre[0] + 2, centre[1] + 1)]
        for k in range(self.p.founders - 1):  # founders sit two cells apart so their first calls can run together
            self.new_cell(spots[k % len(spots)], None, None, "founder")
        last_gain = 0
        while self.step < self.p.max_steps and time.time() - t0 < self.p.wall_s:
            for _ in range(self.p.max_inflight):
                self.express_expensive()
            # wait briefly for model results so development uses them
            for _ in range(60):
                if any(f.done() for f, *_ in self.inflight.values()) or not self.inflight:
                    break
                time.sleep(1)
            self.collect_expensive()
            moved = self.transfer()
            props = []
            for c in list(self.grid.values()):
                for prog, op in self.propose_cheap(c):
                    props.append((c, prog, op))
            if props:
                self.evaluate([p for _, p, _ in props])
            placed = self.divide_and_die(props)
            if moved or placed:
                last_gain = self.step
            self.snapshot()
            b = self.best()
            if b and self.fit(b) >= 1.0:
                break
            if (self.calls_used >= self.p.calls or self.tokens_used >= self.p.tokens) and not self.inflight \
                    and self.step - last_gain >= 3:
                break
            if not self.grid:
                break
            self.step += 1
        # let in-flight calls finish so their tokens are accounted (results after stop are not used)
        for cid, (fut, *_rest) in list(self.inflight.items()):
            fut.result()
        self.collect_expensive()
        self.pool.shutdown(wait=True)
        b = self.best()
        final_eval = self.evals.get(b.sha) if b else None
        return {"arm": "devorg", "kind": "arc", "task_id": self.task_id, "model": self.model,
                "knockout": self.p.knockout, "params": self.p.__dict__, "calls_used": self.calls_used,
                "tokens_used": self.tokens_used, "steps": self.step,
                "final_eval_id": final_eval.get("eval_id") if final_eval else None,
                "final_visible_score": self.fit(b) if b else float("-inf"),
                "final_origin": b.origin if b else None, "n_cells": len(self.grid),
                "events": self.events, "snapshots": self.snapshots, "wall_s": round(time.time() - t0, 1), **self.tag}
