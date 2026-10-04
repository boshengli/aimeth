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
        score_ids = [json.loads(line)["request_id"] for line in stream]
    if len(score_ids) != len(set(score_ids)):
        raise ValueError("duplicate scored request ID")
    if not set(score_ids).issubset({f"{provider}-{tid}-{sample}"
                                   for provider in PROVIDERS for tid in task_ids
                                   for sample in range(4)}):
        raise ValueError("score ledger contains an unexpected request ID")
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
        for rid, event in started.items():
            body = json.dumps(event["request_body"], ensure_ascii=False,
                              separators=(",", ":")).encode()
            if sha256(body).hexdigest() != event["request_sha256"]:
                raise ValueError(f"{rid}: request hash mismatch")
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
    if require_complete and not results["complete"]:
        raise ValueError("calibration is not complete")
    return results
