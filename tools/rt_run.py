"""Run a budget-matched workflow arm over tasks (login node; programs are executed by the GPU08 eval daemon).

ARC:  python tools/rt_run.py arc ARM --tasks PILOT.json --arc-dir DIR --out OUT.jsonl --model glm-5.3-flash --n 4 --reps 2
BIO:  python tools/rt_run.py bio ARM --bench BENCH --annot ANNOT.csv --out OUT.jsonl --model glm-5.3 --n 4 --reps 1
ARM is independent or self_repair. Finished (task, rep) pairs already in OUT are skipped, so runs resume.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_rt.evalq import EvalClient  # noqa: E402
from aimeth_rt.llm import LLM  # noqa: E402
from aimeth_rt.workflows import ARC_SYSTEM, arc_user_prompt, run_workflow  # noqa: E402

PRESETS = {  # request extras per model, matched to the calibration runs
    "glm-5.3-flash": {"thinking": {"type": "enabled"}, "reasoning_effort": "low"},
    "glm-5.3": {"thinking": {"type": "enabled"}},
    "deepseek-flash": {"thinking": {"type": "enabled"}, "reasoning_effort": "low"},
}


def load_tasks_arc(a):
    if a.tasks == "ALL":
        ids = sorted(p.stem for p in Path(a.arc_dir).glob("*.json"))
    else:
        spec = json.load(open(a.tasks))
        if isinstance(spec, dict):
            spec = next(spec[k] for k in ("task_ids", "pilot", "tasks") if k in spec)
        ids = [t["task_id"] if isinstance(t, dict) else t for t in spec]
    out = []
    for tid in ids:
        task = json.load(open(Path(a.arc_dir) / f"{tid}.json"))
        out.append((tid, task, [{"role": "system", "content": ARC_SYSTEM}, {"role": "user", "content": arc_user_prompt(task)}]))
    return out


def load_tasks_bio(a):
    from aimeth_bio.bench import gene_annotation
    from tools.bio_generate import SYSTEM, build_prompt
    ann = gene_annotation(Path(a.annot))
    masks = {k: [d["id"] for d in v] for k, v in json.load(open(Path(a.bench) / "mask_sets.json")).items()}
    out = []
    for jf in sorted((Path(a.bench) / "tasks").glob("*.json")):
        info = json.load(open(jf))
        if a.only and info["task_id"] not in a.only:
            continue
        prompt = build_prompt(info, ann, masks[info["mask_set"]])
        out.append((info["task_id"], None, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["arc", "bio"])
    ap.add_argument("arm", choices=["independent", "self_repair"])
    ap.add_argument("--tasks"); ap.add_argument("--arc-dir"); ap.add_argument("--bench"); ap.add_argument("--annot")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out", required=True)
    ap.add_argument("--evalq", default="/data/libs/aimeth/rt/evalq")
    ap.add_argument("--receipts", default="/data/libs/aimeth/rt/receipts")
    ap.add_argument("--provider", default="zhipu_coding")
    ap.add_argument("--model", default="glm-5.3-flash")
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("--max-tokens", type=int, default=12288)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--llm-start", type=int, default=4)
    ap.add_argument("--llm-cap", type=int, default=8)
    ap.add_argument("--budget-cny", type=float, default=None, help="hard stop for paid providers (conservative envelope)")
    ap.add_argument("--reasoning-effort", default=None)
    ap.add_argument("--limit-tasks", type=int, default=None)
    a = ap.parse_args()

    tasks = load_tasks_arc(a) if a.kind == "arc" else load_tasks_bio(a)
    if a.limit_tasks:
        tasks = tasks[:a.limit_tasks]
    out = Path(a.out)
    done = set()
    if out.exists():
        for line in open(out):
            r = json.loads(line)
            done.add((r["task_id"], r["rep"]))
    jobs = [(tid, task, msgs, rep) for rep in range(a.reps) for tid, task, msgs in tasks if (tid, rep) not in done]
    print(time.strftime("%H:%M:%S"), f"{a.kind}/{a.arm}: {len(jobs)} instances to run ({len(done)} done)", flush=True)
    llm = LLM(a.receipts, start=a.llm_start, cap=a.llm_cap, budget_cny=a.budget_cny)
    ev = EvalClient(a.evalq)
    lock = threading.Lock()
    extra = dict(PRESETS.get(a.model) or {})
    if a.reasoning_effort:
        extra["reasoning_effort"] = a.reasoning_effort

    def one(job):
        tid, task, msgs, rep = job
        r = run_workflow(a.arm, a.kind, tid, task, msgs, llm, ev, provider=a.provider, model=a.model, n=a.n,
                         max_tokens=a.max_tokens, extra=extra, tag={"rep": rep, "run": out.stem}, val_seed=1000 + rep,
                         eval_extra={"arc_dir": a.arc_dir} if a.kind == "arc" else {})
        with lock, open(out, "a") as fh:
            fh.write(json.dumps(r) + "\n")
        return r

    n_done = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(one, jobs):
            n_done += 1
            if n_done % 5 == 0 or n_done == len(jobs):
                print(time.strftime("%H:%M:%S"), f"{n_done}/{len(jobs)} llm={llm.stats} limit={llm.lim.limit} "
                      f"spent_envelope_cny={llm.spent_cny:.2f}", flush=True)


if __name__ == "__main__":
    main()
