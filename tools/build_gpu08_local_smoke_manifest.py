#!/usr/bin/env python3
"""Create the immutable file/hash list for the GPU08 smoke report bundle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "README.md",
    "tasks/T-20260930-002.md",
    "examples/gpu08-local-model-smoke-v1.json",
    "examples/gpu08-local-model-smoke-v2.json",
    "examples/gpu08-local-model-smoke-v3.json",
    "milestones/m2-7-gpu08-deepseek-local-v1.html",
    "milestones/m2-7-gpu08-deepseek-local-v1.json",
    "milestones/m2-7-gpu08-deepseek-local-v1.template.html",
    "milestones/m2-7-gpu08-deepseek-local-v1.evidence.json",
    "milestones/m2-7-gpu08-deepseek-local-v1.validation.json",
    "tools/build_gpu08_local_smoke_report.py",
    "tools/validate_gpu08_local_smoke_report.py",
    "tools/build_gpu08_local_smoke_manifest.py",
    "tools/gpu08_model_smoke.sbatch",
    "tools/gpu08_model_smoke_probe.py",
    "tools/gpu08_model_smoke_v2.sbatch",
    "tools/gpu08_model_smoke_probe_v2.py",
    "tools/gpu08_model_smoke_v3.sbatch",
    "tools/gpu08_model_smoke_probe_v3.py",
]


def main() -> None:
    records = []
    for rel in FILES:
        path = ROOT / rel
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        records.append({"id": rel.replace("/", ":"), "path": rel, "bytes": path.stat().st_size, "sha256": digest})
    manifest = {
        "schema_version": "1.0",
        "scope": "M2.7 GPU08 local DeepSeek serving smoke report bundle; integrity only, no scientific validity claim",
        "source_baseline_commit": "35bce3ea7daef0af7b137c5cdea3ea45fd63b17c",
        "report_delivery_commit": "pending",
        "artifacts": records,
    }
    (ROOT / "gpu08-local-smoke-report-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
