"""SSH transport to the existing private evaluation queue; API keys stay local."""

from __future__ import annotations

import json
import base64
from pathlib import Path
import shlex
import subprocess
import threading
import time
from uuid import uuid4


_REMOTE_PROXY = r'''import concurrent.futures, json, os, re, sys, time, uuid
from pathlib import Path
root = Path(sys.argv[1])
pending, done = root / "pending", root / "done"
out_lock = __import__("threading").Lock()

def process(req):
    rid = req.get("request_id")
    try:
        kind = req.get("kind")
        task_id = req.get("task_id")
        if kind not in ("arc", "bio", "aggregate") or not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
            raise ValueError("invalid evaluation request")
        jid = str(int(time.time() * 1000)) + "-" + uuid.uuid4().hex[:12]
        job = {"id": jid, "kind": kind, "task_id": task_id, "program": req.get("program") or ""}
        if kind == "aggregate":
            job.update(source_kind=req["source_kind"], mode=req["mode"], eval_ids=req["eval_ids"])
        else:
            extra = req.get("extra") or {}
            if set(extra) - {"arc_dir", "val_seed"}:
                raise ValueError("unsupported evaluator options")
            job.update(extra)
        target = pending / (jid + ".json")
        temp = pending / ("." + jid + ".tmp")
        with temp.open("x") as stream:
            stream.write(json.dumps(job, separators=(",", ":")))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, target)
        result_path = done / (jid + ".json")
        deadline = time.monotonic() + float(req.get("timeout_s", 3600))
        while time.monotonic() < deadline:
            if result_path.exists():
                result = json.loads(result_path.read_text())
                result["eval_id"] = jid
                return {"request_id": rid, "result": result}
            time.sleep(1)
        return {"request_id": rid, "result": {"status": "eval_timeout", "eval_id": jid}}
    except Exception as exc:
        return {"request_id": rid, "result": {"status": "remote_eval_error", "detail": type(exc).__name__}}

with concurrent.futures.ThreadPoolExecutor(max_workers=32) as pool:
    futures = set()
    for line in sys.stdin:
        if not line.strip():
            continue
        futures.add(pool.submit(process, json.loads(line)))
    for future in concurrent.futures.as_completed(futures):
        with out_lock:
            sys.stdout.write(json.dumps(future.result(), separators=(",", ":")) + "\n")
            sys.stdout.flush()
'''


class RemoteEvalClient:
    """Submit visible-check jobs through one key-authenticated SSH session.

    No model credential is sent to SSH. On a lost SSH outcome, this adapter
    returns an error without resubmitting the evaluation request.
    """

    def __init__(self, target: str = "libs@172.16.30.19",
                 root: str = "/data/libs/aimeth/rt/runs/p2-controls-v1/evalq",
                 stderr_path: str | Path | None = None,
                 wait_timeout: float = 3600):
        if not target or any(ch.isspace() for ch in target):
            raise ValueError("invalid SSH target")
        self.wait_timeout = wait_timeout
        encoded = base64.b64encode(_REMOTE_PROXY.encode()).decode()
        wrapper = "import base64;exec(base64.b64decode(" + repr(encoded) + "))"
        command = "python3 -u -c " + shlex.quote(wrapper) + " " + shlex.quote(root)
        self.proc = subprocess.Popen(
            ["ssh", "-T", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
             "-o", "ConnectTimeout=8", target, command],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        self.lock = threading.Lock()
        self.condition = threading.Condition()
        self.pending: dict[str, dict] = {}
        self.closed = False
        self.stderr_path = Path(stderr_path) if stderr_path else None
        self.reader = threading.Thread(target=self._read_results, daemon=True)
        self.reader.start()
        self.stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self.stderr_reader.start()

    def _read_results(self):
        try:
            for line in self.proc.stdout:
                try:
                    data = json.loads(line)
                    rid = data.get("request_id")
                    with self.condition:
                        slot = self.pending.get(rid)
                        if slot is not None:
                            slot["result"] = data.get("result") or {"status": "remote_eval_error"}
                            slot["ready"] = True
                        self.condition.notify_all()
                except Exception:
                    continue
        finally:
            with self.condition:
                self.closed = True
                for slot in self.pending.values():
                    if not slot.get("ready"):
                        slot["result"] = {"status": "remote_proxy_lost"}
                        slot["ready"] = True
                self.condition.notify_all()

    def _read_stderr(self):
        if not self.proc.stderr:
            return
        if self.stderr_path:
            self.stderr_path.parent.mkdir(parents=True, exist_ok=True)
            with self.stderr_path.open("a", encoding="utf-8") as out:
                for line in self.proc.stderr:
                    out.write(line)
                    out.flush()
        else:
            for _ in self.proc.stderr:
                pass

    def _request(self, payload: dict) -> dict:
        rid = uuid4().hex
        slot = {"ready": False, "result": None}
        payload["request_id"] = rid
        with self.condition:
            if self.closed or self.proc.poll() is not None:
                return {"status": "remote_proxy_lost"}
            self.pending[rid] = slot
        try:
            with self.lock:
                self.proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
                self.proc.stdin.flush()
        except Exception:
            with self.condition:
                self.pending.pop(rid, None)
            return {"status": "remote_proxy_lost"}
        deadline = time.monotonic() + self.wait_timeout
        with self.condition:
            while not slot["ready"]:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.pending.pop(rid, None)
                    return {"status": "remote_proxy_timeout"}
                self.condition.wait(remaining)
            self.pending.pop(rid, None)
            return slot["result"]

    def run(self, kind: str, task_id: str, program: str, **extra) -> dict:
        result = self._request({"kind": kind, "task_id": task_id,
                                "program": program or "", "extra": extra,
                                "timeout_s": self.wait_timeout})
        if result.get("eval_id"):
            return result
        return {"eval_id": None, **result}

    def aggregate(self, kind: str, task_id: str, eval_ids: list[str], mode: str) -> dict:
        result = self._request({"kind": "aggregate", "task_id": task_id,
                                "source_kind": kind, "mode": mode,
                                "eval_ids": eval_ids, "timeout_s": self.wait_timeout})
        return result

    def close(self):
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        self.reader.join(timeout=2)
        self.stderr_reader.join(timeout=2)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if stream and not stream.closed:
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
