#!/usr/bin/env python3
"""Build the M1 human-readable report from frozen evidence and curated content."""
import argparse
import hashlib
from html import escape
import json
import math
from pathlib import Path
import re
import sys


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--content", type=Path)
    parser.add_argument("--template", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    content_path = args.content or repo / "milestones/m1-foundation-v1.json"
    template_path = args.template or repo / "templates/milestone-foundation.html"
    output = args.output or repo / "milestones/m1-foundation-v1.html"
    content = load(content_path)
    sys.path.insert(0, str(repo / "tools"))
    from verify_artifacts import verify
    # M1 keeps its original scientific/code baseline intact; adding a report is a separate release.
    baseline = repo / "archives/foundation-v1/foundation-manifest.json"
    verified = verify(baseline if baseline.exists() else repo / "foundation-manifest.json")
    audit = load(repo / "reports/handoff-audit.json")
    validation = load(repo / "reports/validation.json")
    sources = load(repo / "references/sources.json")["sources"]
    clone_path = content_path.with_name(content_path.stem + ".clean-checkout.json")
    clone = load(clone_path)
    if clone["commit"] != content["baseline_commit"] or clone["unit_tests"]["exit_code"] != 0:
        raise ValueError("Clean-checkout evidence does not match the claimed baseline")
    test_match = re.search(r"Ran (\d+) tests", validation["unit_tests"]["output"])
    if validation["unit_tests"]["exit_code"] or not test_match:
        raise ValueError("Cannot report passing tests from the supplied validation record")
    summary = {
        "baseline_commit": content["baseline_commit"],
        "source_hashes_matched": sum(item["match"] for item in audit["checksum_checks"]),
        "source_hashes_total": len(audit["checksum_checks"]),
        "syntax_checks_passed": sum(item["passed"] for item in audit["syntax_checks"]),
        "integrity_tests_passed": int(test_match.group(1)),
        "baseline_artifacts_checked": verified["artifacts_checked"],
        "prototype_findings": len(audit["finding_locations"]),
        "model_calls": validation["model_calls"],
        "cluster_jobs": validation["cluster_jobs"],
        "proof_verified": validation["mathematical_proof_verified"],
        "hosted_ci_executed": validation["hosted_ci_executed"],
    }
    if summary["model_calls"] != 0 or summary["cluster_jobs"] != 0 or summary["proof_verified"]:
        raise ValueError("The M1 narrative is scoped to zero live runs and no proof verification")
    labels = {"specified":"规范已建立", "mixed":"部分已实现", "local":"本地已验证", "implemented":"已实现", "design":"设计已准备", "ready":"可开始", "pending":"待完成"}
    rows = []
    for r in content["requirements"]:
        rows.append(f'<tr><td data-label="你的要求"><strong>{escape(r["need"])}</strong></td><td data-label="第一步的设定">{escape(r["set"])}<span class="source-tag">证据：{escape(r["evidence"])}</span></td><td data-label="状态与边界"><span class="badge {r["state"]}">{labels[r["state"]]}</span><p>{escape(r["gap"])}</p></td></tr>')
    findings = ''.join(f'<article class="finding"><div class="finding-id"><b>{escape(r["id"])}</b><span>{escape(r["type"])}</span></div><h3>{escape(r["title"])}</h3><p>{escape(r["body"])}</p></article>' for r in content["findings"])
    readiness = ''.join(f'<article class="card"><span class="badge {r["state"]}">{labels[r["state"]]}</span><h3>{escape(r["title"])}</h3><p>{escape(r["body"])}</p></article>' for r in content["readiness"])
    outputs = ''.join(f'<article><span class="step">0{i}</span><div><h4>{escape(r["title"])}</h4><p>{escape(r["body"])}</p></div></article>' for i,r in enumerate(content["next_outputs"],1))
    scope_zh = {"S01":"作者公告：读取组织与规模描述；不能据此认定因果或必要性。", "S02":"机构公告：读取全文；未据此推断奖项已完成裁决。", "S03":"官方问题陈述：核对目标与条件；用于区分问题变体。", "S04":"形式化仓库：本次读取 README，未重建证明或核查全部依赖。", "S05":"预印本 v3：读取摘要和相关方法部分，未复算其结果。", "S06":"官方复现文档：部署版本尚待核实。", "S07":"本次两次读取失败；没有据此声明 Science 最新政策合规。"}
    selected = [s for s in sources if s["id"] in content["source_ids"]]
    source_html = ''.join(f'<div class="source"><a href="{escape(s["url"],quote=True)}" target="_blank" rel="noopener noreferrer">{escape(s["author_or_owner"])} · {escape(s["title"])}</a><small>{escape(scope_zh[s["id"]])}</small></div>' for s in selected)
    centers = [(115,89),(325,89),(115,249),(325,249)]
    nodes = [(centers[i//8][0]+56*math.cos((i%8)*math.pi/4-math.pi/2),centers[i//8][1]+56*math.sin((i%8)*math.pi/4-math.pi/2)) for i in range(32)]
    graph = []
    for i,(x,y) in enumerate(centers):
        graph.append(f'<rect x="{x-81}" y="{y-73}" width="162" height="146" rx="13" fill="#f3f5ee" stroke="#dce3db"/><text x="{x-68}" y="{y-57}" text-anchor="start" fill="#72857e" font-size="12">组 {chr(65+i)}</text>')
    for i,(x,y) in enumerate(nodes):
        x2,y2=nodes[(i//8)*8+(i+1)%8]
        graph.append(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#659589" stroke-width="1.5"/>')
    graph.extend(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7.5" fill="#27715e" stroke="#fffefa" stroke-width="2"/>' for x,y in nodes)
    replacements = {
        'TITLE':escape(content['title']), 'DATE':escape(content['date']), 'VERSION':escape(content['version']),
        'CONCLUSION':escape(content['conclusion']), 'SCOPE':escape(content['scope']), 'BASELINE':content['baseline_commit'],
        'HASH_MATCHES':str(summary['source_hashes_matched']), 'HASH_TOTAL':str(summary['source_hashes_total']),
        'TESTS':str(summary['integrity_tests_passed']), 'FOUNDATION_COUNT':str(summary['baseline_artifacts_checked']),
        'FINDING_COUNT':str(summary['prototype_findings']), 'REQUIREMENTS':''.join(rows), 'FINDINGS':findings,
        'READINESS':readiness, 'NEXT_OUTPUTS':outputs, 'SOURCES':source_html, 'DEFAULT_GRAPH':''.join(graph),
        'EVIDENCE_SUMMARY':escape(json.dumps(summary,ensure_ascii=False,indent=2)),
    }
    text = template_path.read_text(encoding="utf-8")
    for name,value in replacements.items():
        text = text.replace('@@'+name+'@@',value)
    if re.search(r'@@[A-Z_]+@@',text):
        raise ValueError("Unexpanded report placeholder")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(text,encoding="utf-8")
    evidence = {"schema_version":"1.0", "milestone":content['id'], "report_version":content['version'], "summary":summary,
                "clean_checkout_scope":clone['independence_scope'], "inputs":[]}
    for p in [content_path,template_path,clone_path,repo/'reports/handoff-audit.json',repo/'reports/validation.json',repo/'foundation-manifest.json',repo/'references/sources.json']:
        # Logical names remain portable when the builder is run from another checkout.
        name = p.relative_to(repo).as_posix() if p.is_relative_to(repo) else p.name
        evidence['inputs'].append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    output.with_suffix('.evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'html':str(output),'bytes':output.stat().st_size,'evidence_summary':summary},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
