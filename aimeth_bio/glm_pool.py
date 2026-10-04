"""Adaptive GLM (Coding Plan) call pool.

A long-running process that keeps the account busy without tripping its rate
limit. Work is fed through queue files (JSONL, one job per line) in QUEUE_DIR;
files are rescanned every minute, so new workloads can be added at any time.
Lower file names are served first (prefix files with 10_, 20_, ... for priority).

Job fields: job_id, workload, model, messages, max_tokens, extra (optional),
out_path (where the assistant content is written), extract ("python" to keep
only the longest python code block), provider (default zhipu_coding).

Rate control (AIMD): start at `start` in-flight calls; +1 after every
`grow_every` successful completions up to `cap`; on HTTP 429 the job is
re-queued after a backoff and the limit is halved (floor 2). A 429 means the
request was rejected and not processed, so it is safe to retry. Calls whose
outcome is unknown (network errors, timeouts) are NOT retried automatically.

Live control: ROOT/state/control.json, re-read every minute, may set {"cap": N} (lowers the current
limit at once if needed) and {"drain": true} (launch nothing new, exit when in-flight calls finish;
undispatched jobs stay queued for the next start).
"""
from __future__ import annotations

import json
import random
import re
import sys
import threading
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aimeth_bio.llm_client import chat  # noqa: E402


RATE_CODES = {"1302", "1303", "1305"}  # Zhipu rate/concurrency codes; others (e.g. 1311 plan permission) are permanent


def extract_python(text: str) -> str | None:
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", text or "", flags=re.S)
    if m:
        return max(m, key=len)
    return text if text and ("def transform" in text or "def predict" in text) else None


class Limiter:
    def __init__(self, start: int, cap: int, grow_every: int):
        self.limit, self.cap, self.grow_every = start, cap, grow_every
        self.inflight, self.ok_since_change = 0, 0
        self.cv = threading.Condition()
        self.pause_until = 0.0

    def acquire(self):
        with self.cv:
            while self.inflight >= self.limit or time.time() < self.pause_until:
                self.cv.wait(timeout=1.0)
            self.inflight += 1

    def release(self, outcome: str):
        with self.cv:
            self.inflight -= 1
            if outcome == "ok":
                self.ok_since_change += 1
                if self.ok_since_change >= self.grow_every and self.limit < self.cap:
                    self.limit += 1
                    self.ok_since_change = 0
            elif outcome == "rate_limited":
                self.limit = max(2, self.limit // 2)
                self.ok_since_change = 0
                self.pause_until = time.time() + 30 + random.random() * 30
            self.cv.notify_all()


class Pool:
    def __init__(self, root: Path, start=6, cap=12, grow_every=4):
        self.root = root
        self.qdir, self.rdir, self.state = root / "queue", root / "receipts", root / "state"
        for d in (self.qdir, self.rdir, self.state):
            d.mkdir(parents=True, exist_ok=True)
        self.lim = Limiter(start, cap, grow_every)
        self.pending: deque = deque()
        self.seen: set[str] = set()
        self.lock = threading.Lock()
        self.done_file = self.state / "done.txt"
        if self.done_file.exists():
            self.seen.update(self.done_file.read_text().split())
        self.stats = {"ok": 0, "rate_limited": 0, "error": 0, "unknown": 0}
        self.drain = False

    def control(self):
        f = self.state / "control.json"
        if not f.exists():
            return
        try:
            c = json.loads(f.read_text())
        except Exception:
            return
        with self.lim.cv:
            if "cap" in c:
                self.lim.cap = max(1, int(c["cap"]))
                self.lim.limit = min(self.lim.limit, self.lim.cap)
            self.lim.cv.notify_all()
        if c.get("drain") and not self.drain:
            print(time.strftime("%H:%M:%S"), "drain requested", flush=True)
        self.drain = bool(c.get("drain"))

    def scan(self):
        new = []
        for qf in sorted(self.qdir.glob("*.jsonl")):
            for line in open(qf):
                if not line.strip():
                    continue
                j = json.loads(line)
                if j["job_id"] in self.seen:
                    continue
                if Path(j["out_path"]).exists():
                    self.seen.add(j["job_id"])
                    continue
                self.seen.add(j["job_id"])
                new.append(j)
        with self.lock:
            self.pending.extend(new)
        return len(new)

    def mark_done(self, job_id: str):
        with self.lock, open(self.done_file, "a") as fh:
            fh.write(job_id + "\n")

    def run_job(self, j: dict):
        rec = chat(j.get("provider", "zhipu_coding"), j["model"], j["messages"],
                   str(self.rdir / f"{j['workload']}.jsonl"), max_tokens=j.get("max_tokens", 32768),
                   extra=j.get("extra"), tag={"job_id": j["job_id"], **j.get("meta", {})},
                   timeout=300, total_timeout=3000)
        if rec.get("ok"):
            content = rec.get("content") or ""
            body = extract_python(content) if j.get("extract") == "python" else content
            if body:
                out = Path(j["out_path"])
                out.parent.mkdir(parents=True, exist_ok=True)
                tmp = out.with_suffix(out.suffix + ".tmp")
                tmp.write_text(body)
                tmp.rename(out)
            self.mark_done(j["job_id"])
            return "ok"
        code = None
        try:
            code = str(json.loads(rec.get("error") or "{}").get("error", {}).get("code"))
        except Exception:
            pass
        if rec.get("http_status") == 429 and code in RATE_CODES:
            with self.lock:
                self.pending.append(j)  # rejected by the rate limiter, never processed: safe to retry
            return "rate_limited"
        self.mark_done(j["job_id"])  # failed or unknown outcome: do not resubmit automatically
        return "unknown" if rec.get("outcome") == "unknown" else "error"

    def worker(self, j: dict):
        try:
            outcome = self.run_job(j)
        except Exception as e:  # keep the pool alive
            outcome = "error"
            print("worker exception", type(e).__name__, e, flush=True)
        self.stats[outcome] = self.stats.get(outcome, 0) + 1
        self.lim.release(outcome)

    def serve(self):
        last_scan, last_log = 0.0, 0.0
        while True:
            now = time.time()
            if now - last_scan > 60:
                self.control()
                n = 0 if self.drain else self.scan()
                last_scan = now
                if n:
                    print(time.strftime("%H:%M:%S"), f"queued {n} new jobs", flush=True)
            if now - last_log > 300:
                with self.lock:
                    pend = len(self.pending)
                print(time.strftime("%H:%M:%S"), f"cap={self.lim.cap} limit={self.lim.limit} inflight={self.lim.inflight} pending={pend}",
                      json.dumps(self.stats), flush=True)
                (self.state / "status.json").write_text(json.dumps(
                    {"time": now, "limit": self.lim.limit, "inflight": self.lim.inflight, "pending": pend, **self.stats}))
                last_log = now
            if self.drain:
                if self.lim.inflight == 0:
                    print(time.strftime("%H:%M:%S"), "drained, exiting", json.dumps(self.stats), flush=True)
                    return
                time.sleep(5)
                continue
            with self.lock:
                j = self.pending.popleft() if self.pending else None
            if j is None:
                time.sleep(5)
                continue
            self.lim.acquire()
            threading.Thread(target=self.worker, args=(j,), daemon=True).start()


if __name__ == "__main__":
    root = Path(sys.argv[1])
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    Pool(root, start=start, cap=cap).serve()
