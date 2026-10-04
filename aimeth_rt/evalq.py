"""File-queue evaluation service.

Orchestrators (login node, with internet) submit programs as JSON files into ROOT/pending; a daemon running
inside a Slurm job on GPU08 (no internet) claims them by atomic rename into ROOT/running, executes each
program in a bwrap sandbox (no network, no API keys, no answer keys mounted) and writes ROOT/done/<id>.json.

Only information an agent may legitimately see goes into done/: for ARC, per-training-pair correctness and
the program's training outputs; for callus imputation, scores on a pseudo-task built from the target's own
visible genes. Test predictions are written to ROOT/private/<id>.json and graded later by tools/rt_grade.py.

Daemon: python -m aimeth_rt.evalq daemon ROOT ARC_DIR BENCH_DIR GENE_INFO [N_PROCS]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from tools.bio_evaluate import PY, RUNNER as BIO_RUNNER, static_check  # noqa: E402
from aimeth_bio.bench import grade  # noqa: E402

ARC_RUNNER = r'''
import json, resource, signal, traceback
resource.setrlimit(resource.RLIMIT_AS, (8 * 2**30, 8 * 2**30))
signal.alarm(60)
task = json.load(open("/task/task.json"))
ns = {}
out = {"load_error": None, "train": [], "test": []}
try:
    exec(open("/task/program.py").read(), ns)
    f = ns["transform"]
except Exception:
    out["load_error"] = traceback.format_exc(limit=2)[-800:]
    f = None
def norm(g):
    return [[int(v) for v in row] for row in g]
if f is not None:
    for p in task["train"]:
        try:
            out["train"].append({"ok": True, "grid": norm(f([r[:] for r in p["input"]]))})
        except Exception as e:
            out["train"].append({"ok": False, "error": (type(e).__name__ + ": " + str(e))[:300]})
    for p in task["test"]:
        try:
            out["test"].append(norm(f([r[:] for r in p["input"]])))
        except Exception:
            out["test"].append(None)
json.dump(out, open("/out/res.json", "w"))
'''


def _bwrap(binds: list[tuple[str, str]], out: Path) -> list[str]:
    cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
           "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib64", "/lib64", "--ro-bind", "/lib", "/lib",
           "--ro-bind", "/bin", "/bin", "--ro-bind", PY, PY, "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    for src, dst in binds:
        cmd += ["--ro-bind", src, dst]
    cmd += ["--bind", str(out), "/out", "--setenv", "OMP_NUM_THREADS", "1", "--setenv", "OPENBLAS_NUM_THREADS", "1",
            PY + "/bin/python", "-I", "/task/runner.py"]
    return cmd


# ---------------------------------------------------------------- handlers (run inside the daemon on GPU08)

ARC_ROOT = "/data/libs/aimeth/data/arc-agi/"


def _arc_dir(job: dict, cfg: dict) -> Path:
    d = job.get("arc_dir") or cfg["arc_dir"]
    real = os.path.realpath(d)
    if not real.startswith(ARC_ROOT):
        raise ValueError("arc_dir outside the ARC data root")
    return Path(real)


def handle_arc(job: dict, cfg: dict) -> tuple[dict, dict]:
    task = json.load(open(_arc_dir(job, cfg) / f"{job['task_id']}.json"))
    visible = {"train": task["train"], "test": [{"input": p["input"]} for p in task["test"]]}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "out").mkdir()
        (tmp / "task.json").write_text(json.dumps(visible))
        (tmp / "runner.py").write_text(ARC_RUNNER)
        (tmp / "program.py").write_text(job["program"])
        cmd = _bwrap([(str(tmp / "task.json"), "/task/task.json"), (str(tmp / "program.py"), "/task/program.py"),
                      (str(tmp / "runner.py"), "/task/runner.py")], tmp / "out")
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            return {"status": "timeout"}, {}
        if not (tmp / "out" / "res.json").exists():
            return {"status": "runtime_error", "detail": (p.stderr or "")[-800:]}, {}
        out = json.load(open(tmp / "out" / "res.json"))
    if out["load_error"]:
        return {"status": "load_error", "detail": out["load_error"]}, {}
    train = []
    for pair, r in zip(task["train"], out["train"]):
        train.append({"ok": bool(r["ok"] and r["grid"] == pair["output"]), "error": r.get("error"),
                      "got": r.get("grid")})
    vis = {"status": "ok", "train": train, "train_frac": sum(t["ok"] for t in train) / len(train),
           "train_all": all(t["ok"] for t in train)}
    return vis, {"test_preds": out["test"]}


def _run_bio(arrays: dict, gene_info: str, program: str) -> tuple[np.ndarray | None, str]:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "out").mkdir()
        np.savez(tmp / "task.npz", **arrays)
        (tmp / "runner.py").write_text(BIO_RUNNER)
        (tmp / "program.py").write_text(program)
        cmd = _bwrap([(str(tmp / "task.npz"), "/task/task.npz"), (gene_info, "/task/gene_info.json"),
                      (str(tmp / "program.py"), "/task/program.py"), (str(tmp / "runner.py"), "/task/runner.py")],
                     tmp / "out")
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return None, "timeout (120 s limit)"
        if p.returncode != 0 or not (tmp / "out" / "pred.npy").exists():
            return None, "runtime error: " + (p.stderr or "")[-1200:]
        return np.load(tmp / "out" / "pred.npy"), ""


def handle_bio(job: dict, cfg: dict) -> tuple[dict, dict]:
    t = np.load(Path(cfg["bench_dir"]) / "tasks" / f"{job['task_id']}.npz", allow_pickle=False)
    vis_genes, nm = t["visible_genes"], len(t["masked_genes"])
    rng = np.random.default_rng(int(job.get("val_seed", 0)))
    pseudo = np.sort(rng.choice(len(vis_genes), size=nm, replace=False))
    keep = np.setdiff1d(np.arange(len(vis_genes)), pseudo)
    arrays = {"ref_visible": t["ref_visible"][:, keep], "ref_masked": t["ref_visible"][:, pseudo],
              "tgt_visible": t["tgt_visible"][:, keep], "tgt_xy": t["tgt_xy"],
              "visible_genes": vis_genes[keep], "masked_genes": vis_genes[pseudo]}
    pred, err = _run_bio(arrays, cfg["gene_info"], job["program"])
    if pred is None:
        return {"status": "error", "detail": err}, {}
    truth = t["tgt_visible"][:, pseudo]
    if pred.shape != truth.shape or not np.isfinite(pred).all():
        return {"status": "bad_output", "detail": f"returned shape {pred.shape}, expected {truth.shape} and finite"}, {}
    g = grade(pred, {"tgt_masked": truth, "masked_genes": vis_genes[pseudo]}, t["tgt_xy"])
    per = sorted(((v["pattern_r"], k) for k, v in g["per_gene"].items() if v["informative"]))
    vis = {"status": "ok", "val_pattern_r": g["pattern_r_mean"], "val_cell_r": g["cell_r_mean"],
           "val_worst": [[k, round(r, 3)] for r, k in per[:5]], "val_best": [[k, round(r, 3)] for r, k in per[-3:]]}
    real = {k: t[k] for k in ("ref_visible", "ref_masked", "tgt_visible", "tgt_xy", "visible_genes", "masked_genes")}
    pred_r, err_r = _run_bio(real, cfg["gene_info"], job["program"])
    ok_r = pred_r is not None and pred_r.shape == (len(t["tgt_xy"]), nm) and bool(np.isfinite(pred_r).all())
    vis["real_task_ran"] = ok_r
    if not ok_r:
        vis["real_task_detail"] = err_r or f"returned shape {None if pred_r is None else pred_r.shape}"
    return vis, ({"pred_array": pred_r.astype(np.float32)} if ok_r else {})


def process(path: str, cfg: dict) -> dict:
    job = json.load(open(path))
    t0 = time.time()
    bad = static_check(job["program"]) if job.get("program") else "no program"
    if bad:
        vis, priv = {"status": "rejected_static", "detail": bad}, {}
    else:
        try:
            vis, priv = {"arc": handle_arc, "bio": handle_bio}[job["kind"]](job, cfg)
        except Exception as e:  # never let one job kill the daemon
            vis, priv = {"status": "daemon_error", "detail": f"{type(e).__name__}: {e}"[:500]}, {}
    vis["eval_s"] = round(time.time() - t0, 2)
    root = Path(cfg["root"])
    if priv:
        arr = priv.pop("pred_array", None)
        if arr is not None:
            np.save(root / "private" / (Path(path).stem + ".npy"), arr)
            priv["pred_file"] = Path(path).stem + ".npy"
        (root / "private" / Path(path).name).write_text(json.dumps({"job": {k: v for k, v in job.items()
                                                                          if k != "program"}, **priv}))
    tmp = root / "done" / (Path(path).name + ".tmp")
    tmp.write_text(json.dumps(vis))
    tmp.rename(root / "done" / Path(path).name)
    Path(path).unlink(missing_ok=True)
    return vis


def daemon(root: str, arc_dir: str, bench_dir: str, gene_info: str, nproc: int = 16):
    root_p = Path(root)
    for d in ("pending", "running", "done", "private"):
        (root_p / d).mkdir(parents=True, exist_ok=True)
    os.chmod(root_p / "private", 0o700)
    for f in (root_p / "running").glob("*.json"):  # requeue anything a previous daemon left unfinished
        f.rename(root_p / "pending" / f.name)
    cfg = {"root": root, "arc_dir": arc_dir, "bench_dir": bench_dir, "gene_info": gene_info}
    futs, n_done, last_log = {}, 0, 0.0
    with ProcessPoolExecutor(nproc) as ex:
        while not (root_p / "STOP").exists():
            room = 2 * nproc - len(futs)
            for f in sorted((root_p / "pending").glob("*.json"))[:max(room, 0)]:
                dst = root_p / "running" / f.name
                try:
                    f.rename(dst)
                except FileNotFoundError:
                    continue
                futs[ex.submit(process, str(dst), cfg)] = dst
            for fu in [fu for fu in futs if fu.done()]:
                futs.pop(fu)
                n_done += 1
                if fu.exception():
                    print("process exception", fu.exception(), flush=True)
            if time.time() - last_log > 60:
                (root_p / "daemon_status.json").write_text(json.dumps(
                    {"time": time.time(), "inflight": len(futs), "done": n_done, "host": os.uname().nodename}))
                last_log = time.time()
            time.sleep(0.3)


# ---------------------------------------------------------------- client (runs in the orchestrator)

class EvalClient:
    def __init__(self, root: str):
        self.root = Path(root)

    def submit(self, kind: str, task_id: str, program: str | None, **extra) -> str:
        jid = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        job = {"id": jid, "kind": kind, "task_id": task_id, "program": program or "", **extra}
        tmp = self.root / "pending" / f".{jid}.tmp"
        tmp.write_text(json.dumps(job))
        tmp.rename(self.root / "pending" / f"{jid}.json")
        return jid

    def wait(self, jid: str, timeout: float = 900) -> dict:
        f = self.root / "done" / f"{jid}.json"
        t0 = time.time()
        while time.time() - t0 < timeout:
            if f.exists():
                return json.loads(f.read_text())
            time.sleep(1.0)
        return {"status": "eval_timeout"}

    def run(self, kind: str, task_id: str, program: str | None, **extra) -> dict:
        if not program:
            return {"status": "no_program"}
        jid = self.submit(kind, task_id, program, **extra)
        r = self.wait(jid)
        r["eval_id"] = jid
        return r


if __name__ == "__main__":
    if sys.argv[1] == "daemon":
        daemon(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], int(sys.argv[6]) if len(sys.argv) > 6 else 16)
