"""GLM Coding Plan access through Claude Code (an officially supported tool for the plan).

Each call runs the Claude Code CLI in print mode (`/data/libs/aimeth/cc/cc_glm.sh`, which points Claude Code at
Zhipu's Anthropic-compatible endpoint and reads the key from ~/.config/aimeth/api.env without printing it) with:
all built-in tools disabled (`--tools ""`, MCP tools denied), the default system prompt replaced by the experiment's
system prompt, one turn, JSON output. The returned record mirrors `llm_client.chat` (ok, content, usage with
prompt/completion tokens, finish_reason, latency) and is appended to the receipts file.

Multi-turn conversations (self-repair) continue the Claude Code session with `--resume`: after a successful call the
session id is remembered under a hash of the conversation including the new assistant message, so a later call whose
messages extend that conversation by one user turn resumes it. If no session is found, the earlier turns are
flattened into one prompt (recorded as `conversation_mode = flattened`).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
import uuid

CC = "/data/libs/aimeth/cc/cc_glm.sh"
ENDPOINT = "claude-code -> https://open.bigmodel.cn/api/anthropic"
_lock = threading.Lock()
_sessions: dict[str, str] = {}


def _key(msgs: list[dict]) -> str:
    return hashlib.sha256(json.dumps([[m["role"], m["content"]] for m in msgs], ensure_ascii=False).encode()).hexdigest()


def _flatten(turns: list[dict]) -> str:
    parts = ["The conversation so far is reproduced below; continue it by answering the last USER message.\n"]
    for m in turns:
        parts.append(f"=== {m['role'].upper()} ===\n{m['content']}\n")
    return "\n".join(parts)


def cc_chat(model: str, messages: list[dict], receipts_path: str, *, max_tokens: int = 32000,
            think_budget: int | None = None, effort: str | None = None, timeout: int = 3600,
            tag: dict | None = None) -> dict:
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system") or "You are a helpful assistant."
    turns = [m for m in messages if m["role"] != "system"]
    t0 = time.time()
    rec = {"receipt_id": str(uuid.uuid4()), "provider": "glm_cc", "endpoint": ENDPOINT, "model": model,
           "max_tokens": max_tokens, "request_extra": {"think_budget": think_budget, "effort": effort},
           "tag": tag or {}, "started_unix": t0}
    resume = None
    if len(turns) > 1:
        with _lock:
            resume = _sessions.get(_key(messages[:-1]))
        prompt = turns[-1]["content"] if resume else _flatten(turns)
        rec["conversation_mode"] = "resumed" if resume else "flattened"
    else:
        prompt = turns[0]["content"]
        rec["conversation_mode"] = "single"
    env = dict(os.environ, CLAUDE_CODE_MAX_OUTPUT_TOKENS=str(max_tokens))
    if think_budget:
        env["MAX_THINKING_TOKENS"] = str(think_budget)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as sf:
        sf.write(system)
        sys_path = sf.name
    cmd = [CC, "-p", "--output-format", "json", "--model", model, "--tools", "", "--disallowedTools", "mcp__*",
           "--strict-mcp-config", "--system-prompt-file", sys_path, "--max-turns", "1"]
    if effort:
        cmd += ["--effort", effort]
    if resume:
        cmd += ["--resume", resume]
    try:
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, env=env)
        out = None
        for line in reversed(p.stdout.strip().splitlines()):
            try:
                out = json.loads(line)
                break
            except Exception:
                continue
        if out is None:
            rec.update(ok=False, outcome="unknown", error=("no JSON result; stderr: " + p.stderr[-1500:]))
        else:
            u = out.get("usage") or {}
            usage = {"prompt_tokens": (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
                     + (u.get("cache_creation_input_tokens") or 0),
                     "completion_tokens": u.get("output_tokens") or 0,
                     "cache_read_tokens": u.get("cache_read_input_tokens") or 0}
            rec.update(session_id=out.get("session_id"), usage=usage, finish_reason=out.get("stop_reason"),
                       num_turns=out.get("num_turns"), duration_api_ms=out.get("duration_api_ms"),
                       api_error_status=out.get("api_error_status"), terminal_reason=out.get("terminal_reason"))
            if out.get("is_error") or out.get("subtype") != "success":
                st = out.get("api_error_status")
                rec.update(ok=False, http_status=st if isinstance(st, int) else None,
                           error=json.dumps({"error": {"code": "1302" if st == 429 else str(st),
                                                       "message": str(out.get("result"))[:1500]}}))
            else:
                rec.update(ok=True, content=out.get("result") or "", reasoning_content="")
                with _lock:
                    _sessions[_key(messages + [{"role": "assistant", "content": rec["content"]}])] = out.get("session_id")
    except subprocess.TimeoutExpired:
        rec.update(ok=False, outcome="unknown", error=f"timeout after {timeout}s")
    except Exception as e:
        rec.update(ok=False, outcome="unknown", error=f"{type(e).__name__}: {e}"[:1500])
    finally:
        os.unlink(sys_path)
    rec["latency_s"] = time.time() - t0
    with _lock, open(receipts_path, "a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
