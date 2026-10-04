"""Freeze a deterministic, grid-size-stratified ARC pilot selection."""

import csv
from hashlib import sha256
import json
from pathlib import Path


def freeze_pilot(csv_path: Path, archive: Path, output_path: Path) -> dict:
    with csv_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 400:
        raise ValueError("calibration table must contain all 400 tasks")
    if any(row["deepseek_samples"] != "4" or row["zhipu_samples"] != "4" for row in rows):
        raise ValueError("both models require four settled samples per task")
    areas = sorted(int(row["max_input_area"]) for row in rows)
    q1, q2 = areas[133], areas[266]
    strata = {"small": [], "medium": [], "large": []}
    for row in rows:
        score = float(row["pooled_pass_at_1"])
        if not 0.20 <= score <= 0.60:
            continue
        area = int(row["max_input_area"])
        stratum = "small" if area <= q1 else "medium" if area <= q2 else "large"
        strata[stratum].append(row["task_id"])
    eligible = sum(map(len, strata.values()))
    if eligible < 40:
        raise ValueError(f"only {eligible} tasks satisfy the frozen 20%-60% criterion; cannot select 40")
    for group in strata.values():
        group.sort(key=lambda task_id: sha256(("p2-arc-v1:" + task_id).encode()).hexdigest())
    quotas = {"small": 14, "medium": 13, "large": 13}
    selected = []
    for name in ("small", "medium", "large"):
        take = min(quotas[name], len(strata[name]))
        selected.extend({"task_id": tid, "stratum": name} for tid in strata[name][:take])
        strata[name] = strata[name][take:]
    while len(selected) < 40:
        available = [(name, group[0]) for name, group in strata.items() if group]
        if not available:
            raise AssertionError("eligible pool unexpectedly exhausted")
        name, tid = min(available, key=lambda pair: sha256(("p2-arc-v1:" + pair[1]).encode()).hexdigest())
        selected.append({"task_id": tid, "stratum": name})
        strata[name].remove(tid)
    selected_ids = {x["task_id"] for x in selected}
    digest = sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    manifest = {"schema_version": 1, "selection": "40 eligible tasks, stratified by max input grid area",
                "criterion": "0.20 <= pooled sample success/8 <= 0.60",
                "area_tercile_cutoffs": [q1, q2], "tie_break": "SHA-256('p2-arc-v1:' + task_id)",
                "eligible_count": eligible, "pilot": selected,
                "remaining_task_ids": sorted(row["task_id"] for row in rows if row["task_id"] not in selected_ids),
                "archive_sha256": digest.hexdigest(),
                "calibration_csv_sha256": sha256(csv_path.read_bytes()).hexdigest(),
                "heldout_note": "Remaining tasks were probed during calibration; they are held out only from subsequent organization development, not untouched by this study."}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n"
    if output_path.exists():
        raise FileExistsError("pilot manifest is frozen and cannot be overwritten")
    output_path.write_bytes(content)
    output_path.with_suffix(output_path.suffix + ".sha256").write_text(sha256(content).hexdigest() + "\n")
    return {"pilot_count": len(selected), "eligible_count": eligible,
            "manifest_sha256": sha256(content).hexdigest(), "path": str(output_path)}
