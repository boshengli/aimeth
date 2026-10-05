"""Run one frozen P2 comparison arm; generated programs go to the eval service.

Phase-B example (public calls are an explicit CLI opt-in):
  python tools/rt_run.py arc vote --tasks arc2-40.json --arc-archive arc-agi-data.tgz \
    --arc-dir /data/libs/aimeth/data/arc-agi/arc2/data/evaluation --budget-calls 8 \
    --budget-tokens 262144 --provider deepseek --model deepseek-flash --execute-paid --out run.jsonl
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_rt.arc_data import load_arc2_evaluation  # noqa: E402
from aimeth_rt.control_arms import ARMS, Budget, run_control_arm  # noqa: E402
from aimeth_rt.llm import LLM  # noqa: E402
from aimeth_rt.remote_eval import RemoteEvalClient  # noqa: E402
from aimeth_rt.workflows import ARC_SYSTEM, arc_user_prompt, run_workflow  # noqa: E402

PRESETS = {
    "deepseek-flash": {"thinking": {"type": "enabled"}, "reasoning_effort": "low"},
    "glm-5.3-flash": {"thinking": {"type": "enabled"}, "reasoning_effort": "low"},
    "glm-5.3": {"thinking": {"type": "enabled"}},
    ("glm_cc", "glm-5.3"): {"think_budget": 32000, "effort": "high"},
    ("glm_cc", "glm-5.3-flash"): {"think_budget": 32000, "effort": "high"},
    ("local_dsv4", "deepseek-v4-flash-0731"): {"reasoning_effort": "low", "chat_template_kwargs": {"thinking": True}},
}


def _task_ids(spec) -> list[str]:
    if isinstance(spec, dict):
        for key in ("task_ids", "pilot", "tasks"):
            if key in spec:
                spec = spec[key]
                break
    if not isinstance(spec, list):
        raise ValueError("task manifest must be a list or contain task_ids")
    ids = [item["task_id"] if isinstance(item, dict) else item for item in spec]
    if not ids or any(not isinstance(tid, str) or not tid for tid in ids) or len(set(ids)) != len(ids):
        raise ValueError("task manifest must contain unique nonempty task IDs")
    return ids


def load_tasks_arc(a):
    archive_views = load_arc2_evaluation(a.arc_archive) if a.arc_archive else None
    if a.tasks == "ALL":
        ids = sorted(archive_views) if archive_views is not None else sorted(
            p.stem for p in Path(a.arc_dir).glob("*.json"))
    else:
        ids = _task_ids(json.loads(Path(a.tasks).read_text()))
    if archive_views is not None:
        missing = sorted(set(ids) - set(archive_views))
        if missing:
            raise ValueError(f"task manifest IDs absent from ARC archive: {missing[:3]}")
    out = []
    for tid in ids:
        task = archive_views[tid] if archive_views is not None else json.loads(
            (Path(a.arc_dir) / f"{tid}.json").read_text())
        messages = [{"role": "system", "content": ARC_SYSTEM},
                    {"role": "user", "content": arc_user_prompt(task)}]
        out.append((tid, task, messages))
    return out


def load_tasks_bio(a):
    if a.bio_prompt_manifest:
        records = json.loads(Path(a.bio_prompt_manifest).read_text())
        if not isinstance(records, list):
            raise ValueError("public callus prompt manifest must be a JSON list")
        selected = set(a.only or [])
        out = []
        for row in records:
            task_id, messages = row.get("task_id"), row.get("messages")
            if not isinstance(task_id, str) or not isinstance(messages, list):
                raise ValueError("invalid public callus prompt record")
            actual = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if actual != row.get("prompt_sha256"):
                raise ValueError(f"public prompt hash mismatch for {task_id}")
            if not selected or task_id in selected:
                out.append((task_id, None, messages))
        if selected and {tid for tid, _, _ in out} != selected:
            raise ValueError("one or more requested callus IDs are absent from the public prompt manifest")
        return out
    if not a.bench or not a.annot:
        raise ValueError("callus runs require --bench and --annot")
    from aimeth_bio.bench import gene_annotation
    from tools.bio_generate import SYSTEM, build_prompt
    ann = gene_annotation(Path(a.annot))
    masks = {k: [d["id"] for d in values] for k, values in
             json.loads((Path(a.bench) / "mask_sets.json").read_text()).items()}
    selected = set(a.only or [])
    out = []
    for jf in sorted((Path(a.bench) / "tasks").glob("*.json")):
        info = json.loads(jf.read_text())
        if selected and info["task_id"] not in selected:
            continue
        prompt = build_prompt(info, ann, masks[info["mask_set"]])
        out.append((info["task_id"], None,
                    [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]))
    if selected and {tid for tid, _, _ in out} != selected:
        raise ValueError("one or more requested callus IDs are absent from the task directory")
    return out


def _jsonl_append(path: Path, row: dict, lock: threading.Lock):
    path.parent.mkdir(parents=True, exist_ok=True)
    with lock, path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def finalize_fenced_tasks(out: Path, state_log: Path, fenced: set[tuple[str, int]], *,
                          kind: str, arm: str, provider: str, model: str,
                          budget: Budget | None, model_max_tokens: int, seed: int,
                          run_name: str) -> int:
    """Persist interrupted starts as unknown without ever dispatching them again."""
    existing = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                existing.add((row["task_id"], row["rep"]))
    lock = threading.Lock()
    added = 0
    for task_id, rep in sorted(fenced):
        if (task_id, rep) in existing:
            continue
        budget_spec = ({"calls": budget.calls,
                        "completion_reasoning_tokens": budget.tokens} if budget else None)
        config = {"kind": kind, "arm": arm, "task_id": task_id, "rep": rep,
                  "provider": provider, "model": model,
                  "budget": budget_spec, "seed": seed + rep}
        row = {**config, "arm": arm, "condition": "single_model",
               "model_max_tokens": model_max_tokens,
               "n_budget": budget.calls if budget else None,
               "calls_used": None, "completion_reasoning_tokens_used": None,
               "prompt_tokens_reported": None, "final_eval_id": None,
               "final_round": -1, "final_visible_score": None, "contributor_eval_ids": [],
               "steps": [], "stop_reason": "started_task_outcome_unknown_not_retried",
               "dispatch_outcome": "unknown", "cost_estimate_cny": None,
               "run_cost_estimate_cny_cumulative": None, "run": run_name}
        _jsonl_append(out, row, lock)
        _jsonl_append(state_log, {"event": "task_finalized_unknown", **config}, lock)
        existing.add((task_id, rep))
        added += 1
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["arc", "bio"])
    ap.add_argument("arm", choices=ARMS)
    ap.add_argument("--tasks", help="JSON list of frozen task IDs, or ALL")
    ap.add_argument("--arc-dir", help="answer-bearing evaluator directory; never mounted for an agent")
    ap.add_argument("--arc-archive", help="ARC-AGI-2 archive used only to create answer-free public views")
    ap.add_argument("--bench"); ap.add_argument("--annot"); ap.add_argument("--only", nargs="*")
    ap.add_argument("--bio-prompt-manifest", help="frozen answer-free prompt export from the cluster dataset")
    ap.add_argument("--out", required=True)
    ap.add_argument("--state-log", help="append-only start log used to fence duplicate task dispatch")
    ap.add_argument("--evalq", default="/data/libs/aimeth/rt/runs/p2-controls-v1/evalq")
    ap.add_argument("--eval-transport", choices=["ssh", "local"], default="ssh")
    ap.add_argument("--remote-target", default="libs@172.16.30.19")
    ap.add_argument("--receipts", help="private append-only provider receipts (default: <out dir>/receipts)")
    ap.add_argument("--provider", default="deepseek")
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--model-max-tokens", type=int, default=262144,
                    help="recorded effective output ceiling; single_long is capped here")
    ap.add_argument("--budget-calls", type=int)
    ap.add_argument("--budget-tokens", type=int, help="completion + reasoning tokens per task instance")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--llm-start", type=int, default=2)
    ap.add_argument("--llm-cap", type=int, default=8)
    ap.add_argument("--reasoning-effort", default=None)
    ap.add_argument("--execute-paid", action="store_true",
                    help="explicit gate for external billed providers; local_dsv4 does not use paid APIs")
    ap.add_argument("--finalize-fenced", action="store_true",
                    help="record previously started but unsettled tasks as unknown; never resend them")
    ap.add_argument("--seed", type=int, default=1000)
    ap.add_argument("--k", type=int); ap.add_argument("--m", type=int, default=3)
    ap.add_argument("--population-size", type=int, default=8)
    a = ap.parse_args()

    budgeted = a.budget_calls is not None or a.budget_tokens is not None or a.arm not in ("independent", "self_repair")
    if a.kind == "arc" and (not a.arc_dir or (budgeted and not a.arc_archive)):
        ap.error("ARC controls require --arc-dir; Phase-B ARC-2 additionally requires --arc-archive")
    if a.kind == "arc" and not a.tasks:
        ap.error("ARC requires a frozen --tasks manifest or ALL")
    if budgeted and (a.budget_calls is None or a.budget_tokens is None):
        ap.error("budgeted P2 controls require both --budget-calls and --budget-tokens")
    if budgeted and a.provider != "local_dsv4" and not a.execute_paid:
        ap.error("budgeted external-provider calls are disabled unless --execute-paid is explicit")
    if budgeted and a.provider == "deepseek" and not os.environ.get("DEEPSEEK_API_KEY"):
        ap.error("DEEPSEEK_API_KEY must be supplied through the process environment")
    if a.model_max_tokens < 1 or a.workers < 1:
        ap.error("model output cap and worker count must be positive")
    try:
        budget = Budget(a.budget_calls, a.budget_tokens) if budgeted else None
        tasks = load_tasks_arc(a) if a.kind == "arc" else load_tasks_bio(a)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        ap.error(str(exc))
    if not tasks:
        ap.error("no tasks selected")

    out = Path(a.out)
    state_log = Path(a.state_log) if a.state_log else out.with_suffix(".events.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    completed = set()
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                completed.add((row["task_id"], row["rep"]))
    started = set()
    if state_log.exists():
        for line in state_log.read_text().splitlines():
            if line.strip():
                row = json.loads(line)
                if row.get("event") == "task_started":
                    started.add((row["task_id"], row["rep"]))
    fenced = started - completed
    if fenced and not a.finalize_fenced:
        ap.error("started but unsettled tasks are fenced; use --finalize-fenced to record them as unknown without retry")
    if fenced:
        count = finalize_fenced_tasks(out, state_log, fenced, kind=a.kind, arm=a.arm,
                                      provider=a.provider, model=a.model, budget=budget,
                                      model_max_tokens=a.model_max_tokens, seed=a.seed,
                                      run_name=out.stem)
        completed.update(fenced)
        print(f"finalized_fenced_unknown={count}; no model request was repeated", flush=True)
    jobs = [(tid, task, msgs, rep) for rep in range(1) for tid, task, msgs in tasks
            if (tid, rep) not in completed and (tid, rep) not in started]
    print(time.strftime("%Y-%m-%dT%H:%M:%S%z"),
          f"{a.kind}/{a.arm}: queued={len(jobs)} completed={len(completed)} fenced_incomplete={len(fenced)}",
          flush=True)

    lock_path = out.with_suffix(out.suffix + ".lock")
    lock_handle = lock_path.open("a+")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        ap.error(f"another process holds the run lock for {out}")
    receipts_dir = a.receipts or str(out.parent / "receipts")
    llm = LLM(receipts_dir, start=a.llm_start, cap=a.llm_cap, budget_cny=None)
    if a.eval_transport == "ssh":
        ev = RemoteEvalClient(a.remote_target, a.evalq,
                              stderr_path=out.with_suffix(out.suffix + ".eval-ssh.stderr.log"))
    else:
        from aimeth_rt.evalq import EvalClient
        ev = EvalClient(a.evalq)
    lock = threading.Lock()
    extra = dict(PRESETS.get((a.provider, a.model)) or ({} if a.provider == "glm_cc" else PRESETS.get(a.model)) or {})
    if a.reasoning_effort:
        extra["reasoning_effort"] = a.reasoning_effort

    def one(job):
        tid, task, msgs, rep = job
        config = {"kind": a.kind, "arm": a.arm, "task_id": tid, "rep": rep,
                  "provider": a.provider, "model": a.model,
                  "budget": {"calls": budget.calls, "tokens": budget.tokens} if budgeted else None,
                  "seed": a.seed + rep}
        _jsonl_append(state_log, {"event": "task_started", "at": time.time(), **config}, lock)
        if budgeted:
            result = run_control_arm(a.arm, a.kind, tid, task, msgs, llm, ev, budget,
                                     provider=a.provider, model=a.model,
                                     model_max_tokens=a.model_max_tokens, extra=extra,
                                     seed=a.seed + rep, k=a.k, m=a.m,
                                     population_size=a.population_size, val_seed=1000 + rep,
                                     eval_extra={"arc_dir": a.arc_dir} if a.kind == "arc" else {},
                                     tag={"rep": rep, "run": out.stem})
        else:
            result = run_workflow(a.arm, a.kind, tid, task, msgs, llm, ev,
                                  provider=a.provider, model=a.model, n=8,
                                  max_tokens=min(a.model_max_tokens, 32768), extra=extra,
                                  tag={"rep": rep, "run": out.stem}, val_seed=1000 + rep,
                                  eval_extra={"arc_dir": a.arc_dir} if a.kind == "arc" else {})
        task_cost = sum((step.get("cost_envelope_cny_estimate") or 0.0)
                        for step in result.get("steps", []))
        result.update(cost_estimate_cny=round(task_cost, 6),
                      run_cost_estimate_cny_cumulative=round(llm.spent_cny, 6), **config)
        with lock, out.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return result

    try:
        with ThreadPoolExecutor(a.workers) as pool:
            for index, _ in enumerate(pool.map(one, jobs), 1):
                if index % 5 == 0 or index == len(jobs):
                    print(time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                          f"settled={index}/{len(jobs)} provider_stats={json.dumps(llm.stats)} "
                          f"cost_envelope_cny={llm.spent_cny:.4f}", flush=True)
        print("complete", json.dumps({"records": len(jobs), "fenced_incomplete": len(fenced),
                                      "provider_stats": llm.stats,
                                      "cost_envelope_cny": round(llm.spent_cny, 6)}), flush=True)
    finally:
        if hasattr(ev, "close"):
            ev.close()


if __name__ == "__main__":
    main()
