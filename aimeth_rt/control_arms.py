"""Budget-matched, non-developmental P2 controls.

Every arm uses one configured model. ARC answer-bearing test outputs stay in
the evaluation service; only visible checks and program text are returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re

from .workflows import (ARC_SYSTEM, _perfect, _score, arc_feedback, arc_user_prompt,
                        bio_feedback, extract_arc, extract_bio)
from .llm import PRICES_USD_PER_M, CNY_PER_USD_ENVELOPE


ARMS = ("independent", "self_repair", "single_long", "vote",
        "orchestrator_worker", "debate", "evolution")
PROMPT_TEMPLATES = {
    "orchestrator_plan": "Return JSON with a 'plans' array of distinct solution strategies. Do not write the final program. Number of plans: {k}",
    "worker": "Implement this plan as a complete program: {plan}",
    "orchestrator_assign": "Assign one worker revision using only these programs and visible-check results. Return a concise instruction, not a program:\n{summaries}",
    "worker_revision": "{instruction}\nCurrent program:\n{program}\nVisible feedback:\n{feedback}",
    "debater_propose": "Propose an independent program as debater {index}.",
    "debater_revision": "Review the programs and visible checks, then return a revised complete program:\n{summaries}",
    "evolution_planner": "Suggest mutation and crossover strategies for program search; do not write a program.",
    "evolution_propose": "Use non-spatial evolutionary {mode} to propose one new complete program. Parents and visible checks: {parents}",
}


@dataclass(frozen=True)
class Budget:
    calls: int
    tokens: int

    def __post_init__(self):
        if type(self.calls) is not int or self.calls < 1:
            raise ValueError("calls must be a positive integer")
        if type(self.tokens) is not int or self.tokens < 0:
            raise ValueError("tokens must be a nonnegative integer")


class BudgetLedger:
    """Per-task logical-call and completion/reasoning-token ceilings."""

    def __init__(self, budget: Budget, provider: str, model: str,
                 model_max_tokens: int, llm, extra: dict | None = None,
                 tag: dict | None = None):
        if not provider or not model or type(model_max_tokens) is not int or model_max_tokens < 1:
            raise ValueError("provider, model and a positive model output cap are required")
        self.budget, self.provider, self.model = budget, provider, model
        self.model_max_tokens, self.llm, self.extra = model_max_tokens, llm, extra or {}
        self.tag = tag or {}
        self.used_calls = 0
        self.used_tokens = 0
        self.events: list[dict] = []

    def call(self, role: str, messages: list[dict], requested_max: int) -> tuple[dict, dict] | None:
        if self.used_calls >= self.budget.calls or self.used_tokens >= self.budget.tokens:
            return None
        cap = min(requested_max, self.model_max_tokens,
                  self.budget.tokens - self.used_tokens)
        if cap < 1:
            return None
        prompt_sha = sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        rec = self.llm.call(self.provider, self.model, messages,
                            workload=f"rt_control_{role}", max_tokens=cap,
                            extra=self.extra, tag={**self.tag, "role": role,
                                                   "logical_call": self.used_calls})
        if rec.get("outcome") == "not_sent":
            return None
        usage = rec.get("usage") or {}
        generated = usage.get("completion_tokens")
        if isinstance(generated, bool) or not isinstance(generated, int) or generated < 0:
            generated = cap if rec.get("outcome") == "unknown" else 0
        if generated > cap:
            raise RuntimeError("provider exceeded requested max_tokens; preserve receipt and stop")
        input_rate, output_rate = PRICES_USD_PER_M.get(self.model, (0.0, 0.0))
        cost_envelope_cny = ((usage.get("prompt_tokens") or 0) * input_rate
                             + generated * output_rate) / 1_000_000 * CNY_PER_USD_ENVELOPE
        self.used_calls += 1
        self.used_tokens += generated
        event = {"role": role, "provider": self.provider, "model": self.model,
                 "requested_max_tokens": cap, "completion_reasoning_tokens": generated,
                 "usage_known": type(usage.get("completion_tokens")) is int,
                 "prompt_tokens": usage.get("prompt_tokens"),
                 "completion_tokens": usage.get("completion_tokens"),
                 "reported_completion_tokens": usage.get("completion_tokens"),
                 "cost_envelope_cny_estimate": round(cost_envelope_cny, 8),
                 "finish_reason": rec.get("finish_reason"),
                 "outcome": rec.get("outcome", "ok" if rec.get("ok") else "error"),
                 "receipt_id": rec.get("receipt_id"), "prompt_sha256": prompt_sha,
                 "prompt_template_sha256": self._template_hash(role),
                 "ok": bool(rec.get("ok"))}
        self.events.append(event)
        return rec, event

    @staticmethod
    def _template_hash(role: str) -> str | None:
        aliases = {"orchestrator_plan": "orchestrator_plan",
                   "worker": "worker", "orchestrator_assign": "orchestrator_assign",
                   "worker_revision": "worker_revision", "debater_0": "debater_propose",
                   "debater_1": "debater_propose", "debater_2": "debater_propose",
                   "debater_0_revision": "debater_revision", "debater_1_revision": "debater_revision",
                   "debater_2_revision": "debater_revision", "evolution_planner": "evolution_planner",
                   "evolution_mutation": "evolution_propose", "evolution_crossover": "evolution_propose",
                   "independent": None, "self_repair": None, "single_long": None,
                   "vote_sampler": None}
        name = aliases.get(role)
        if name is None:
            return None
        return sha256(PROMPT_TEMPLATES[name].encode()).hexdigest()


@dataclass
class Candidate:
    code: str
    evaluation: dict
    score: float
    step: int


def _public_arc(task: dict) -> dict:
    if not task or not task.get("train") or not task.get("test"):
        raise ValueError("ARC task requires nonempty training and test inputs")
    return {"train": [{"input": p["input"], "output": p["output"]} for p in task["train"]],
            "test": [{"input": p["input"]} for p in task["test"]]}


def _extract(kind: str, rec: dict) -> tuple[str | None, str | None]:
    if not rec.get("ok"):
        return None, None
    content = rec.get("content")
    source = "content"
    if not (content or "").strip() and rec.get("reasoning_content"):
        blocks = [b for b in re.findall(
            r"```(?:python)?\s*\n(.*?)```", rec["reasoning_content"], flags=re.S)
            if ("def transform" in b if kind == "arc" else "def predict" in b)]
        if blocks:
            content = "```python\n" + blocks[-1] + "```"
            source = "reasoning_fallback"
    code = (extract_arc if kind == "arc" else extract_bio)(content)
    return code, source if code else None


def _visible_summary(candidate: Candidate) -> dict:
    ev = candidate.evaluation
    return {"step": candidate.step, "visible_score": candidate.score,
            "status": ev.get("status"), "eval_id": ev.get("eval_id"),
            "program": candidate.code}


def _plans(text: str | None, k: int) -> list[str]:
    try:
        parsed = json.loads(text or "")
        values = parsed.get("plans", []) if isinstance(parsed, dict) else []
    except json.JSONDecodeError:
        values = [line.strip(" -0123456789.)") for line in (text or "").splitlines()]
    unique = []
    for value in values:
        if isinstance(value, str) and value.strip() and value.strip() not in unique:
            unique.append(value.strip())
    while len(unique) < k:
        unique.append(f"Try an independent rule hypothesis #{len(unique) + 1}.")
    return unique[:k]


def run_control_arm(arm: str, kind: str, task_id: str, task: dict | None,
                    first_prompt: list[dict], llm, ev_client, budget: Budget, *,
                    provider: str, model: str, model_max_tokens: int,
                    extra: dict | None = None, seed: int = 0, k: int | None = None,
                    m: int = 3, population_size: int = 8, val_seed: int = 0,
                    eval_extra: dict | None = None, tag: dict | None = None) -> dict:
    if arm not in ARMS or kind not in ("arc", "bio"):
        raise ValueError("unsupported arm/task family")
    if m < 1 or population_size < 1:
        raise ValueError("positive debate and population sizes required")
    if arm == "orchestrator_worker" and k is not None and (k < 1 or k >= budget.calls):
        raise ValueError("k must be positive and leave at least one call for worker revision")

    public_task = _public_arc(task) if kind == "arc" else None
    prompt = ([{"role": "system", "content": ARC_SYSTEM},
               {"role": "user", "content": arc_user_prompt(public_task)}]
              if kind == "arc" else list(first_prompt))
    ledger = BudgetLedger(budget, provider, model, model_max_tokens, llm, extra,
                          {**(tag or {}), "task_id": task_id, "arm": arm})
    import random
    rng = random.Random(seed)
    steps: list[dict] = []
    candidates: list[Candidate] = []
    stopped: str | None = None
    eval_options = dict(eval_extra or {})
    per_call = max(1, budget.tokens // budget.calls) if budget.calls else 1

    def invoke(role: str, messages: list[dict], cap: int = per_call) -> Candidate | None:
        nonlocal stopped
        called = ledger.call(role, messages, cap)
        if called is None:
            stopped = stopped or "budget_exhausted_or_not_sent"
            return None
        rec, event = called
        code, source = _extract(kind, rec)
        ev = (ev_client.run(kind, task_id, code, val_seed=val_seed, **eval_options)
              if code else {"status": "no_program"})
        score = _score(kind, ev)
        step = {**event, "code_source": source,
                "program_sha256": sha256(code.encode()).hexdigest() if code else None,
                "eval_id": ev.get("eval_id"), "visible_status": ev.get("status"),
                "visible_score": score if score > float("-inf") else None,
                "train_all": bool(ev.get("train_all")) if kind == "arc" else None}
        steps.append(step)
        if code and score > float("-inf"):
            candidate = Candidate(code, ev, score, len(steps) - 1)
            candidates.append(candidate)
            if _perfect(kind, ev):
                stopped = "arc_train_perfect"
            return candidate
        return None

    if arm == "single_long":
        invoke("single_long", prompt, min(budget.tokens, model_max_tokens))

    elif arm in ("independent", "self_repair", "vote"):
        messages = list(prompt)
        for _ in range(budget.calls):
            c = invoke("vote_sampler" if arm == "vote" else arm,
                       prompt if arm in ("independent", "vote") else messages)
            if stopped:
                break
            if arm == "self_repair" and c:
                feedback = (arc_feedback(public_task, c.evaluation) if kind == "arc"
                            else bio_feedback(c.evaluation))
                messages += [{"role": "assistant", "content": c.code},
                             {"role": "user", "content": feedback}]

    elif arm == "orchestrator_worker":
        k0 = k or max(1, budget.calls // 2)
        plan_request = PROMPT_TEMPLATES["orchestrator_plan"].format(k=k0)
        planned = ledger.call("orchestrator_plan", prompt + [{"role": "user", "content": plan_request}], per_call)
        plans = _plans(planned[0].get("content") if planned else None, k0)
        if planned:
            rec, event = planned
            steps.append({**event, "code_source": None, "program_sha256": None,
                          "eval_id": None, "visible_status": "planning_only", "visible_score": None})
        for plan in plans[:min(k0, budget.calls - 1)]:
            invoke("worker", prompt + [{"role": "user", "content":
                   PROMPT_TEMPLATES["worker"].format(plan=plan)}])
            if stopped:
                break
        while not stopped and ledger.used_calls < budget.calls:
            remaining_calls = budget.calls - ledger.used_calls
            instruction = "Revise the best visible-check program using the visible results."
            if candidates:
                summaries = [_visible_summary(c) for c in candidates]
                if remaining_calls >= 2:
                    assignment = ledger.call("orchestrator_assign", prompt + [{"role": "user", "content":
                        PROMPT_TEMPLATES["orchestrator_assign"].format(
                            summaries=json.dumps(summaries, default=str))}], per_call)
                    if assignment:
                        rec, event = assignment
                        steps.append({**event, "code_source": None, "program_sha256": None,
                                      "eval_id": None, "visible_status": "assignment_only",
                                      "visible_score": None})
                        instruction = rec.get("content") or instruction
                best = max(candidates, key=lambda c: (c.score, -c.step))
                feedback = (arc_feedback(public_task, best.evaluation) if kind == "arc"
                            else bio_feedback(best.evaluation))
                message = PROMPT_TEMPLATES["worker_revision"].format(
                    instruction=instruction, program=best.code, feedback=feedback)
            else:
                message = "Try a new independent program."
            invoke("worker_revision", prompt + [{"role": "user", "content": message}])
            if stopped:
                break

    elif arm == "debate":
        agents = min(m, budget.calls)
        for index in range(agents):
            invoke(f"debater_{index}", prompt + [{"role": "user", "content":
                   PROMPT_TEMPLATES["debater_propose"].format(index=index + 1)}])
            if stopped:
                break
        turn = 0
        while not stopped and ledger.used_calls < budget.calls:
            shared = [_visible_summary(c) for c in candidates]
            invoke(f"debater_{turn % max(1, agents)}_revision", prompt + [{"role": "user", "content":
                   PROMPT_TEMPLATES["debater_revision"].format(
                       summaries=json.dumps(shared, default=str))}])
            turn += 1
            if stopped:
                break

    else:  # non-spatial evolutionary search; no cell types or developmental policy
        identity = ("def transform(grid):\n    return grid" if kind == "arc" else None)
        population: list[Candidate] = []
        if identity:
            ev = ev_client.run(kind, task_id, identity, val_seed=val_seed, **eval_options)
            score = _score(kind, ev)
            if score > float("-inf"):
                candidate = Candidate(identity, ev, score, -1)
                candidates.append(candidate)
                population.append(candidate)
                if _perfect(kind, ev):
                    stopped = "arc_train_perfect"
        seen = {sha256(c.code.encode()).hexdigest() for c in population}
        if not stopped and ledger.used_calls < budget.calls:
            planned = ledger.call("evolution_planner", prompt + [{"role": "user", "content":
                PROMPT_TEMPLATES["evolution_planner"]}], per_call)
            if planned:
                _, event = planned
                steps.append({**event, "code_source": None, "program_sha256": None,
                              "eval_id": None, "visible_status": "planning_only", "visible_score": None})
        generation = 0
        while not stopped and ledger.used_calls < budget.calls:
            generation += 1
            top = sorted(population, key=lambda c: (c.score, -len(c.code)), reverse=True)
            parent = rng.choice(top[:min(4, len(top))]) if top else None
            mate = rng.choice(top[:min(4, len(top))]) if len(top) > 1 and generation % 2 == 0 else None
            parents = [{"code": c.code, "visible_score": c.score}
                       for c in (parent, mate) if c is not None]
            mode = "crossover" if mate else "mutation"
            request = PROMPT_TEMPLATES["evolution_propose"].format(
                mode=mode, parents=json.dumps(parents))
            candidate = invoke(f"evolution_{mode}", prompt + [{"role": "user", "content": request}])
            if candidate and sha256(candidate.code.encode()).hexdigest() not in seen:
                seen.add(sha256(candidate.code.encode()).hexdigest())
                population.append(candidate)
                population = sorted(population, key=lambda c: (c.score, -len(c.code)), reverse=True)[:population_size]
            if stopped:
                break

    if candidates:
        best = max(candidates, key=lambda c: (c.score, c.step if arm == "self_repair" else -c.step))
    else:
        best = None
    final_id = best.evaluation.get("eval_id") if best else None
    final_score = best.score if best else None
    contributors = [final_id] if final_id else []
    if arm == "vote" and candidates:
        ids = [c.evaluation["eval_id"] for c in candidates if c.evaluation.get("eval_id")]
        if ids:
            aggregate = ev_client.aggregate(kind, task_id, ids, "vote" if kind == "arc" else "average")
            if aggregate.get("status") == "ok":
                final_id = aggregate["eval_id"]
                contributors = aggregate.get("contributor_eval_ids", ids)
                final_score = (aggregate.get("source_best_visible_score") if kind == "arc"
                               else aggregate.get("source_mean_visible_score"))
                steps.append({"role": "visible_aggregation", "eval_id": final_id,
                              "visible_status": "ok", "visible_score": final_score,
                              "contributor_eval_ids": contributors, "completion_reasoning_tokens": 0})

    usage = [e for e in ledger.events]
    return {"arm": arm, "kind": kind, "task_id": task_id, "condition": "single_model",
            "provider": provider, "model": model, "model_max_tokens": model_max_tokens,
            "budget": {"calls": budget.calls, "completion_reasoning_tokens": budget.tokens},
            "n_budget": budget.calls,
            "calls_used": ledger.used_calls, "completion_reasoning_tokens_used": ledger.used_tokens,
            "prompt_tokens_reported": sum((e.get("prompt_tokens") or 0) for e in usage),
            "final_eval_id": final_id, "final_round": best.step if best else -1,
            "final_visible_score": final_score, "contributor_eval_ids": contributors,
            "steps": steps, "stop_reason": stopped or "planned_calls_or_tokens_exhausted",
            "seed": seed, **(tag or {})}
