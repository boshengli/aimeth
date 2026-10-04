"""Close interrupted Phase-B denominators without making any model calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_rt.control_arms import ARMS, Budget
from tools.rt_run import finalize_fenced_tasks


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def finalize(run_dir: Path, arc_manifest: Path, bio_manifest: Path) -> dict:
    lock_pid = run_dir / "launcher.lockdir" / "pid"
    if lock_pid.exists():
        try:
            os.kill(int(lock_pid.read_text().strip()), 0)
        except (ProcessLookupError, ValueError):
            pass
        else:
            raise RuntimeError("controller process still appears live; do not finalize while it may dispatch calls")

    arc_ids = {row["task_id"] for row in json.loads(arc_manifest.read_text())["tasks"]}
    bio_ids = {row["task_id"] for row in json.loads(bio_manifest.read_text())}
    expected = {"arc2": arc_ids, "callus": bio_ids}
    counts = {"unknown_started": 0, "not_started": 0}
    budget = Budget(8, 262144)
    for family, task_ids in expected.items():
        kind = "arc" if family == "arc2" else "bio"
        for arm in ARMS:
            out = run_dir / f"{family}-{arm}.jsonl"
            state = out.with_suffix(".events.jsonl")
            rows = read_jsonl(out)
            results = {(row["task_id"], row["rep"]) for row in rows}
            events = read_jsonl(state)
            started = {(row["task_id"], row["rep"]) for row in events
                       if row.get("event") == "task_started"}
            fenced = started - results
            if fenced:
                counts["unknown_started"] += finalize_fenced_tasks(
                    out, state, fenced, kind=kind, arm=arm, provider="deepseek",
                    model="deepseek-flash", budget=budget, model_max_tokens=262144,
                    seed=1000, run_name=out.stem)
                results.update(fenced)

            unseen = {(task_id, 0) for task_id in task_ids} - results
            lock = threading.Lock()
            for task_id, rep in sorted(unseen):
                config = {"kind": kind, "arm": arm, "task_id": task_id, "rep": rep,
                          "provider": "deepseek", "model": "deepseek-flash",
                          "budget": {"calls": budget.calls,
                                     "completion_reasoning_tokens": budget.tokens},
                          "seed": 1000 + rep}
                row = {**config, "condition": "single_model", "model_max_tokens": 262144,
                       "n_budget": 8, "calls_used": 0,
                       "completion_reasoning_tokens_used": 0, "prompt_tokens_reported": 0,
                       "final_eval_id": None, "final_round": -1,
                       "final_visible_score": None, "contributor_eval_ids": [], "steps": [],
                       "stop_reason": "not_started_before_campaign_end",
                       "dispatch_outcome": "not_started", "cost_estimate_cny": 0.0,
                       "run_cost_estimate_cny_cumulative": None, "run": out.stem}
                out.parent.mkdir(parents=True, exist_ok=True)
                with lock, out.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                state.parent.mkdir(parents=True, exist_ok=True)
                with lock, state.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"event": "task_finalized_not_started", **config},
                                            sort_keys=True) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                counts["not_started"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=Path("runs/p2-controls-v1"))
    parser.add_argument("--arc-manifest", type=Path, default=Path("plans/arc2-pilot40-v1.json"))
    parser.add_argument("--bio-manifest", type=Path,
                        default=Path("runs/p2-controls-v1/callus-public-prompts-v1.json"))
    args = parser.parse_args()
    print(json.dumps(finalize(args.run_dir, args.arc_manifest, args.bio_manifest), sort_keys=True))


if __name__ == "__main__":
    main()
