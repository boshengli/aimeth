"""Export only answer-free callus prompts for a local, API-backed controller."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_bio.bench import gene_annotation  # noqa: E402
from tools.bio_generate import SYSTEM, build_prompt  # noqa: E402


def export_public_prompts(bench: Path, annotation: Path, expected_count: int = 36) -> list[dict]:
    ann = gene_annotation(annotation)
    masks = {k: [d["id"] for d in v] for k, v in
             json.loads((bench / "mask_sets.json").read_text()).items()}
    rows = []
    for path in sorted((bench / "tasks").glob("*.json")):
        info = json.loads(path.read_text())
        prompt = build_prompt(info, ann, masks[info["mask_set"]])
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]
        digest = hashlib.sha256(json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        rows.append({"task_id": info["task_id"], "messages": messages, "prompt_sha256": digest})
    if len(rows) != expected_count or len({row["task_id"] for row in rows}) != expected_count:
        raise ValueError(f"expected {expected_count} unique callus tasks, found {len(rows)}")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bench", required=True, type=Path)
    parser.add_argument("--annot", required=True, type=Path)
    parser.add_argument("--out", default="-", help="JSON output file; '-' writes to stdout")
    args = parser.parse_args()
    rows = export_public_prompts(args.bench, args.annot)
    encoded = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.out == "-":
        sys.stdout.write(encoded)
    else:
        Path(args.out).write_text(encoded, encoding="utf-8")


if __name__ == "__main__":
    main()
