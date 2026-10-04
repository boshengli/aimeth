"""Stage 2 (GPU08, no network): run generated programs in a bwrap sandbox and grade.

Usage: python tools/bio_evaluate.py BENCH_DIR RUN_DIR [N_PROCS]
The sandbox sees only the Python env, the task file, gene annotations and the
program; answer keys and API keys are not mounted. Grading happens outside.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tempfile
import tokenize
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_bio.bench import grade  # noqa: E402

PY = "/data/libs/aimeth/envs/dev"
ALLOWED_IMPORT = re.compile(r"^\s*(import|from)\s+(numpy|scipy|math|collections|itertools|functools|heapq|statistics)(\.|\s|$)")
BANNED_NAMES = {"open", "exec", "eval", "compile", "__import__", "os", "sys", "subprocess", "socket", "shutil",
                "pathlib", "importlib", "loadtxt", "genfromtxt", "fromfile", "load", "save", "savez", "savetxt",
                "tofile", "memmap", "pickle", "ctypes", "builtins", "__builtins__", "globals", "locals", "getattr",
                "setattr", "delattr", "vars", "input", "breakpoint", "__loader__", "__spec__", "__class__",
                "__subclasses__", "__globals__", "__code__"}

RUNNER = r'''
import json, numpy as np, resource, signal
resource.setrlimit(resource.RLIMIT_AS, (16 * 2**30, 16 * 2**30))
signal.alarm(120)
t = np.load("/task/task.npz", allow_pickle=False)
info = json.load(open("/task/gene_info.json"))
ns = {}
exec(open("/task/program.py").read(), ns)
pred = ns["predict"](t["ref_visible"], t["ref_masked"], t["tgt_visible"], t["tgt_xy"],
                     t["visible_genes"], t["masked_genes"], info)
np.save("/out/pred.npy", np.asarray(pred, dtype=np.float64))
'''


def _names(src: str):
    try:
        return {t.string for t in tokenize.generate_tokens(io.StringIO(src).readline) if t.type == tokenize.NAME}
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None


def static_check(src: str) -> str | None:
    """Identifier-level screen (comments and strings ignored). The sandbox is the real boundary."""
    for line in src.splitlines():
        s = line.strip()
        if s.startswith(("import ", "from ")) and not ALLOWED_IMPORT.match(line):
            return f"disallowed import: {s[:80]}"
    names = _names(src)
    if names is None:
        return "tokenize failed"
    hit = sorted(names & BANNED_NAMES)
    return f"banned names: {hit}" if hit else None


def sandbox_cmd(task_npz: Path, gene_info: Path, prog: Path, runner: Path, out: Path) -> list[str]:
    return ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib64", "/lib64", "--ro-bind", "/lib", "/lib",
            "--ro-bind", "/bin", "/bin", "--ro-bind", PY, PY, "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--ro-bind", str(task_npz), "/task/task.npz", "--ro-bind", str(gene_info), "/task/gene_info.json",
            "--ro-bind", str(prog), "/task/program.py", "--ro-bind", str(runner), "/task/runner.py",
            "--bind", str(out), "/out",
            "--setenv", "OMP_NUM_THREADS", "1", "--setenv", "OPENBLAS_NUM_THREADS", "1",
            PY + "/bin/python", "-I", "/task/runner.py"]


def run_one(args):
    prog, bench, gene_info = args
    tid = "__".join(prog.name.split("__")[0:4])
    res = {"program": prog.name, "task_id": tid}
    bad = static_check(prog.read_text())
    if bad:
        res.update(status="rejected_static", detail=bad)
        return res
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        runner = tmp / "runner.py"
        runner.write_text(RUNNER)
        out = tmp / "out"
        out.mkdir()
        try:
            p = subprocess.run(sandbox_cmd(bench / "tasks" / f"{tid}.npz", gene_info, prog, runner, out),
                               capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            res.update(status="timeout")
            return res
        if p.returncode != 0 or not (out / "pred.npy").exists():
            res.update(status="runtime_error", detail=(p.stderr or "")[-1500:])
            return res
        pred = np.load(out / "pred.npy")
    t = np.load(bench / "tasks" / f"{tid}.npz")
    key = np.load(bench / "keys" / f"{tid}.key.npz")
    if pred.shape != key["tgt_masked"].shape or not np.isfinite(pred).all():
        res.update(status="bad_output", detail=f"shape {pred.shape} vs {key['tgt_masked'].shape}")
        return res
    g = grade(pred, key, t["tgt_xy"])
    res.update(status="ok", cell_r_mean=g["cell_r_mean"], pattern_r_mean=g["pattern_r_mean"],
               per_gene={k: v["pattern_r"] for k, v in g["per_gene"].items() if v["informative"]})
    return res


def main(bench: Path, run: Path, procs: int):
    progs = sorted((run / "programs").glob("*.py"))
    with ProcessPoolExecutor(procs) as ex:
        results = list(ex.map(run_one, [(p, bench, run / "gene_info.json") for p in progs]))
    (run / "eval_results.json").write_text(json.dumps(results, indent=1))
    print(Counter(r["status"] for r in results))


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 8)
