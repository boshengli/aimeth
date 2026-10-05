"""Build an ARC-AGI-2 evaluation archive with test inputs but no test outputs.

The archive is an answer-free prompt source for generation controllers. Hidden
test predictions are still produced and graded only by the separate evaluator.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile


PREFIX = "arc2/data/evaluation/"


def _task_ids(path: Path) -> list[str]:
    raw = json.loads(path.read_text())
    if isinstance(raw, dict):
        raw = next(raw[k] for k in ("task_ids", "pilot", "tasks") if k in raw)
    if not isinstance(raw, list):
        raise ValueError("task manifest must be a JSON list")
    ids = [item["task_id"] if isinstance(item, dict) else item for item in raw]
    if len(ids) != 40 or len(set(ids)) != 40:
        raise ValueError("L1 task manifest must contain exactly 40 unique task IDs")
    if any(not isinstance(tid, str) or len(tid) != 8 or
           any(c not in "0123456789abcdef" for c in tid) for tid in ids):
        raise ValueError("invalid ARC-AGI-2 task ID")
    return ids


def _public_view(path: Path) -> tuple[str, bytes]:
    task_id = path.stem
    if len(task_id) != 8 or any(c not in "0123456789abcdef" for c in task_id):
        raise ValueError(f"invalid task filename: {path.name}")
    raw = json.loads(path.read_text())
    if not raw.get("train") or not raw.get("test"):
        raise ValueError(f"{path.name}: empty train/test split")
    # Construct a fresh object. In particular, test-pair outputs are never
    # copied into the archive supplied to the generation controller.
    public = {
        "train": [{"input": pair["input"], "output": pair["output"]}
                  for pair in raw["train"]],
        "test": [{"input": pair["input"]} for pair in raw["test"]],
    }
    return task_id, json.dumps(public, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":")).encode("utf-8")


def build(source: Path, task_manifest: Path, output: Path) -> str:
    ids = _task_ids(task_manifest)
    files = sorted(source.glob("*.json"))
    if len(files) != 120 or len({p.stem for p in files}) != 120:
        raise ValueError(f"expected 120 ARC-AGI-2 evaluation JSON files; found {len(files)}")
    by_id = {p.stem: p for p in files}
    if not set(ids).issubset(by_id):
        raise ValueError("task manifest contains IDs absent from the evaluation directory")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"refusing to reuse stale temporary archive: {temporary}")
    with temporary.open("xb") as raw_file:
        with gzip.GzipFile(fileobj=raw_file, mode="wb", mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w") as tar:
                for path in files:
                    task_id, payload = _public_view(path)
                    info = tarfile.TarInfo(PREFIX + task_id + ".json")
                    info.size = len(payload)
                    info.mode = 0o644
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mtime = 0
                    tar.addfile(info, io.BytesIO(payload))
        raw_file.flush()
        os.fsync(raw_file.fileno())
    digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
    if output.exists():
        existing_digest = hashlib.sha256(output.read_bytes()).hexdigest()
        temporary.unlink()
        if existing_digest != digest:
            raise FileExistsError("public ARC archive exists with a different hash; refusing to overwrite")
        return digest
    os.replace(temporary, output)
    return digest


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, type=Path,
                    help="ARC-AGI-2 evaluation directory used only by this sanitizing exporter")
    ap.add_argument("--tasks", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    print(build(args.source, args.tasks, args.out))


if __name__ == "__main__":
    main()
