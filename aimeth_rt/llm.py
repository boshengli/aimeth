"""Thread-safe LLM caller with an AIMD concurrency limiter shared by every workflow in one process.

A rate-limit rejection (HTTP 429 with a Zhipu rate code) was never processed, so it is retried after the
limiter's pause. Any other failure, including an unknown outcome, is returned to the workflow and counts
as a spent call; it is never resubmitted automatically.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aimeth_bio.glm_pool import Limiter, RATE_CODES  # noqa: E402
from aimeth_bio.llm_client import chat  # noqa: E402


class LLM:
    def __init__(self, receipts_dir: str, start: int = 4, cap: int = 8):
        self.lim = Limiter(start, cap, 4)
        self.rdir = Path(receipts_dir)
        self.rdir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.stats = {"ok": 0, "rate_limited": 0, "error": 0, "unknown": 0}

    def call(self, provider: str, model: str, messages: list[dict], *, workload: str, max_tokens: int,
             extra: dict | None = None, tag: dict | None = None) -> dict:
        while True:
            self.lim.acquire()
            try:
                rec = chat(provider, model, messages, str(self.rdir / f"{workload}.jsonl"), max_tokens=max_tokens,
                           extra=extra, tag=tag, timeout=300, total_timeout=3000)
            except Exception as e:  # defensive: chat() already catches, but keep the limiter consistent
                rec = {"ok": False, "error": f"{type(e).__name__}: {e}", "outcome": "unknown"}
            code = None
            try:
                code = str(json.loads(rec.get("error") or "{}").get("error", {}).get("code"))
            except Exception:
                pass
            if rec.get("ok"):
                outcome = "ok"
            elif rec.get("http_status") == 429 and code in RATE_CODES:
                outcome = "rate_limited"
            else:
                outcome = "unknown" if rec.get("outcome") == "unknown" else "error"
            self.lim.release(outcome)
            with self.lock:
                self.stats[outcome] += 1
            if outcome != "rate_limited":
                return rec
