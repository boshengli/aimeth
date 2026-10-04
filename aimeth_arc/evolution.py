"""Non-spatial evolutionary program search with an LLM mutation operator."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import random
import time
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .calibration import Journal, PROVIDERS, utc_now, usage_estimate_cny
from .data import ArcTask
from .executor import run_program
from .grading import exact_match
from .scoring import extract_program


@dataclass(frozen=True)
class Candidate:
    code: str
    train_correct: int
    train_total: int
    execution_status: str
    generation: int

    @property
    def fitness(self) -> tuple[int, int]:
        return (self.train_correct, -len(self.code))


class MutationOperator(Protocol):
    def mutate(self, task: ArcTask, parent: Candidate, call_id: str) -> str | None: ...


class PublicLLMMutationOperator:
    """Paid adapter; all requests, responses, and uncertain outcomes are journaled."""

    def __init__(self, provider: str, private_root: Path, cap_cny: float = 300.0):
        if provider not in PROVIDERS:
            raise ValueError("unknown provider")
        self.provider = provider
        self.cfg = PROVIDERS[provider]
        self.key = os.environ.get(self.cfg["env"])
        if not self.key and provider == "zhipu":
            self.key = os.environ.get("ZAI_API_KEY")
        if not self.key:
            raise RuntimeError("API key environment variable unavailable")
        self.journal = Journal(private_root / f"{provider}-mutation-receipts.jsonl")
        self.cap_cny = min(cap_cny, self.cfg["cap_cny"])

    def mutate(self, task: ArcTask, parent: Candidate, call_id: str) -> str | None:
        if call_id in self.journal.started:
            raise ValueError("mutation call ID already dispatched; no duplicate request")
        body = {
            "model": self.cfg["model"], "max_tokens": 8192,
            "thinking": {"type": "enabled"}, "reasoning_effort": "low",
            "messages": [
                {"role": "system", "content": (
                    "Mutate one Python ARC grid transformation program. Return only a new "
                    "def transform(grid: list[list[int]]) -> list[list[int]] program. "
                    "Only numpy imports are allowed. No I/O or external state.")},
                {"role": "user", "content": json.dumps({
                    "training_pairs": task.public_view()["train"],
                    "parent_program": parent.code,
                    "parent_training_correct": parent.train_correct,
                    "parent_training_total": parent.train_total,
                }, separators=(",", ":"))},
            ],
        }
        data = json.dumps(body, separators=(",", ":")).encode()
        # Peak uncached price and 10 CNY/USD are budget envelopes, not bills.
        reserve_cny = ((len(data) * self.cfg["input_usd_per_m"]
                        + 8192 * self.cfg["output_usd_per_m"]) / 1_000_000 * 10)
        if self.journal.known_estimate_cny + self.journal.unknown_reserved_cny + reserve_cny > self.cap_cny:
            raise RuntimeError("mutation spend cap would be exceeded")
        self.journal.append({"event": "dispatch_started", "at": utc_now(),
                             "request_id": call_id, "provider": self.provider,
                             "request_sha256": sha256(data).hexdigest(),
                             "request_body": body, "reserve_cny": reserve_cny})
        req = Request(self.cfg["endpoint"], data, method="POST", headers={
            "Content-Type": "application/json", "Authorization": "Bearer " + self.key})
        t0 = time.monotonic()
        status = None
        response_body = None
        failure = None
        try:
            with urlopen(req, timeout=600) as response:
                status = response.status
                response_body = response.read(2_000_000).decode("utf-8", "replace")
        except HTTPError as exc:
            status = exc.code
            response_body = exc.read(2_000_000).decode("utf-8", "replace")
            failure = "http_error"
        except (URLError, OSError, TimeoutError) as exc:
            failure = type(exc).__name__
        if response_body and self.key in response_body:
            response_body = response_body.replace(self.key, "<REDACTED_SECRET>")
        try:
            parsed = json.loads(response_body) if response_body else None
        except json.JSONDecodeError:
            parsed = None
            failure = failure or "invalid_response_json"
        usage = parsed.get("usage") if isinstance(parsed, dict) else None
        estimate = usage_estimate_cny(usage, self.provider)
        self.journal.append({"event": "settled", "at": utc_now(),
                             "request_id": call_id, "provider": self.provider,
                             "http_status": status, "elapsed_s": round(time.monotonic()-t0, 3),
                             "response_body": response_body, "usage": usage,
                             "failure": failure, "reserve_cny": reserve_cny,
                             "estimated_cny": estimate})
        self.journal.started.add(call_id)
        self.journal.known_estimate_cny += reserve_cny if estimate is None else estimate
        if not isinstance(parsed, dict):
            return None
        message = (parsed.get("choices") or [{}])[0].get("message") or {}
        return extract_program(message.get("content"))


def evaluate_candidate(task: ArcTask, code: str, generation: int) -> Candidate:
    result = run_program(code, [pair["input"] for pair in task.train])
    correct = (sum(exact_match(output, pair["output"])
                   for output, pair in zip(result.outputs, task.train))
               if result.outputs is not None else 0)
    return Candidate(code, correct, len(task.train), result.status, generation)


def evolutionary_search(task: ArcTask, mutate: MutationOperator, call_budget: int,
                        seed: int = 0, population_size: int = 8,
                        observer: Callable[[dict], None] | None = None) -> dict:
    if call_budget < 0 or population_size < 1:
        raise ValueError("invalid search budget")
    rng = random.Random(seed)
    population = [evaluate_candidate(task, "def transform(grid):\n    return grid", 0)]
    seen = {sha256(population[0].code.encode()).hexdigest()}
    events = []
    for generation in range(1, call_budget + 1):
        top = sorted(population, key=lambda candidate: candidate.fitness, reverse=True)
        parent = rng.choice(top[:min(4, len(top))])
        call_id = f"evolution-{task.task_id}-{seed}-{generation}"
        code = mutate.mutate(task, parent, call_id)
        if code:
            digest = sha256(code.encode()).hexdigest()
            if digest not in seen:
                seen.add(digest)
                population.append(evaluate_candidate(task, code, generation))
                population = sorted(population, key=lambda x: x.fitness, reverse=True)[:population_size]
        event = {"generation": generation, "call_id": call_id,
                 "candidate_received": bool(code),
                 "best_training_correct": max(x.train_correct for x in population),
                 "training_total": len(task.train)}
        events.append(event)
        if observer:
            observer(event)
    best = max(population, key=lambda candidate: candidate.fitness)
    return {"task_id": task.task_id, "seed": seed, "call_budget": call_budget,
            "calls_attempted": len(events), "unique_candidates": len(seen),
            "best_training_correct": best.train_correct,
            "training_total": best.train_total, "best_code": best.code,
            "events": events}
