#!/usr/bin/env python3
"""Rebuild the immutable M2.1 HTML from frozen evidence and template."""
import argparse
import html
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def graph_svg(config):
    names = config['agents']
    groups = config['organization']['groups']
    coordinates = {}
    colors = ['#176f70', '#b26c2a', '#6860a3', '#546b37']
    for k, group in enumerate(groups):
        cx, cy = (380, 175) if len(names) == 1 else (190 + 380*(k%2), 90 + 170*(k//2))
        for i, agent in enumerate(group):
            angle = i * 2*math.pi / len(group)
            coordinates[agent] = (cx + (0 if len(names)==1 else 66*math.cos(angle)),
                                  cy + (0 if len(names)==1 else 66*math.sin(angle)), colors[k%4])
    body = []
    for a,b in config['round_edges']['0']:
        x,y,_ = coordinates[a]; xx,yy,_=coordinates[b]
        body.append(f'<path d="M{x:.1f},{y:.1f} L{xx:.1f},{yy:.1f}" stroke="#728b91" stroke-opacity=".42" marker-end="url(#arrow)"/>')
    for name,(x,y,color) in coordinates.items():
        body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="{color}"/><text x="{x:.1f}" y="{y+4:.1f}" text-anchor="middle" fill="white" font-size="10">{int(name[1:])+1}</text>')
    return '<svg viewBox="0 0 760 350" role="img" aria-label="当前组织的实际 32 节点配置；S 为单节点"><defs><marker id="arrow" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0,0L10,5L0,10Z" fill="#728b91"/></marker></defs>'+''.join(body)+'</svg>'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args=parser.parse_args()
    evidence=json.loads((ROOT/'milestones/m2-1-organization-v1.evidence.json').read_text())
    v=json.loads((ROOT/'reports/m2-1-validation.json').read_text())
    template=(ROOT/'templates/milestone-organization-v1.html').read_text()
    svgs={a:graph_svg(json.loads((ROOT/f'examples/organizations/{a}.manifest.json').read_text())) for a in 'SILX'}
    trace_rows=''.join(f'<tr><td>{r["arm"]}</td><td>{r["status"]["planned_total_steps"]}</td><td>{r["status"]["messages"]}</td><td>{r["verification"]["events"]}</td><td>{r["verification"]["status"]}</td></tr>' for r in v['trace_runs'])
    replacements={
        '@@SVG@@':svgs['X'], '@@SVGS@@':json.dumps(svgs,ensure_ascii=False).replace('</','<\\/'),
        '@@TRACE_ROWS@@':trace_rows, '@@TEST_COUNT@@':str(v['unit_tests']['count']),
        '@@BASELINE@@':html.escape(evidence['baseline_commit']),
        '@@IMPLEMENTATION@@':html.escape(evidence['implementation_commit']),
        '@@EVIDENCE@@':html.escape(json.dumps(evidence,indent=2,ensure_ascii=False)),
        '@@PLAN@@':html.escape(json.dumps(v['large_plan'],indent=2,ensure_ascii=False)),
    }
    for key,value in replacements.items():
        template=template.replace(key,value)
    if '@@' in template:
        raise ValueError('Unresolved report placeholder')
    Path(args.output).write_text(template,encoding='utf-8')


if __name__=='__main__':
    main()
