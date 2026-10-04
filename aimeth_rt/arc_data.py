"""ARC-AGI-2 evaluation loading and private two-attempt grading.

The task loader returns only training pairs and test inputs. The answer-bearing
archive is read again only by the private grading path.
"""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
import tarfile


PREFIX = "arc2/data/evaluation/"
PILOT_40_SALT = "T-20261004-002:ARC2-eval-pilot-v1"


def _task_members(bundle: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = [m for m in bundle if m.isfile() and m.name.startswith(PREFIX)
               and m.name.endswith(".json")]
    if len(members) != 120 or len({Path(m.name).stem for m in members}) != 120:
        raise ValueError(f"expected 120 distinct ARC-AGI-2 evaluation tasks, found {len(members)}")
    for member in members:
        tid = Path(member.name).stem
        if (member.name != PREFIX + tid + ".json" or len(tid) != 8
                or any(c not in "0123456789abcdef" for c in tid)
                or member.size > 2_000_000):
            raise ValueError("invalid ARC-AGI-2 archive member")
    return sorted(members, key=lambda m: m.name)


def load_arc2_evaluation(archive: str | Path) -> dict[str, dict]:
    """Return 120 public views; no test output is returned or retained."""
    views = {}
    with tarfile.open(archive, "r:gz") as bundle:
        for member in _task_members(bundle):
            with bundle.extractfile(member) as stream:
                raw = json.load(stream)
            if not raw.get("train") or not raw.get("test"):
                raise ValueError(f"{member.name}: empty train/test split")
            views[Path(member.name).stem] = {
                "train": [{"input": p["input"], "output": p["output"]} for p in raw["train"]],
                "test": [{"input": p["input"]} for p in raw["test"]],
            }
    return views


def grade_arc_attempts(attempts: list[list], truth: list) -> bool:
    """A task passes when every test output matches one of at most two attempts."""
    if len(attempts) != len(truth):
        return False
    return all(1 <= len(options) <= 2 and any(option == answer for option in options)
               for options, answer in zip(attempts, truth))


def select_arc2_pilot(task_ids: list[str], n: int = 40,
                      salt: str = PILOT_40_SALT) -> list[dict[str, str]]:
    """Outcome-blind deterministic sample, ranked only by salted task-ID hash."""
    if type(n) is not int or n < 1 or n > len(task_ids) or len(set(task_ids)) != len(task_ids):
        raise ValueError("n must be within a unique task-ID list")
    ranked = sorted((sha256(f"{salt}:{tid}".encode()).hexdigest(), tid) for tid in task_ids)
    return [{"task_id": tid, "selection_sha256": digest} for digest, tid in ranked[:n]]
