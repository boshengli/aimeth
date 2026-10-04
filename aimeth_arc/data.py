"""Read ARC-AGI-1 evaluation tasks without copying answers into prompts."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tarfile
from typing import Any


Grid = list[list[int]]


@dataclass(frozen=True)
class ArcTask:
    task_id: str
    train: tuple[dict[str, Grid], ...]
    test: tuple[dict[str, Grid], ...]

    def public_view(self) -> dict[str, Any]:
        """Training examples and test inputs only; never expose test outputs."""
        return {
            "train": [{"input": p["input"], "output": p["output"]} for p in self.train],
            "test": [{"input": p["input"]} for p in self.test],
        }

    def test_outputs(self) -> tuple[Grid, ...]:
        return tuple(p["output"] for p in self.test)

    def max_input_area(self) -> int:
        return max(len(p["input"]) * len(p["input"][0]) for p in (*self.train, *self.test))


def _grid(value: Any) -> Grid:
    if not isinstance(value, list) or not 1 <= len(value) <= 30:
        raise ValueError("grid rows must be 1..30")
    width = len(value[0]) if isinstance(value[0], list) else 0
    if not 1 <= width <= 30:
        raise ValueError("grid columns must be 1..30")
    for row in value:
        if not isinstance(row, list) or len(row) != width:
            raise ValueError("grid is not rectangular")
        if any(type(cell) is not int or not 0 <= cell <= 9 for cell in row):
            raise ValueError("grid colors must be integers 0..9")
    return value


def _parse_task(task_id: str, raw: dict[str, Any]) -> ArcTask:
    pairs: dict[str, tuple[dict[str, Grid], ...]] = {}
    for split in ("train", "test"):
        records = raw.get(split)
        if not isinstance(records, list) or not records:
            raise ValueError(f"{task_id}: missing {split} pairs")
        pairs[split] = tuple(
            {"input": _grid(p["input"]), "output": _grid(p["output"])}
            for p in records
        )
    return ArcTask(task_id, pairs["train"], pairs["test"])


def load_arc1_evaluation(archive: str | Path) -> dict[str, ArcTask]:
    tasks: dict[str, ArcTask] = {}
    with tarfile.open(archive, "r:gz") as bundle:
        for member in bundle:
            if (not member.isfile() or not member.name.startswith("arc1/data/evaluation/")
                    or not member.name.endswith(".json")):
                continue
            task_id = Path(member.name).stem
            if len(task_id) != 8 or not all(c in "0123456789abcdef" for c in task_id):
                raise ValueError("invalid ARC task identifier")
            if member.size > 2_000_000:
                raise ValueError("oversized ARC task")
            stream = bundle.extractfile(member)
            if stream is None:
                raise ValueError("missing ARC member")
            tasks[task_id] = _parse_task(task_id, json.load(stream))
    if len(tasks) != 400:
        raise ValueError(f"expected 400 ARC-AGI-1 evaluation tasks, found {len(tasks)}")
    return dict(sorted(tasks.items()))
