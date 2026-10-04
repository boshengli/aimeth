"""Audit the Phase-B task denominator and frozen per-instance budget rules."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("independent", "self_repair", "single_long", "vote",
        "orchestrator_worker", "debate", "evolution")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def audit(run_dir: Path, arc_manifest: Path, bio_manifest: Path) -> dict:
    arc_ids = {r["task_id"] for r in json.loads(arc_manifest.read_text())["tasks"]}
    bio_ids = {r["task_id"] for r in json.loads(bio_manifest.read_text())}
    expected = {"arc2": arc_ids, "callus": bio_ids}
    counts = {}
    failures = []
    for family, ids in expected.items():
        for arm in ARMS:
            path = run_dir / f"{family}-{arm}.jsonl"
            rows = read_jsonl(path)
            got = [(r.get("task_id"), r.get("rep")) for r in rows]
            if len(got) != len(set(got)):
                failures.append(f"duplicate result keys: {path.name}")
            if set(got) != {(tid, 0) for tid in ids}:
                failures.append(f"denominator mismatch: {path.name} expected={len(ids)} observed={len(rows)}")
            for row in rows:
                if row.get("arm") != arm or row.get("kind") != ("arc" if family == "arc2" else "bio"):
                    failures.append(f"arm/task-kind mismatch: {path.name}:{row.get('task_id')}")
                if row.get("provider") != "deepseek" or row.get("model") != "deepseek-flash":
                    failures.append(f"model identity mismatch: {path.name}:{row.get('task_id')}")
                budget = row.get("budget") or {}
                if budget.get("calls") != 8 or budget.get("completion_reasoning_tokens") != 262144:
                    failures.append(f"budget mismatch: {path.name}:{row.get('task_id')}")
                if ((row.get("calls_used") is not None and row["calls_used"] > 8)
                        or (row.get("completion_reasoning_tokens_used") is not None
                            and row["completion_reasoning_tokens_used"] > 262144)):
                    failures.append(f"ceiling exceeded: {path.name}:{row.get('task_id')}")
                for step in row.get("steps", []):
                    ceiling = 262144 if arm == "single_long" else 32768
                    if step.get("requested_max_tokens", 0) > ceiling:
                        failures.append(f"per-call cap exceeded: {path.name}:{row.get('task_id')}")
            starts = read_jsonl(path.with_suffix(".events.jsonl"))
            started_ids = [(r.get("task_id"), r.get("rep")) for r in starts
                           if r.get("event") == "task_started"]
            if len(started_ids) != len(set(started_ids)):
                failures.append(f"duplicate task start: {path.name}")
            if not set(started_ids).issubset(set(got)):
                failures.append(f"task start lacks result or unknown-status record: {path.name}")
            failed_results = sum(not r.get("final_eval_id") for r in rows)
            counts[f"{family}/{arm}"] = {
                "planned": len(ids), "settled": len(rows), "failed_or_ungraded": failed_results,
                "unknown_dispatch_outcomes": sum(r.get("dispatch_outcome") == "unknown" for r in rows),
                "not_started_tasks": sum(r.get("dispatch_outcome") == "not_started" for r in rows),
                "provider_errors": sum(not s.get("ok", False) for r in rows for s in r.get("steps", [])
                                       if "ok" in s),
                "completion_reasoning_tokens_known_sum": sum(
                    r.get("completion_reasoning_tokens_used") or 0 for r in rows),
                "tasks_with_unknown_token_usage": sum(
                    r.get("completion_reasoning_tokens_used") is None for r in rows),
                "cost_estimate_cny_known_sum": round(
                    sum(r.get("cost_estimate_cny") or 0.0 for r in rows), 6),
            }
    report = {"run_version": "p2-controls-v1", "arc2_expected": len(arc_ids),
              "callus_expected": len(bio_ids), "arms": list(ARMS),
              "results": counts, "integrity_failures": failures,
              "complete": not failures}
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "audit.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--arc-manifest", type=Path, default=ROOT / "plans/arc2-pilot40-v1.json")
    parser.add_argument("--bio-manifest", type=Path, default=Path("runs/p2-controls-v1/callus-public-prompts-v1.json"))
    args = parser.parse_args()
    result = audit(args.run_dir, args.arc_manifest, args.bio_manifest)
    print(json.dumps(result, indent=2))
    if not result["complete"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
