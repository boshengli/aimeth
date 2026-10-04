"""Cross-check private ARC request ledgers against public scores and budget caps."""

from __future__ import annotations

from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from .calibration import PROVIDERS


def audit_calibration(private_root: Path, csv_path: Path,
                      require_complete: bool = True) -> dict[str, Any]:
    with csv_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    task_ids = [row["task_id"] for row in rows]
    if len(task_ids) != 400 or len(set(task_ids)) != 400:
        raise ValueError("calibration CSV must have 400 unique tasks")
    results: dict[str, Any] = {"task_count": 400, "providers": {}, "complete": True}
    score_path = private_root / "scores.jsonl"
    with score_path.open() as stream:
        score_rows = [json.loads(line) for line in stream]
    score_ids = [row["request_id"] for row in score_rows]
    if len(score_ids) != len(set(score_ids)):
        raise ValueError("duplicate scored request ID")
    if not set(score_ids).issubset({f"{provider}-{tid}-{sample}"
                                   for provider in PROVIDERS for tid in task_ids
                                   for sample in range(4)}):
        raise ValueError("score ledger contains an unexpected request ID")
    scores = {row["request_id"]: row for row in score_rows}
    for row in rows:
        pooled: list[bool] = []
        for provider in PROVIDERS:
            available = [scores[f"{provider}-{row['task_id']}-{sample}"]
                         for sample in range(4)
                         if f"{provider}-{row['task_id']}-{sample}" in scores]
            expected = {
                f"{provider}_samples": str(len(available)),
                f"{provider}_pass_at_1": str(sum(bool(x["test_success"]) for x in available) / 4)
                if len(available) == 4 else "",
                f"{provider}_pass_at_4": str(int(any(x["test_success"] for x in available)))
                if len(available) == 4 else "",
                f"{provider}_programs_extracted": str(sum(bool(x["program_extracted"])
                                                       for x in available)),
                f"{provider}_execution_ok": str(sum(x["execution_status"] == "ok"
                                                  for x in available)),
            }
            for field, value in expected.items():
                if row[field] != value:
                    raise ValueError(f"{row['task_id']}: calibration CSV mismatch in {field}")
            pooled.extend(bool(x["test_success"]) for x in available)
        expected_pooled = str(sum(pooled) / 8) if len(pooled) == 8 else ""
        if row["pooled_pass_at_1"] != expected_pooled:
            raise ValueError(f"{row['task_id']}: pooled pass@1 mismatch")
    comparable_requests: dict[str, dict[str, str]] = {}
    for provider, cfg in PROVIDERS.items():
        path = private_root / f"{provider}-receipts.jsonl"
        started: dict[str, dict[str, Any]] = {}
        settled: dict[str, dict[str, Any]] = {}
        with path.open() as stream:
            for line in stream:
                event = json.loads(line)
                rid = event["request_id"]
                target = started if event["event"] == "dispatch_started" else settled
                if rid in target:
                    raise ValueError(f"duplicate {event['event']} receipt: {rid}")
                target[rid] = event
        expected = {f"{provider}-{tid}-{sample}" for tid in task_ids for sample in range(4)}
        if not set(started).issubset(expected) or not set(settled).issubset(set(started)):
            raise ValueError(f"{provider}: unexpected or unreserved request")
        comparable_requests[provider] = {}
        for rid, event in started.items():
            messages = event["request_body"]["messages"]
            if (len(messages) != 2 or "Task data:\n" not in messages[1]["content"]):
                raise ValueError(f"{rid}: missing structured ARC prompt")
            task_view = json.loads(messages[1]["content"].split("Task data:\n", 1)[1])
            if (not task_view.get("test") or
                    any(set(pair) != {"input"} for pair in task_view["test"])):
                raise ValueError(f"{rid}: test output leaked into generation prompt")
            body = json.dumps(event["request_body"], ensure_ascii=False,
                              separators=(",", ":")).encode()
            if sha256(body).hexdigest() != event["request_sha256"]:
                raise ValueError(f"{rid}: request hash mismatch")
            comparable = dict(event["request_body"])
            comparable.pop("model", None)
            key = rid.removeprefix(provider + "-")
            comparable_requests[provider][key] = sha256(json.dumps(
                comparable, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode()).hexdigest()
        estimate = sum(event["estimated_cny"] if event.get("estimated_cny") is not None
                       else event["reserve_cny"] for event in settled.values())
        estimate += sum(event["reserve_cny"] for rid, event in started.items()
                        if rid not in settled)
        if estimate > cfg["cap_cny"]:
            raise ValueError(f"{provider}: budget envelope exceeds cap")
        scored = {rid for rid in score_ids if rid.startswith(provider + "-")}
        if not scored.issubset(set(settled)):
            raise ValueError(f"{provider}: scored request lacks settled receipt")
        complete = set(started) == set(settled) == scored == expected
        results["complete"] &= complete
        results["providers"][provider] = {
            "planned": len(expected), "started": len(started),
            "settled": len(settled), "scored": len(scored),
            "http_statuses": dict(Counter(str(event.get("http_status"))
                                          for event in settled.values())),
            "budget_envelope_cny": round(estimate, 3),
            "cap_cny": cfg["cap_cny"], "complete": complete,
            "receipt_sha256": sha256(path.read_bytes()).hexdigest(),
        }
    common = set(comparable_requests["deepseek"]) & set(comparable_requests["zhipu"])
    if any(comparable_requests["deepseek"][key] != comparable_requests["zhipu"][key]
           for key in common):
        raise ValueError("provider request conditions differ beyond the model identifier")
    results["matched_cross_provider_requests"] = len(common)
    if require_complete and not results["complete"]:
        raise ValueError("calibration is not complete")
    return results
