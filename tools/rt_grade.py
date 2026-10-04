"""Grade workflow records against hidden answers (run on GPU08; never called by agents).

Usage: python tools/rt_grade.py RECORDS.jsonl EVALQ_ROOT [--arc-dir DIR] [--bench DIR] > graded.jsonl
For each record, the final program (chosen by the visible check only) is graded: ARC - exact match on all
test outputs; callus - mean smoothed-pattern r and single-cell r on the masked genes (answer key).
Every round's program is also graded ("oracle" fields) for diagnostics only; arms are compared on final.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_bio.bench import grade  # noqa: E402
from aimeth_rt.arc_data import grade_arc_attempts  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("records"); ap.add_argument("evalq")
    ap.add_argument("--arc-dir"); ap.add_argument("--bench")
    a = ap.parse_args()
    priv = Path(a.evalq) / "private"
    cache = {}

    def g(kind, task_id, eid):
        if not eid:
            return None
        if (kind, eid) in cache:
            return cache[(kind, eid)]
        f = priv / f"{eid}.json"
        res = None
        if f.exists():
            p = json.load(open(f))
            if kind == "arc":
                truth = [t["output"] for t in json.load(open(Path(a.arc_dir) / f"{task_id}.json"))["test"]]
                attempts = p.get("test_attempts") or [[pred] for pred in p["test_preds"]]
                res = {"solved": grade_arc_attempts(attempts, truth)}
            elif p.get("pred_file"):
                t = np.load(Path(a.bench) / "tasks" / f"{task_id}.npz")
                key = np.load(Path(a.bench) / "keys" / f"{task_id}.key.npz")
                gr = grade(np.load(priv / p["pred_file"]), key, t["tgt_xy"])
                res = {"pattern_r": gr["pattern_r_mean"], "cell_r": gr["cell_r_mean"]}
        cache[(kind, eid)] = res
        return res

    for line in open(a.records):
        r = json.loads(line)
        out = {k: r[k] for k in ("arm", "kind", "task_id", "model", "rep", "n_budget", "calls_used", "final_round",
                                 "final_visible_score", "completion_reasoning_tokens_used",
                                 "cost_estimate_cny", "stop_reason") if k in r}
        out["final"] = g(r["kind"], r["task_id"], r["final_eval_id"])
        out["rounds"] = [g(r["kind"], r["task_id"], s.get("eval_id")) for s in r["steps"]]
        out["tokens"] = sum((s.get("prompt_tokens") or 0) +
                             (s.get("completion_tokens") if isinstance(s.get("completion_tokens"), int)
                              else (s.get("completion_reasoning_tokens") or 0)) for s in r["steps"])
        out["prompt_tokens"] = sum((s.get("prompt_tokens") or 0) for s in r["steps"])
        out["completion_tokens"] = sum((s.get("completion_tokens") if isinstance(s.get("completion_tokens"), int)
                                        else (s.get("completion_reasoning_tokens") or 0)) for s in r["steps"])
        out["calls_used"] = r.get("calls_used")
        print(json.dumps(out))


if __name__ == "__main__":
    main()
