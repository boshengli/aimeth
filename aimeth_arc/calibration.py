"""Resumable, bounded public-API calibration for ARC program synthesis."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .data import ArcTask


MAX_TOKENS = 12288
CONCURRENCY = 16
# Deliberately conservative internal budget conversion, not an exchange-rate claim.
CNY_PER_USD_ENVELOPE = 10.0
PROVIDERS = {
    "deepseek": {
        "model": "deepseek-flash",
        "endpoint": "https://api.deepseek.com/chat/completions",
        "env": "DEEPSEEK_API_KEY",
        "input_usd_per_m": 0.30,
        "output_usd_per_m": 1.20,
        "cap_cny": 300.0,
    },
    "zhipu": {
        "model": "glm-5.3-flash",
        "endpoint": "https://api.z.ai/api/paas/v4/chat/completions",
        "env": "ZHIPU_API_KEY",
        "input_usd_per_m": 0.15,
        "output_usd_per_m": 0.50,
        "cap_cny": 300.0,
    },
}

SYSTEM_PROMPT = (
    "You solve ARC-AGI grid transformation tasks. Return only one Python program "
    "with def transform(grid: list[list[int]]) -> list[list[int]]. "
    "You may import numpy as np. Do not use any other imports, file or network I/O, "
    "dynamic execution, or external state. The program must apply the same rule "
    "to every input. Your final answer must contain executable Python code only."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_request(task: ArcTask, provider: str) -> dict[str, Any]:
    cfg = PROVIDERS[provider]
    body: dict[str, Any] = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                "Infer the grid rule from the training input/output pairs. The test outputs "
                "are hidden. Write a general transform program. Task data:\n"
                + json.dumps(task.public_view(), separators=(",", ":"))
            )},
        ],
        "max_tokens": MAX_TOKENS,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "low",
    }
    return body


def cost_envelope_cny(prompt_bytes: int, provider: str) -> float:
    cfg = PROVIDERS[provider]
    usd = ((prompt_bytes * cfg["input_usd_per_m"]
            + MAX_TOKENS * cfg["output_usd_per_m"]) / 1_000_000)
    return usd * CNY_PER_USD_ENVELOPE


def usage_estimate_cny(usage: dict[str, Any] | None, provider: str) -> float | None:
    if not isinstance(usage, dict):
        return None
    inp = usage.get("prompt_tokens")
    out = usage.get("completion_tokens")
    if not isinstance(inp, int) or not isinstance(out, int):
        return None
    cfg = PROVIDERS[provider]
    return ((inp * cfg["input_usd_per_m"] + out * cfg["output_usd_per_m"])
            / 1_000_000 * CNY_PER_USD_ENVELOPE)


class Journal:
    def __init__(self, path: Path):
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        self.path = path
        self.lock = threading.Lock()
        self.finished: set[str] = set()
        self.started: set[str] = set()
        self.known_estimate_cny = 0.0
        self.unknown_reserved_cny = 0.0
        if path.exists():
            with path.open() as stream:
                for line in stream:
                    event = json.loads(line)
                    rid = event["request_id"]
                    if event["event"] == "dispatch_started":
                        self.started.add(rid)
                        self.unknown_reserved_cny += event["reserve_cny"]
                    elif event["event"] == "settled":
                        self.finished.add(rid)
                        reserve = event["reserve_cny"]
                        self.unknown_reserved_cny -= reserve
                        estimate = event.get("estimated_cny")
                        self.known_estimate_cny += reserve if estimate is None else estimate

    def append(self, event: dict[str, Any]) -> None:
        with self.lock:
            fd = os.open(self.path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
            try:
                content = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
                while content:
                    content = content[os.write(fd, content):]
                os.fsync(fd)
            finally:
                os.close(fd)


def _send_one(task: ArcTask, sample: int, provider: str, key: str,
              journal: Journal, body: dict[str, Any], reserve_cny: float) -> dict[str, Any]:
    rid = f"{provider}-{task.task_id}-{sample}"
    body_bytes = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
    started = {"event": "dispatch_started", "at": utc_now(), "request_id": rid,
               "provider": provider, "task_id": task.task_id, "sample": sample,
               "request_sha256": sha256(body_bytes).hexdigest(),
               "request_body": body, "reserve_cny": reserve_cny}
    journal.append(started)
    cfg = PROVIDERS[provider]
    req = Request(cfg["endpoint"], body_bytes, method="POST", headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + key,
    })
    t0 = time.monotonic()
    status = None
    response_body = None
    response_headers: dict[str, str] = {}
    failure = None
    try:
        with urlopen(req, timeout=600) as response:
            status = response.status
            response_headers = {k: v for k, v in response.headers.items()
                                if k.lower() in ("x-request-id", "request-id", "date")}
            response_body = response.read(2_000_000).decode("utf-8", "replace")
    except HTTPError as exc:
        status = exc.code
        response_body = exc.read(2_000_000).decode("utf-8", "replace")
        failure = "http_error"
    except (URLError, TimeoutError, OSError) as exc:
        # Dispatch may have reached the provider: no automatic retry.
        failure = type(exc).__name__
    elapsed = time.monotonic() - t0
    if response_body is not None and key in response_body:
        response_body = response_body.replace(key, "<REDACTED_SECRET>")
    parsed = None
    if response_body is not None:
        try:
            parsed = json.loads(response_body)
        except json.JSONDecodeError:
            failure = failure or "invalid_response_json"
    usage = parsed.get("usage") if isinstance(parsed, dict) else None
    estimate = usage_estimate_cny(usage, provider)
    choice = (parsed.get("choices") or [{}])[0] if isinstance(parsed, dict) else {}
    event = {"event": "settled", "at": utc_now(), "request_id": rid,
             "provider": provider, "task_id": task.task_id, "sample": sample,
             "http_status": status, "elapsed_s": round(elapsed, 3),
             "response_headers": response_headers, "response_body": response_body,
             "usage": usage, "served_model": parsed.get("model") if isinstance(parsed, dict) else None,
             "finish_reason": choice.get("finish_reason"), "failure": failure,
             "reserve_cny": reserve_cny, "estimated_cny": estimate}
    journal.append(event)
    return {k: event[k] for k in ("request_id", "http_status", "failure", "finish_reason", "usage")}


def calibrate(tasks: dict[str, ArcTask], provider: str, root: Path,
              max_requests: int | None = None) -> dict[str, Any]:
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    cfg = PROVIDERS[provider]
    key = os.environ.get(cfg["env"])
    if not key and provider == "zhipu":
        key = os.environ.get("ZAI_API_KEY")
    if not key:
        raise RuntimeError(f"{provider}: required API key environment variable missing")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    journal = Journal(root / f"{provider}-receipts.jsonl")
    planned = []
    for task in tasks.values():
        body = build_request(task, provider)
        byte_count = len(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode())
        reserve = cost_envelope_cny(byte_count, provider)
        for sample in range(4):
            rid = f"{provider}-{task.task_id}-{sample}"
            if rid not in journal.started and rid not in journal.finished:
                planned.append((task, sample, body, reserve))
    if max_requests is not None:
        planned = planned[:max_requests]
    whole_envelope = sum(x[3] for x in planned)
    prior = journal.known_estimate_cny + journal.unknown_reserved_cny
    if prior + whole_envelope > cfg["cap_cny"]:
        raise RuntimeError(f"{provider}: conservative CNY 300 cap would be exceeded")
    manifest = {"provider": provider, "model": cfg["model"], "task_count": len(tasks),
                "samples_per_task": 4, "max_tokens": MAX_TOKENS,
                "thinking": "enabled", "reasoning_effort": "low", "concurrency": CONCURRENCY,
                "planned_new_requests": len(planned), "prior_estimate_or_reserve_cny": round(prior, 4),
                "new_worst_case_reserve_cny": round(whole_envelope, 4),
                "cap_cny": cfg["cap_cny"], "pricing_source": (
                    "https://api-docs.deepseek.com/quick_start/pricing/" if provider == "deepseek"
                    else "https://docs.z.ai/guides/overview/pricing"),
                "budget_method": "peak uncached input and output rates; 10 CNY/USD safety envelope",
                "created_at": utc_now()}
    manifest_path = root / f"{provider}-calibration-manifest.json"
    with manifest_path.open("w") as stream:
        json.dump(manifest, stream, indent=2)
    os.chmod(manifest_path, 0o600)
    results = []
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(_send_one, task, sample, provider, key, journal, body, reserve)
                   for task, sample, body, reserve in planned]
        for future in as_completed(futures):
            results.append(future.result())
    return {"provider": provider, "new_requests": len(results),
            "http_200": sum(r["http_status"] == 200 for r in results),
            "unknown_transport": sum(r["http_status"] is None for r in results),
            "manifest": str(manifest_path)}
