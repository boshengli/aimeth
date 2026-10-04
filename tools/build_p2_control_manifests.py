"""Freeze outcome-blind P2 task IDs and prompt-template hashes before Phase B."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_rt.arc_data import load_arc2_evaluation, select_arc2_pilot, PILOT_40_SALT
from aimeth_rt.control_arms import PROMPT_TEMPLATES
from aimeth_rt.workflows import ARC_SYSTEM


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def build(archive: Path, output: Path):
    views = load_arc2_evaluation(archive)
    archive_sha = sha(archive.read_bytes())
    ids = sorted(views)
    selection = select_arc2_pilot(ids)
    rows_120 = [{"task_id": tid,
                 "public_view_sha256": sha(json.dumps(views[tid], sort_keys=True,
                                                        separators=(",", ":")).encode())}
                for tid in ids]
    common = {"source_archive_sha256": archive_sha,
              "task_id_source": "arc2/data/evaluation/*.json",
              "answer_outputs_excluded_from_public_view": True}
    write_json(output / "arc2-eval120-v1.json", {
        "version": "p2-arc2-eval120-v1", **common, "tasks": rows_120})
    write_json(output / "arc2-pilot40-v1.json", {
        "version": "p2-arc2-hash-pilot40-v1", **common,
        "selection": {"method": "sort ascending by SHA256(salt + ':' + task_id), take first 40",
                      "salt": PILOT_40_SALT,
                      "outcome_blind": True,
                      "stratification": "none"},
        "tasks": selection})
    write_json(output / "p2-control-prompt-hashes-v1.json", {
        "version": "p2-control-prompts-v1",
        "arc_system_sha256": sha(ARC_SYSTEM.encode()),
        "role_templates": {name: {"text": text, "sha256": sha(text.encode())}
                           for name, text in sorted(PROMPT_TEMPLATES.items())},
        "realized_prompt_policy": "Every model-call record stores SHA-256 of canonical JSON messages; response text is not part of public milestone artifacts."})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arc-archive", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("plans"))
    args = parser.parse_args()
    build(args.arc_archive, args.output_dir)


if __name__ == "__main__":
    main()
