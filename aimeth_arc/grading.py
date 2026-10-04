"""ARC exact-match rules. The generator never receives this module's test keys."""

from collections.abc import Callable, Sequence
from typing import Any

from .data import ArcTask, Grid, _grid


def exact_match(candidate: Any, target: Grid) -> bool:
    try:
        return _grid(candidate) == target
    except (TypeError, ValueError):
        return False


def grade_attempts(attempts: Sequence[Any], target: Grid) -> bool:
    """A test output succeeds if either of its first two attempts matches exactly."""
    if len(attempts) > 2:
        raise ValueError("ARC permits at most two attempts per test output")
    return any(exact_match(attempt, target) for attempt in attempts)


def score_training(task: ArcTask, transform: Callable[[Grid], Any]) -> tuple[int, int]:
    correct = 0
    for pair in task.train:
        try:
            candidate = transform([row[:] for row in pair["input"]])
            correct += int(exact_match(candidate, pair["output"]))
        except Exception:
            pass
    return correct, len(task.train)


def grade_test_outputs(task: ArcTask, per_test_attempts: Sequence[Sequence[Any]]) -> bool:
    if len(per_test_attempts) != len(task.test):
        raise ValueError("one attempt list is required per test input")
    return all(grade_attempts(attempts, target)
               for attempts, target in zip(per_test_attempts, task.test_outputs()))
