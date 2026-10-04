"""Run ARC programs in a bwrap sandbox (GPU08, no network) and grade outside the sandbox.
Usage: python tools/arc_evaluate.py ARC_DIR RUN [N_PROCS]
Inside the sandbox the program sees only train inputs/outputs and test INPUTS; test outputs stay outside.
"""
import json, subprocess, sys, tempfile
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.bio_evaluate import PY, static_check  # noqa: E402

RUNNER = r'''
import json, resource, signal
resource.setrlimit(resource.RLIMIT_AS, (8 * 2**30, 8 * 2**30))
signal.alarm(60)
task = json.load(open("/task/task.json"))
ns = {}
exec(open("/task/program.py").read(), ns)
f = ns["transform"]
def norm(g):
    return [[int(v) for v in row] for row in g]
train_ok = []
for p in task["train"]:
    try:
        train_ok.append(norm(f([r[:] for r in p["input"]])) == p["output"])
    except Exception:
        train_ok.append(False)
preds = []
for p in task["test"]:
    try:
        preds.append(norm(f([r[:] for r in p["input"]])))
    except Exception as e:
        preds.append(None)
json.dump({"train_ok": train_ok, "preds": preds}, open("/out/res.json", "w"))
'''


def run_one(args):
    prog, arc_dir = args
    tid = prog.name.split("__")[0]
    res = {"program": prog.name, "task": tid, "model": prog.name.split("__")[1]}
    bad = static_check(prog.read_text())
    if bad:
        res.update(status="rejected_static", detail=bad); return res
    task = json.load(open(Path(arc_dir) / f"{tid}.json"))
    visible = {"train": task["train"], "test": [{"input": p["input"]} for p in task["test"]]}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp); (tmp / "out").mkdir()
        (tmp / "task.json").write_text(json.dumps(visible)); (tmp / "runner.py").write_text(RUNNER)
        cmd = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session",
               "--ro-bind", "/usr", "/usr", "--ro-bind", "/lib64", "/lib64", "--ro-bind", "/lib", "/lib",
               "--ro-bind", "/bin", "/bin", "--ro-bind", PY, PY, "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
               "--ro-bind", str(tmp / "task.json"), "/task/task.json", "--ro-bind", str(prog), "/task/program.py",
               "--ro-bind", str(tmp / "runner.py"), "/task/runner.py", "--bind", str(tmp / "out"), "/out",
               "--setenv", "OMP_NUM_THREADS", "1", PY + "/bin/python", "-I", "/task/runner.py"]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        except subprocess.TimeoutExpired:
            res.update(status="timeout"); return res
        if not (tmp / "out" / "res.json").exists():
            res.update(status="runtime_error", detail=(p.stderr or "")[-600:]); return res
        out = json.load(open(tmp / "out" / "res.json"))
    truth = [p["output"] for p in task["test"]]
    res.update(status="ok", train_all=all(out["train_ok"]), train_frac=sum(out["train_ok"]) / len(out["train_ok"]),
               solved=all(a == b for a, b in zip(out["preds"], truth)))
    return res


def main(arc_dir, run, procs=16):
    progs = sorted((Path(run) / "programs").glob("*.py"))
    with ProcessPoolExecutor(procs) as ex:
        results = list(ex.map(run_one, [(p, arc_dir) for p in progs]))
    (Path(run) / "eval_results.json").write_text(json.dumps(results, indent=1))
    print(Counter(r["status"] for r in results), "solved:", Counter((r["model"], r.get("solved")) for r in results))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 16)
