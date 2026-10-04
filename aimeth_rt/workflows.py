"""Budget-matched single-agent workflows (P2 controls).

Both workflows spend at most `n` model calls per task instance and stop early once a program is perfect on
the visible check (ARC: all training pairs), so the budget rule is identical across arms.

  independent : n independent samples of the initial prompt; final = best visible check (ties: earliest).
  self_repair : one conversation; after each program the visible check is returned as feedback and the model
                revises; final = best visible check over the rounds (ties: latest).

Visible check: ARC - training-pair correctness (test outputs never leave the evaluation service);
callus imputation - pseudo-task score on the target's own visible genes (answer keys never read here).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ARC_SYSTEM = (
    "You solve ARC-AGI grid transformation tasks. Return only one Python program "
    "with def transform(grid: list[list[int]]) -> list[list[int]]. "
    "You may import numpy as np. Do not use any other imports, file or network I/O, "
    "dynamic execution, or external state. The program must apply the same rule "
    "to every input. Your final answer must contain executable Python code only."
)


def arc_user_prompt(task: dict) -> str:
    view = {"train": [{"input": p["input"], "output": p["output"]} for p in task["train"]],
            "test": [{"input": p["input"]} for p in task["test"]]}
    return ("Infer the grid rule from the training input/output pairs. The test outputs "
            "are hidden. Write a general transform program. Task data:\n" + json.dumps(view, separators=(",", ":")))


def extract_arc(content: str | None) -> str | None:
    if not isinstance(content, str) or not content.strip():
        return None
    fenced = re.search(r"```(?:python)?\s*\n(.*?)```", content, re.IGNORECASE | re.DOTALL)
    code = fenced.group(1) if fenced else content.strip()
    start = code.find("def transform(")
    imp = code.find("import numpy")
    if imp >= 0 and (start < 0 or imp < start):
        start = imp
    return code[start:].strip() if start >= 0 else None


def extract_bio(content: str | None) -> str | None:
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", content or "", flags=re.S)
    if m:
        return max(m, key=len)
    return content if content and "def predict" in content else None


def _g(grid) -> str:
    return json.dumps(grid, separators=(",", ":"))


def arc_feedback(task: dict, ev: dict) -> str:
    st = ev.get("status")
    if st != "ok":
        return (f"Your program could not be evaluated ({st}): {ev.get('detail', '')[:800]}\n"
                "Fix it. Return only the complete corrected Python program.")
    lines = [f"Your program was run on the {len(ev['train'])} training pairs: "
             f"{sum(t['ok'] for t in ev['train'])} correct."]
    for i, (pair, t) in enumerate(zip(task["train"], ev["train"]), 1):
        if t["ok"]:
            lines.append(f"Pair {i}: correct.")
        elif t.get("error"):
            lines.append(f"Pair {i}: raised {t['error']}")
        else:
            lines.append(f"Pair {i}: WRONG.\n  input: {_g(pair['input'])}\n  expected: {_g(pair['output'])}\n"
                         f"  your output: {_g(t['got'])}")
    lines.append("Re-examine the rule so that it explains every training pair, then return only the complete "
                 "corrected Python program.")
    return "\n".join(lines)


def bio_feedback(ev: dict) -> str:
    st = ev.get("status")
    if st != "ok":
        return (f"Your program failed on a validation run ({st}): {ev.get('detail', '')[:1200]}\n"
                "Fix it. Return only one Python code block containing the full corrected program.")
    msg = (f"Validation (a pseudo-task on the same target section: the same number of genes, chosen at random among "
           f"the VISIBLE genes, were hidden and predicted from the rest; scored exactly like the real task):\n"
           f"  mean smoothed-pattern r = {ev['val_pattern_r']:.3f}, mean single-cell r = {ev['val_cell_r']:.3f}\n"
           f"  worst pseudo-masked genes: {ev['val_worst']}\n  best: {ev['val_best']}\n")
    if not ev.get("real_task_ran"):
        msg += f"On the real task inputs the program did not produce a valid output: {ev.get('real_task_detail', '')[:600]}\n"
    msg += ("Improve the method (the real masked genes are the ones listed earlier). "
            "Return only one Python code block containing the full improved program.")
    return msg


def _score(kind: str, ev: dict) -> float:
    if ev.get("status") != "ok":
        return float("-inf")
    if kind == "arc":
        return ev["train_frac"]
    return ev["val_pattern_r"] if ev.get("real_task_ran") else float("-inf")


def _perfect(kind: str, ev: dict) -> bool:
    return kind == "arc" and ev.get("status") == "ok" and ev.get("train_all", False)


def _step(rec: dict, prog: str | None, ev: dict) -> dict:
    u = rec.get("usage") or {}
    return {"receipt_id": rec.get("receipt_id"), "ok": rec.get("ok"), "finish": rec.get("finish_reason"),
            "prompt_tokens": u.get("prompt_tokens"), "completion_tokens": u.get("completion_tokens"),
            "latency_s": round(rec.get("latency_s", 0), 1),
            "program_sha256": hashlib.sha256(prog.encode()).hexdigest() if prog else None,
            "eval_id": ev.get("eval_id"), "eval": {k: v for k, v in ev.items() if k not in ("train",)},
            "train_ok": [t["ok"] for t in ev.get("train", [])]}


def run_workflow(arm: str, kind: str, task_id: str, task: dict | None, first_prompt: list[dict], llm, ev_client,
                 *, provider: str, model: str, n: int, max_tokens: int, extra: dict | None, tag: dict,
                 val_seed: int = 0, eval_extra: dict | None = None) -> dict:
    extract = extract_arc if kind == "arc" else extract_bio
    steps, best = [], (float("-inf"), None, -1)
    msgs = list(first_prompt)
    for i in range(n):
        call_msgs = list(first_prompt) if arm == "independent" else msgs
        rec = llm.call(provider, model, call_msgs, workload=f"rt_{kind}_{arm}", max_tokens=max_tokens, extra=extra,
                       tag={**tag, "round": i})
        content = rec.get("content") if rec.get("ok") else None
        source = "content"
        if rec.get("ok") and not (content or "").strip() and rec.get("reasoning_content"):
            # Some thinking models (observed: deepseek-flash in multi-turn) finish with the final code block inside
            # the reasoning stream and an empty answer. Same rule for every arm: take the LAST complete block.
            blocks = [b for b in re.findall(r"```(?:python)?\s*\n(.*?)```", rec["reasoning_content"], flags=re.S)
                      if ("def transform" in b if kind == "arc" else "def predict" in b)]
            if blocks:
                content = "```python\n" + blocks[-1] + "```"
                source = "reasoning_fallback"
        prog = extract(content)
        ev = ev_client.run(kind, task_id, prog, val_seed=val_seed, **(eval_extra or {})) if prog else {"status": "no_program"}
        steps.append({**_step(rec, prog, ev), "code_source": source if prog else None})
        sc = _score(kind, ev)
        if sc > best[0] or (arm == "self_repair" and sc == best[0] and sc > float("-inf")):
            best = (sc, ev.get("eval_id"), i)
        if _perfect(kind, ev):
            break
        if arm == "self_repair":
            if content:
                msgs = msgs + [{"role": "assistant", "content": content},
                               {"role": "user", "content": arc_feedback(task, ev) if kind == "arc" else bio_feedback(ev)}]
            # a failed call leaves the conversation unchanged; the next round re-asks
    return {"arm": arm, "kind": kind, "task_id": task_id, "model": model, "n_budget": n, "calls_used": len(steps),
            "final_eval_id": best[1], "final_round": best[2], "final_visible_score": best[0], "steps": steps, **tag}
