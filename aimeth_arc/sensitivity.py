"""Post-hoc description of output-length truncation in ARC calibration."""

from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


PROVIDERS = ("deepseek", "zhipu")


def summarize_truncation(scores_path: Path, pilot_path: Path, csv_path: Path,
                         output_json: Path, output_csv: Path) -> dict[str, Any]:
    """Describe truncation without changing scores or frozen task selection.

    A selected task is truncation-majority when length-truncated failed samples
    outnumber other failed samples across its eight pooled samples.
    """
    pilot = json.loads(pilot_path.read_text())
    selected = {row["task_id"] for row in pilot["pilot"]}
    if len(selected) != 40:
        raise ValueError("expected 40 unique pilot tasks")
    if pilot["calibration_csv_sha256"] != sha256(csv_path.read_bytes()).hexdigest():
        raise ValueError("pilot and calibration CSV do not match")
    with csv_path.open(newline="") as stream:
        calibration_rows = list(csv.DictReader(stream))
    task_ids = {row["task_id"] for row in calibration_rows}
    if len(calibration_rows) != 400 or len(task_ids) != 400 or not selected <= task_ids:
        raise ValueError("expected 400 unique calibrated tasks and selected subset")
    scores: dict[str, dict[str, Any]] = {}
    for line in scores_path.read_text().splitlines():
        row = json.loads(line)
        rid = row["request_id"]
        if rid in scores:
            raise ValueError(f"duplicate score: {rid}")
        scores[rid] = row
    if len(scores) != 400 * 4 * 2:
        raise ValueError("truncation analysis requires all 3200 scored samples")
    columns = ["task_id", "selected_pilot", "deepseek_length_count",
               "deepseek_nontruncated_count", "deepseek_nontruncated_successes",
               "deepseek_nontruncated_pass_rate", "zhipu_length_count",
               "zhipu_nontruncated_count", "zhipu_nontruncated_successes",
               "zhipu_nontruncated_pass_rate", "pooled_failed_count",
               "pooled_length_failed_count", "pooled_nonlength_failed_count",
               "length_majority_of_failures"]
    public_rows: list[dict[str, Any]] = []
    aggregate = {p: {"length_count": 0, "nontruncated_count": 0,
                     "nontruncated_successes": 0} for p in PROVIDERS}
    majority_count = 0
    for task_id in sorted(task_ids):
        public: dict[str, Any] = {"task_id": task_id,
                                  "selected_pilot": task_id in selected}
        length_failures = 0
        nonlength_failures = 0
        for provider in PROVIDERS:
            samples = []
            for sample in range(4):
                rid = f"{provider}-{task_id}-{sample}"
                if rid not in scores:
                    raise ValueError(f"missing score: {rid}")
                row = scores[rid]
                if (row["provider"], row["task_id"], row["sample"]) != (provider, task_id, sample):
                    raise ValueError(f"inconsistent score identity: {rid}")
                samples.append(row)
            length = [x for x in samples if x.get("finish_reason") == "length"]
            nonlength = [x for x in samples if x.get("finish_reason") != "length"]
            successes = sum(bool(x["test_success"]) for x in nonlength)
            public[f"{provider}_length_count"] = len(length)
            public[f"{provider}_nontruncated_count"] = len(nonlength)
            public[f"{provider}_nontruncated_successes"] = successes
            public[f"{provider}_nontruncated_pass_rate"] = (
                successes / len(nonlength) if nonlength else "")
            aggregate[provider]["length_count"] += len(length)
            aggregate[provider]["nontruncated_count"] += len(nonlength)
            aggregate[provider]["nontruncated_successes"] += successes
            length_failures += sum(not bool(x["test_success"]) for x in length)
            nonlength_failures += sum(not bool(x["test_success"]) for x in nonlength)
        public["pooled_failed_count"] = length_failures + nonlength_failures
        public["pooled_length_failed_count"] = length_failures
        public["pooled_nonlength_failed_count"] = nonlength_failures
        public["length_majority_of_failures"] = (
            length_failures > nonlength_failures if public["pooled_failed_count"] else False)
        if task_id in selected and public["length_majority_of_failures"]:
            majority_count += 1
        public_rows.append(public)
    for provider, stats in aggregate.items():
        if stats["length_count"] + stats["nontruncated_count"] != 1600:
            raise AssertionError(f"{provider}: invalid sample denominator")
        stats["length_rate"] = stats["length_count"] / 1600
        stats["nontruncated_pass_rate"] = (
            stats["nontruncated_successes"] / stats["nontruncated_count"]
            if stats["nontruncated_count"] else None)
    result = {
        "schema_version": 1,
        "purpose": "post-hoc descriptive sensitivity analysis; not a selection gate",
        "definition": "finish_reason=length is truncation; nontruncated pass rate is successful samples divided by samples with another finish_reason; a pilot task has truncation-majority failures only when pooled length-truncated failed samples exceed all other failed samples across both providers",
        "providers": aggregate,
        "selected_pilot_count": len(selected),
        "selected_pilot_length_majority_failure_count": majority_count,
        "calibration_csv_sha256": sha256(csv_path.read_bytes()).hexdigest(),
        "pilot_manifest_sha256": sha256(pilot_path.read_bytes()).hexdigest(),
        "private_score_ledger_sha256": sha256(scores_path.read_bytes()).hexdigest(),
        "limitations": "Excluding truncated samples changes the denominator and is not a causal estimate; truncation can correlate with task difficulty or model behaviour. No pilot task was reselected."
    }
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(public_rows)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2) + "\n")
    return result
