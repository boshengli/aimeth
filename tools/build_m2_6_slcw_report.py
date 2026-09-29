#!/usr/bin/env python3
"""Validate M2.6 offline report references and build deterministic hash manifest."""
from __future__ import annotations

import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "milestones/m2-6-slcw-realignment-v1.html"
SOURCES = ROOT / "milestones/m2-6-slcw-realignment-v1.sources.json"
EVIDENCE = ROOT / "milestones/m2-6-slcw-realignment-v1.evidence.json"
QA = ROOT / "milestones/m2-6-slcw-realignment-v1.browser-qa.json"
DESIGN = ROOT / "docs/slcw-source-realignment-v1.md"
OUTPUT = ROOT / "milestones/m2-6-slcw-realignment-v1.artifacts.json"


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        if attr.get("id"):
            self.ids.add(str(attr["id"]))
        if tag == "a" and attr.get("href"):
            self.hrefs.append(str(attr["href"]))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    html = REPORT.read_text(encoding="utf-8")
    parser = Links()
    parser.feed(html)
    assert '<html lang="zh-CN">' in html
    assert "M2.6" in html and "单 Agent 解题成功不是群体测试的入场门槛" in html
    for href in parser.hrefs:
        if href.startswith("#"):
            assert href[1:] in parser.ids, f"missing section target: {href}"
        elif not re.match(r"https?://", href):
            target = (REPORT.parent / href.split("#", 1)[0]).resolve()
            assert target.is_file(), f"missing offline resource: {href}"

    source_data = json.loads(SOURCES.read_text(encoding="utf-8"))
    for row in source_data["sources"]:
        assert re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
        assert row["bytes"] > 0 and row["inspected_lines"]
    record = {
        "schema_version": "1.0",
        "milestone": "M2.6",
        "baseline_commit": "8b56634efae095945cc6ae7deb2cd3f7d7854fe1",
        "builder": "tools/build_m2_6_slcw_report.py",
        "report": REPORT.relative_to(ROOT).as_posix(),
        "inputs": {
            p.relative_to(ROOT).as_posix(): sha(p)
            for p in (REPORT, DESIGN, SOURCES, EVIDENCE, QA, Path(__file__))
        },
        "local_reference_check": "PASS",
        "source_entries": len(source_data["sources"]),
    }
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"PASS: report links, 5 local inputs hashed, {len(source_data['sources'])} original sources recorded")


if __name__ == "__main__":
    main()
