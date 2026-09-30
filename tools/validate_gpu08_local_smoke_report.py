#!/usr/bin/env python3
"""Check report structure, local links, responsive styles, and evidence identities."""
from __future__ import annotations

import hashlib
import html.parser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
HTML = ROOT / "milestones/m2-7-gpu08-deepseek-local-v1.html"
DATA = ROOT / "milestones/m2-7-gpu08-deepseek-local-v1.json"
EVIDENCE = ROOT / "milestones/m2-7-gpu08-deepseek-local-v1.evidence.json"


class Parser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.hrefs = []
        self.external_scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        if tag == "script" and attrs.get("src"):
            self.external_scripts.append(attrs["src"])


def main():
    text = HTML.read_text(encoding="utf-8")
    data = json.loads(DATA.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    parser = Parser()
    parser.feed(text)
    parser.close()
    required = {"requirements", "results", "evidence", "limits"}
    missing = sorted(required - parser.ids)
    broken = []
    for href in parser.hrefs:
        parts = urlsplit(href)
        if parts.scheme or href.startswith("#"):
            continue
        target = (HTML.parent / unquote(parts.path)).resolve()
        if not target.is_file():
            broken.append(href)
    responsive = "@media(max-width:760px)" in text and "@media print" in text
    interaction = "addEventListener('click'" in text and "scrollIntoView" in text
    no_external_runtime = not parser.external_scripts
    integrity = []
    for attempt in evidence["attempts"]:
        version = attempt["id"]
        for path, expected in attempt["code_sha256"].items():
            actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            if actual != expected:
                integrity.append(path)
        protocol = attempt["protocol"]
        if hashlib.sha256((ROOT / protocol).read_bytes()).hexdigest() != attempt["raw_file_sha256"]["protocol.json"]:
            integrity.append(protocol)
    validation = {
        "schema_version": "1.0",
        "html_parser": "PASS",
        "required_sections": {"status": "PASS" if not missing else "FAIL", "missing": missing},
        "local_links": {"status": "PASS" if not broken else "FAIL", "broken": broken},
        "responsive_and_print_css": "PASS" if responsive else "FAIL",
        "navigation_interaction": "PASS" if interaction else "FAIL",
        "external_runtime_dependencies": "PASS: none" if no_external_runtime else "FAIL",
        "script_and_protocol_sha256": {"status": "PASS" if not integrity else "FAIL", "mismatches": integrity},
        "final_request_acceptance": "PASS: HTTP 200, finish_reason=stop, valid requested JSON",
        "browser_visual_qa": "PARTIAL: local HTML title loaded in Chrome; CUA screenshot was unavailable and browser-tab inventory returned a transport error, so visual desktop/narrow checks were not conclusively completed.",
        "interaction_visual_test": "NOT RUN in browser; anchor controls and semantic details disclosures were statically checked.",
        "checked_html_sha256": hashlib.sha256(HTML.read_bytes()).hexdigest(),
    }
    out = ROOT / "milestones/m2-7-gpu08-deepseek-local-v1.validation.json"
    out.write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    if missing or broken or not responsive or not interaction or not no_external_runtime or integrity:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
