"""Cheap genes for ARC program-cells: symbolic operations on Python `transform` programs (no model call).

Every operation returns new program source or None. Programs are only ever executed by the evaluation service's
sandbox; these functions only rewrite text. Operations:
  rename_toplevel : give a program's top-level names a suffix so two programs can live in one module
  wrap_output     : apply a fixed grid operation (rotate / flip / transpose) to the program's output
  compose         : f(g(grid)) from two programs
  color_literals  : replace one colour literal (0-9) by another colour present in the task
  learn_color_map : from the program's own training outputs (visible), learn a consistent colour remap
                    to the expected training outputs and wrap the program with it
"""
from __future__ import annotations

import io
import random
import re
import tokenize

WRAPS = {
    "rot90": "np.rot90(_o, 1)", "rot180": "np.rot90(_o, 2)", "rot270": "np.rot90(_o, 3)",
    "fliplr": "np.fliplr(_o)", "flipud": "np.flipud(_o)", "transpose": "_o.T",
}


def _toplevel_names(src: str) -> set[str]:
    names = set()
    for line in src.splitlines():
        m = re.match(r"^(?:def|class)\s+([A-Za-z_]\w*)", line)
        if m:
            names.add(m.group(1))
            continue
        m = re.match(r"^([A-Za-z_]\w*)\s*(?::[^=]*)?=(?!=)", line)
        if m:
            names.add(m.group(1))
    return names


def rename_toplevel(src: str, suffix: str) -> str | None:
    names = _toplevel_names(src)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None
    out, prev = [], None
    for t in toks:
        if t.type == tokenize.NAME and t.string in names and not (prev is not None and prev.string == "."):
            t = t._replace(string=t.string + suffix)
        out.append(t)
        if t.type not in (tokenize.NL, tokenize.COMMENT):
            prev = t
    try:
        return tokenize.untokenize(out)
    except Exception:
        return None


def _header() -> str:
    return "import numpy as np\n"


def wrap_output(src: str, op: str) -> str | None:
    base = rename_toplevel(src, "__w")
    if base is None or "transform__w" not in base:
        return None
    return (_header() + base + "\n\ndef transform(grid):\n    _o = np.array(transform__w([r[:] for r in grid]))\n"
            f"    return {WRAPS[op]}.tolist()\n")


def compose(src_f: str, src_g: str) -> str | None:
    f = rename_toplevel(src_f, "__f")
    g = rename_toplevel(src_g, "__g")
    if not f or not g or "transform__f" not in f or "transform__g" not in g:
        return None
    return (_header() + f + "\n\n" + g + "\n\ndef transform(grid):\n"
            "    return transform__f(transform__g([r[:] for r in grid]))\n")


def color_literals(src: str, palette: list[int], rng: random.Random, k: int = 2) -> list[str]:
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    idx = [i for i, t in enumerate(toks) if t.type == tokenize.NUMBER and t.string.isdigit() and int(t.string) <= 9]
    out = []
    for _ in range(k * 3):
        if not idx or len(out) >= k:
            break
        i = rng.choice(idx)
        new = rng.choice([c for c in palette if c != int(toks[i].string)] or [int(toks[i].string)])
        t2 = list(toks)
        t2[i] = t2[i]._replace(string=str(new))
        try:
            s = tokenize.untokenize(t2)
        except Exception:
            continue
        if s != src and s not in out:
            out.append(s)
    return out


def learn_color_map(src: str, task: dict, train_results: list[dict]) -> str | None:
    """train_results: the evaluation service's per-pair results (ok, got). Uses only training pairs."""
    mapping = {}
    for pair, r in zip(task["train"], train_results):
        got, exp = r.get("got"), pair["output"]
        if got is None or len(got) != len(exp) or any(len(a) != len(b) for a, b in zip(got, exp)):
            return None
        for ra, rb in zip(got, exp):
            for a, b in zip(ra, rb):
                if mapping.setdefault(a, b) != b:
                    return None
    if all(a == b for a, b in mapping.items()):
        return None
    base = rename_toplevel(src, "__m")
    if base is None or "transform__m" not in base:
        return None
    return (_header() + base + f"\n\n_CMAP = {dict(sorted(mapping.items()))!r}\n\ndef transform(grid):\n"
            "    _o = transform__m([r[:] for r in grid])\n"
            "    return [[_CMAP.get(int(v), int(v)) for v in row] for row in _o]\n")


def task_palette(task: dict) -> list[int]:
    cols = set()
    for p in task["train"]:
        for g in (p["input"], p["output"]):
            for row in g:
                cols.update(int(v) for v in row)
    return sorted(cols)
