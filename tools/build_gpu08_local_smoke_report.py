#!/usr/bin/env python3
"""Build the self-contained M2.7 GPU08 local DeepSeek smoke report."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "milestones/m2-7-gpu08-deepseek-local-v1.json"
TEMPLATE = ROOT / "milestones/m2-7-gpu08-deepseek-local-v1.template.html"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def build(output: Path, allow_pending: bool = False) -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    template = TEMPLATE.read_text(encoding="utf-8")
    delivery = data.get("report_delivery_commit", "pending")
    if delivery == "pending" and not allow_pending:
        raise SystemExit("report_delivery_commit is pending; pass --allow-pending before the delivery commit")

    row_parts = []
    for item in data["attempts"]:
        passed = item["version"] == "v3"
        badge = '<span class="badge pass">PASS</span>' if passed else '<span class="badge fail">FAILED / STOPPED</span>'
        protocol = f"../examples/gpu08-local-model-smoke-{item['version']}.json"
        links = [f'<a href="m2-7-gpu08-deepseek-local-v1.evidence.json">public evidence receipt</a>', f'<a href="{protocol}">frozen protocol</a>']
        if item["version"] == "v3":
            links.append('<a href="m2-7-gpu08-deepseek-local-v1.evidence.json">accepted response</a>')
        notes = esc(item["outcome"])
        row_parts.append(
            "<tr>"
            f"<td><strong>{esc(item['version'])}</strong><br>Slurm {esc(item['job'])}<br>{badge}</td>"
            f"<td>{notes}</td>"
            f"<td>{esc(item['state'])}</td>"
            f"<td>{' · '.join(links)}</td>"
            "</tr>"
        )

    evidence_items = []
    for version in ("v1", "v2", "v3"):
        evidence_items.append(
            f'<li><strong>{version}</strong>：'
            f'<a href="m2-7-gpu08-deepseek-local-v1.evidence.json">公开运行收据与原始记录 SHA-256</a>'
            f' · <a href="../examples/gpu08-local-model-smoke-{version}.json">冻结协议</a></li>'
        )

    response = data["request_result"]["content"]
    replacements = {
        "__TITLE__": esc(data["milestone"]),
        "__MILESTONE__": esc(data["milestone"]),
        "__VERSION__": esc(data["version"]),
        "__DATE__": esc(data["date"]),
        "__SUMMARY__": esc(data["outcome"] + ". 本地模型权重与服务镜像均在 GPU08；调用只经 loopback。"),
        "__JOB__": esc(data["runtime"]["slurm_job"]),
        "__SOURCE_BASELINE__": esc(data["source_baseline_commit"]),
        "__MODEL_REVISION__": esc(data["model"]["revision"]),
        "__CONTAINER_SHA__": esc(data["runtime"]["container_sha256"]),
        "__PRIVATE_ROOT__": esc(data["private_cluster_run_root"]),
        "__DELIVERY_COMMIT__": esc(delivery),
        "__ATTEMPT_ROWS__": "\n".join(row_parts),
        "__FINAL_RESPONSE__": esc(response),
        "__EVIDENCE_LINKS__": "\n".join(evidence_items),
    }
    result = template
    for marker, replacement in replacements.items():
        result = result.replace(marker, replacement)
    unresolved = [marker for marker in replacements if marker in result]
    if unresolved:
        raise SystemExit(f"unresolved report template markers: {unresolved}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(result, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "milestones/m2-7-gpu08-deepseek-local-v1.html")
    parser.add_argument("--allow-pending", action="store_true")
    args = parser.parse_args()
    build(args.output, allow_pending=args.allow_pending)


if __name__ == "__main__":
    main()
