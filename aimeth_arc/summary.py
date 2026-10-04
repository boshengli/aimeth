"""Produce a small, secret-free ARC calibration evidence summary."""

from __future__ import annotations

from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from typing import Any


def _quantile(values: list[float], proportion: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    return round(values[min(len(values)-1, int((len(values)-1)*proportion))], 3)


def _provider_summary(path: Path) -> dict[str, Any]:
    events = []
    for line in path.open() if path.exists() else []:
        if not line.endswith("\n"):
            continue
        event = json.loads(line)
        if event["event"] == "settled":
            events.append(event)
    elapsed = [float(x["elapsed_s"]) for x in events if x.get("elapsed_s") is not None]
    prompt = sum((x.get("usage") or {}).get("prompt_tokens", 0) for x in events)
    output = sum((x.get("usage") or {}).get("completion_tokens", 0) for x in events)
    return {"settled": len(events), "http_statuses": dict(Counter(str(x.get("http_status")) for x in events)),
            "finish_reasons": dict(Counter(str(x.get("finish_reason")) for x in events)),
            "transport_unknown": sum(x.get("http_status") is None for x in events),
            "reported_prompt_tokens": prompt, "reported_completion_tokens": output,
            "usage_missing": sum(x.get("usage") is None for x in events),
            "elapsed_median_s": round(median(elapsed), 3) if elapsed else None,
            "elapsed_p95_s": _quantile(elapsed, .95),
            "conservative_estimated_cny": round(sum(
                x["estimated_cny"] if x.get("estimated_cny") is not None else x["reserve_cny"]
                for x in events), 3),
            "receipt_sha256": sha256(path.read_bytes()).hexdigest() if path.exists() else None}


def summarize(private_root: Path, public_csv: Path, output: Path,
              pilot_manifest: Path | None = None) -> dict[str, Any]:
    with public_csv.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    summary: dict[str, Any] = {"schema_version": 1, "calibration_tasks": len(rows),
                               "samples_per_task_per_model": 4, "providers": {},
                               "data_scope": "ARC-AGI-1 evaluation, 400 tasks",
                               "interpretation": "descriptive single-program difficulty calibration; no organization effect",
                               "calibration_csv_sha256": sha256(public_csv.read_bytes()).hexdigest()}
    for provider in ("deepseek", "zhipu"):
        stats = _provider_summary(private_root / f"{provider}-receipts.jsonl")
        stats["planned_v2"] = len(rows) * 4
        stats["task_pass_at_4_count"] = sum(row[f"{provider}_pass_at_4"] == "1" for row in rows)
        stats["sample_successes"] = (round(sum(float(row[f"{provider}_pass_at_1"]) * 4
                                                   for row in rows if row[f"{provider}_pass_at_1"]), 0))
        stats["programs_extracted"] = sum(int(row[f"{provider}_programs_extracted"]) for row in rows)
        stats["execution_ok"] = sum(int(row[f"{provider}_execution_ok"]) for row in rows)
        stats["complete"] = stats["settled"] == stats["planned_v2"]
        summary["providers"][provider] = stats
    v1 = private_root.parent / "deepseek-receipts.jsonl"
    summary["superseded_deepseek_v1_probe"] = _provider_summary(v1) if v1.exists() else None
    summary["complete"] = all(x["complete"] for x in summary["providers"].values())
    if pilot_manifest and pilot_manifest.exists():
        pilot = json.loads(pilot_manifest.read_text())
        summary["pilot"] = {"count": len(pilot["pilot"]),
                            "eligible_count": pilot["eligible_count"],
                            "manifest_sha256": sha256(pilot_manifest.read_bytes()).hexdigest()}
    else:
        summary["pilot"] = None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2) + "\n")
    return summary
