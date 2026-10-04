"""Score saved calibration receipts without exposing test answers to generation."""

from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from .data import ArcTask
from .executor import run_program
from .grading import exact_match


def extract_program(content: Any) -> str | None:
    if not isinstance(content, str) or not content.strip():
        return None
    fenced = re.search(r"```(?:python)?\s*\n(.*?)```", content, re.IGNORECASE | re.DOTALL)
    code = fenced.group(1) if fenced else content.strip()
    start = code.find("def transform(")
    import_start = code.find("import numpy")
    if import_start >= 0 and (start < 0 or import_start < start):
        start = import_start
    return code[start:].strip() if start >= 0 else None


def read_settled(path: Path) -> dict[str, dict[str, Any]]:
    settled: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return settled
    with path.open() as stream:
        for line in stream:
            if not line.endswith("\n"):
                continue  # concurrent writer has not committed this record yet
            event = json.loads(line)
            if event["event"] == "settled":
                rid = event["request_id"]
                if rid in settled:
                    raise ValueError(f"duplicate settled receipt: {rid}")
                settled[rid] = event
    return settled


def score_receipt(task: ArcTask, event: dict[str, Any]) -> dict[str, Any]:
    parsed = None
    raw = event.get("response_body")
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            pass
    choice = (parsed.get("choices") or [{}])[0] if isinstance(parsed, dict) else {}
    message = choice.get("message") or {}
    code = extract_program(message.get("content"))
    base = {"request_id": event["request_id"], "provider": event["provider"],
            "task_id": task.task_id, "sample": event["sample"],
            "http_status": event.get("http_status"), "finish_reason": event.get("finish_reason"),
            "usage": event.get("usage"), "elapsed_s": event.get("elapsed_s"),
            "program_sha256": sha256(code.encode()).hexdigest() if code else None,
            "program_extracted": bool(code), "execution_status": None,
            "train_correct": 0, "train_total": len(task.train), "test_success": False}
    if not code:
        base["execution_status"] = "no_program"
        return base
    grids = [p["input"] for p in (*task.train, *task.test)]
    result = run_program(code, grids)
    if result.status == "sandbox_unavailable":
        raise RuntimeError("candidate scoring requires an OS sandbox")
    base["execution_status"] = result.status
    if result.status != "ok" or result.outputs is None:
        return base
    train_outputs = result.outputs[:len(task.train)]
    test_outputs = result.outputs[len(task.train):]
    base["train_correct"] = sum(exact_match(a, p["output"])
                                for a, p in zip(train_outputs, task.train))
    base["test_success"] = all(exact_match(a, p["output"])
                               for a, p in zip(test_outputs, task.test))
    return base


def score_all(tasks: dict[str, ArcTask], private_root: Path,
              public_csv: Path) -> dict[str, Any]:
    private_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    score_path = private_root / "scores.jsonl"
    scores: dict[str, dict[str, Any]] = {}
    if score_path.exists():
        for line in score_path.read_text().splitlines():
            row = json.loads(line)
            scores[row["request_id"]] = row
    for provider in ("deepseek", "zhipu"):
        settled = read_settled(private_root / f"{provider}-receipts.jsonl")
        for task in tasks.values():
            for sample in range(4):
                rid = f"{provider}-{task.task_id}-{sample}"
                if rid not in settled or rid in scores:
                    continue
                row = score_receipt(task, settled[rid])
                with score_path.open("a") as stream:
                    stream.write(json.dumps(row, separators=(",", ":")) + "\n")
                    stream.flush()
                scores[rid] = row
    rows = []
    complete = True
    for task in tasks.values():
        row: dict[str, Any] = {"task_id": task.task_id,
                               "max_input_area": task.max_input_area()}
        pooled = []
        for provider in ("deepseek", "zhipu"):
            sample_rows = [scores.get(f"{provider}-{task.task_id}-{i}") for i in range(4)]
            available = [r for r in sample_rows if r is not None]
            successes = [bool(r["test_success"]) for r in available]
            row[f"{provider}_samples"] = len(available)
            row[f"{provider}_pass_at_1"] = (sum(successes) / 4 if len(available) == 4 else "")
            row[f"{provider}_pass_at_4"] = (int(any(successes)) if len(available) == 4 else "")
            row[f"{provider}_programs_extracted"] = sum(r["program_extracted"] for r in available)
            row[f"{provider}_execution_ok"] = sum(r["execution_status"] == "ok" for r in available)
            row[f"{provider}_prompt_tokens"] = sum((r.get("usage") or {}).get("prompt_tokens", 0) for r in available)
            row[f"{provider}_completion_tokens"] = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in available)
            pooled.extend(successes)
            complete &= len(available) == 4
        row["pooled_pass_at_1"] = sum(pooled) / 8 if len(pooled) == 8 else ""
        rows.append(row)
    public_csv.parent.mkdir(parents=True, exist_ok=True)
    with public_csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {"task_count": len(rows), "scored_receipts": len(scores), "complete": complete,
            "csv": str(public_csv), "private_scores": str(score_path)}
