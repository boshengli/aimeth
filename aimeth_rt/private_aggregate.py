"""Private answer-key-side aggregation for agent-generated predictions."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def handle_aggregate(job: dict, cfg: dict) -> tuple[dict, dict]:
    """Combine private predictions and return a public-safe summary plus private answer.

    ARC test grids and callus prediction arrays are returned only in the second,
    daemon-private value. The public summary contains source IDs and visible
    scores/agreement counts only.
    """
    root = Path(cfg["root"])
    source_kind, mode = job["source_kind"], job["mode"]
    if (source_kind, mode) not in (("arc", "vote"), ("bio", "average")):
        raise ValueError("unsupported private aggregation")
    ids = job.get("eval_ids") or []
    if not isinstance(ids, list) or not 1 <= len(ids) <= 128 or len(ids) != len(set(ids)):
        raise ValueError("invalid aggregate source list")
    sources = []
    for eid in ids:
        if not isinstance(eid, str) or not eid or Path(eid).name != eid or "/" in eid or ".." in eid:
            raise ValueError("invalid evaluation identifier")
        private = json.loads((root / "private" / (eid + ".json")).read_text())
        metadata = private["job"]
        if metadata["kind"] != source_kind or metadata["task_id"] != job["task_id"]:
            raise ValueError("aggregate source belongs to another task")
        visible = json.loads((root / "done" / (eid + ".json")).read_text())
        if visible.get("status") != "ok":
            raise ValueError("aggregate source was not successfully evaluated")
        sources.append((eid, private, visible))

    if mode == "vote":
        counts = {len(private["test_preds"]) for _, private, _ in sources}
        if len(counts) != 1:
            raise ValueError("inconsistent ARC test input count")
        winners, support, contributors = [], [], []
        for index in range(counts.pop()):
            ballots: dict[str, list[tuple[int, str, list, float]]] = {}
            for order, (eid, private, visible) in enumerate(sources):
                grid = private["test_preds"][index]
                if grid is None:
                    continue
                key = json.dumps(grid, separators=(",", ":"))
                ballots.setdefault(key, []).append((order, eid, grid, float(visible["train_frac"])))
            if not ballots:
                winners.append(None)
                support.append(0)
                continue
            group = min(ballots.values(), key=lambda b: (-len(b), -max(v[3] for v in b), min(v[0] for v in b)))
            representative = min(group, key=lambda v: (-v[3], v[0]))
            winners.append(representative[2])
            support.append(len(group))
            contributors.extend(v[1] for v in group)
        used = [eid for eid in ids if eid in set(contributors)]
        return ({"status": "ok", "mode": mode, "contributor_eval_ids": used,
                 "agreement_by_test": support,
                 "source_best_visible_score": max(float(v["train_frac"]) for _, _, v in sources)},
                {"test_preds": winners})

    arrays = []
    for _, private, _ in sources:
        pred_file = private.get("pred_file")
        if not isinstance(pred_file, str) or Path(pred_file).name != pred_file or ".." in pred_file:
            raise ValueError("invalid private prediction filename")
        array = np.load(root / "private" / pred_file, allow_pickle=False)
        if arrays and array.shape != arrays[0].shape:
            raise ValueError("inconsistent callus prediction shapes")
        if not np.isfinite(array).all():
            raise ValueError("nonfinite callus prediction")
        arrays.append(array)
    mean = np.mean(np.stack(arrays).astype(np.float64), axis=0).astype(np.float32)
    return ({"status": "ok", "mode": mode, "contributor_eval_ids": ids,
             "source_mean_visible_score": sum(float(v["val_pattern_r"]) for _, _, v in sources) / len(sources)},
            {"pred_array": mean})
