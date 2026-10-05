"""Streaming chat client for DeepSeek / Zhipu with append-only receipts.

Keys are read from ~/.config/aimeth/api.env at call time and never logged.
Streaming keeps long reasoning calls alive. Every attempt writes one JSON line
with request metadata, the assembled message (content + reasoning), usage,
latency, finish_reason and the last raw chunk.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid

ENDPOINTS = {
    "deepseek": ("https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY"),
    "zhipu": ("https://open.bigmodel.cn/api/paas/v4/chat/completions", "ZHIPU_API_KEY"),
    # GLM Coding Plan quota endpoint (same key)
    "zhipu_coding": ("https://open.bigmodel.cn/api/coding/paas/v4/chat/completions", "ZHIPU_API_KEY"),
    # Local DeepSeek-V4-Flash-0731 served by SGLang on GPU08 (cluster shared weights; key generated locally)
    "local_dsv4": ("http://gpu08:30500/v1/chat/completions", "LOCAL_DSV4_KEY"),
}
_lock = threading.Lock()


def _key(name: str) -> str:
    for line in open(os.path.expanduser("~/.config/aimeth/api.env")):
        line = line.strip()
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise KeyError(name)


def chat(provider: str, model: str, messages: list[dict], receipts_path: str, *, max_tokens: int = 16384,
         timeout: int = 300, total_timeout: int = 3600, extra: dict | None = None, tag: dict | None = None) -> dict:
    """timeout = max silence between stream chunks; total_timeout = wall cap for one call."""
    url, key_name = ENDPOINTS[provider]
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "stream": True}
    if provider in ("deepseek", "local_dsv4"):
        body["stream_options"] = {"include_usage": True}
    if extra:
        body.update(extra)
    t0 = time.time()
    rec = {"receipt_id": str(uuid.uuid4()), "provider": provider, "endpoint": url, "model": model,
           "max_tokens": max_tokens, "request_extra": extra or {}, "tag": tag or {}, "started_unix": t0}
    content, reasoning, finish, usage, served, last = [], [], None, None, None, None
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + _key(key_name),
                                              "Content-Type": "application/json", "Accept": "text/event-stream"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            rec["http_status"] = r.status
            for raw in r:
                if time.time() - t0 > total_timeout:
                    raise TimeoutError("total_timeout exceeded")
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                last = chunk
                served = chunk.get("model", served)
                if chunk.get("usage"):
                    usage = chunk["usage"]
                for ch in chunk.get("choices") or []:
                    d = ch.get("delta") or {}
                    if d.get("content"):
                        content.append(d["content"])
                    if d.get("reasoning_content"):
                        reasoning.append(d["reasoning_content"])
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
        rec.update(ok=True, content="".join(content), reasoning_content="".join(reasoning),
                   finish_reason=finish, usage=usage, served_model=served, last_chunk=last)
    except urllib.error.HTTPError as e:
        rec.update(ok=False, http_status=e.code, error=e.read().decode(errors="replace")[:4000])
    except Exception as e:  # network / timeout: outcome unknown, never auto-resubmitted here
        rec.update(ok=False, error=f"{type(e).__name__}: {e}"[:2000], outcome="unknown",
                   partial_content="".join(content)[-4000:], partial_reasoning_chars=sum(map(len, reasoning)))
    rec["latency_s"] = time.time() - t0
    with _lock, open(receipts_path, "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
