"""Paired task-level analysis for the frozen P2 Phase-B comparison."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

ARMS = ("independent", "self_repair", "single_long", "vote",
        "orchestrator_worker", "debate", "evolution")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_family(run_dir: Path, family: str, expected_ids: set[str], metric: str,
                replicates: int, seed: int) -> tuple[list[dict], dict]:
    values: dict[str, dict[str, float]] = {}
    failures: dict[str, dict[str, int]] = {}
    details: dict[str, dict[str, dict]] = {}
    for arm in ARMS:
        path = run_dir / "graded" / f"{family}-{arm}.graded.jsonl"
        rows = read_jsonl(path)
        ids = [row.get("task_id") for row in rows]
        if len(ids) != len(set(ids)) or set(ids) != expected_ids:
            raise ValueError(f"{family}/{arm}: graded task denominator mismatch")
        values[arm], failures[arm], details[arm] = {}, {}, {}
        for row in rows:
            final = row.get("final") or {}
            if family == "arc2":
                is_valid = isinstance(final.get("solved"), bool)
                score = 1.0 if final.get("solved") is True else 0.0
            else:
                raw = final.get(metric) if final else None
                is_valid = isinstance(raw, (int, float)) and np.isfinite(raw)
                score = float(raw) if is_valid else 0.0
            values[arm][row["task_id"]] = score
            failures[arm][row["task_id"]] = 0 if is_valid else 1
            details[arm][row["task_id"]] = {
                "score": score, "graded": bool(is_valid),
                "calls_used": row.get("calls_used"),
                "completion_tokens": row.get("completion_tokens"),
                "cost_estimate_cny": row.get("cost_estimate_cny"),
            }

    ordered_ids = sorted(expected_ids)
    baseline = np.asarray([values["independent"][tid] for tid in ordered_ids], dtype=float)
    rng = np.random.default_rng(seed)
    summary = []
    for arm in ARMS:
        sample = np.asarray([values[arm][tid] for tid in ordered_ids], dtype=float)
        failed = sum(failures[arm].values())
        if arm == "independent":
            delta = np.zeros(len(ordered_ids), dtype=float)
        else:
            delta = sample - baseline
        indices = rng.integers(0, len(ordered_ids), size=(replicates, len(ordered_ids)))
        boot = delta[indices].mean(axis=1)
        summary.append({"family": family, "metric": "arc_exact_solve" if family == "arc2" else metric,
                        "arm": arm, "n_task_instances": len(ordered_ids),
                        "mean_score_failures_as_zero": float(sample.mean()),
                        "ungraded_or_no_final": failed,
                        "paired_difference_vs_independent": float(delta.mean()),
                        "bootstrap_95_ci_low": float(np.quantile(boot, 0.025)),
                        "bootstrap_95_ci_high": float(np.quantile(boot, 0.975)),
                        "bootstrap_replicates": replicates, "bootstrap_seed": seed,
                        "resampling_unit": "task instance, paired across arms"})
    task_table = [{"family": family, "task_id": tid,
                   **{arm: details[arm][tid] for arm in ARMS}}
                  for tid in ordered_ids]
    return summary, {"expected_task_instances": len(ordered_ids), "task_table": task_table}


def analyze(run_dir: Path, arc_manifest: Path, bio_manifest: Path,
            replicates: int = 10_000, seed: int = 1000) -> dict:
    arc_ids = {row["task_id"] for row in json.loads(arc_manifest.read_text())["tasks"]}
    bio_ids = {row["task_id"] for row in json.loads(bio_manifest.read_text())}
    arc, arc_detail = load_family(run_dir, "arc2", arc_ids, "solved", replicates, seed)
    bio, bio_detail = load_family(run_dir, "callus", bio_ids, "pattern_r", replicates, seed + 1)
    bio_cell, _ = load_family(run_dir, "callus", bio_ids, "cell_r", replicates, seed + 2)
    result = {"version": "p2-controls-analysis-v1", "replicates": replicates,
              "seed": seed, "failure_policy": "no final grade or invalid output scores 0 and stays in denominator",
              "interpretation": "one independently initialized arm run per task; task-bootstrap intervals are exploratory and do not substitute for multiple independent population initializations per task",
              "families": {"arc2": arc_detail, "callus": bio_detail},
              "summary": arc + bio + bio_cell}
    output = run_dir / "analysis"
    output.mkdir(parents=True, exist_ok=True)
    (output / "paired-summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    with (output / "paired-summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result["summary"][0]))
        writer.writeheader()
        writer.writerows(result["summary"])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--arc-manifest", type=Path, default=Path("plans/arc2-pilot40-v1.json"))
    parser.add_argument("--bio-manifest", type=Path, default=Path("runs/p2-controls-v1/callus-public-prompts-v1.json"))
    parser.add_argument("--bootstrap-replicates", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=1000)
    args = parser.parse_args()
    result = analyze(args.run_dir, args.arc_manifest, args.bio_manifest,
                     args.bootstrap_replicates, args.seed)
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
