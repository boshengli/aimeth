"""Run the developmental arm (DevOrg-ARC v0) over ARC tasks. Same budget contract and grading as tools/rt_run.py.

python tools/rt_devorg.py --tasks ALL|FILE --arc-dir DIR --out OUT.jsonl --provider deepseek --model deepseek-flash \
    --calls 8 --tokens 262144 --per-call 32768 [--knockout none|no_division|no_cheap|shuffled_organiser|well_mixed]
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
from aimeth_rt.devorg import DevOrg, Params  # noqa: E402
from aimeth_rt.evalq import EvalClient  # noqa: E402
from aimeth_rt.llm import LLM  # noqa: E402
from tools.rt_run import PRESETS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True); ap.add_argument("--arc-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--evalq", default="/data/libs/aimeth/rt/evalq")
    ap.add_argument("--receipts", default="/data/libs/aimeth/rt/receipts")
    ap.add_argument("--provider", default="deepseek"); ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--calls", type=int, default=8); ap.add_argument("--tokens", type=int, default=262144)
    ap.add_argument("--per-call", type=int, default=32768)
    ap.add_argument("--knockout", default="none")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=20)
    ap.add_argument("--llm-start", type=int, default=10); ap.add_argument("--llm-cap", type=int, default=30)
    ap.add_argument("--budget-cny", type=float, default=None)
    ap.add_argument("--limit-tasks", type=int, default=None)
    a = ap.parse_args()
    if a.tasks == "ALL":
        ids = sorted(p.stem for p in Path(a.arc_dir).glob("*.json"))
    else:
        spec = json.load(open(a.tasks))
        if isinstance(spec, dict):
            spec = next(spec[k] for k in ("task_ids", "pilot", "tasks") if k in spec)
        ids = [t["task_id"] if isinstance(t, dict) else t for t in spec]
    ids = ids[:a.limit_tasks] if a.limit_tasks else ids
    out = Path(a.out)
    done = {json.loads(l)["task_id"] for l in open(out)} if out.exists() else set()
    ids = [t for t in ids if t not in done]
    print(time.strftime("%H:%M:%S"), f"devorg/{a.knockout}: {len(ids)} tasks ({len(done)} done)", flush=True)
    llm = LLM(a.receipts, start=a.llm_start, cap=a.llm_cap, budget_cny=a.budget_cny)
    ev = EvalClient(a.evalq)
    extra = dict(PRESETS.get((a.provider, a.model)) or ({} if a.provider == "glm_cc" else PRESETS.get(a.model)) or {})
    lock = threading.Lock()

    def one(tid):
        task = json.load(open(Path(a.arc_dir) / f"{tid}.json"))
        p = Params(calls=a.calls, tokens=a.tokens, per_call_cap=a.per_call, knockout=a.knockout, seed=a.seed)
        r = DevOrg(tid, task, llm, ev, p, provider=a.provider, model=a.model, extra=extra, arc_dir=a.arc_dir,
                   tag={"rep": 0, "run": out.stem}).run()
        with lock, open(out, "a") as fh:
            fh.write(json.dumps(r) + "\n")
        return r

    n = 0
    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(one, ids):
            n += 1
            print(time.strftime("%H:%M:%S"), f"{n}/{len(ids)} {r['task_id']} fit={r['final_visible_score']:.2f} "
                  f"calls={r['calls_used']} steps={r['steps']} cells={r['n_cells']} llm={llm.stats} "
                  f"spent={llm.spent_cny:.1f}", flush=True)


if __name__ == "__main__":
    main()
