#!/usr/bin/env python3
"""Deterministically render M1.1 from versioned validation and synthetic trace evidence."""
import argparse
import hashlib
from html import escape
import json
from pathlib import Path
import re
import sys


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=root/'milestones/m1-1-runtime-v1.html');args=parser.parse_args()
    paths=['milestones/m1-1-runtime-v1.json','reports/runtime-validation.json','reports/runtime-load-10000.json','reports/github-publication.json','examples/runtime/demo.events.jsonl','templates/milestone-runtime-v1.html']
    content,validation,load,publish=[json.loads((root/p).read_text()) for p in paths[:4]]
    events=[json.loads(line) for line in (root/paths[4]).read_text().splitlines()]
    snapshot=root/'archives/runtime-v0.1/aimeth_runtime'
    source_hash=hashlib.sha256()
    for p in sorted(snapshot.glob('*.py')): source_hash.update(p.name.encode()+b'\0'+p.read_bytes()+b'\0')
    identity='sha256:'+source_hash.hexdigest()
    if identity!=validation['code_identity'] or identity!=load['code_identity']: raise ValueError('Archived runtime source differs from frozen validation')
    if validation['unit_tests']['exit_code'] or not load['status']['complete'] or load['verification']['status']!='verified': raise ValueError('Cannot publish passing result from failed evidence')
    if load['external_model_calls'] or validation['proof_verified']: raise ValueError('This report is scoped to synthetic engineering evidence')
    def rows(items):
        return ''.join('<tr>'+''.join('<td>'+escape(str(value))+'</td>' for value in row)+'</tr>' for row in items)
    event_rows=''.join('<tr data-kind="'+escape(e['kind'].split('.')[0])+'"><td>'+str(e['seq'])+'</td><td><code>'+escape(e['kind'])+'</code></td><td>'+escape(e['step_id'] or 'run')+'</td><td><code>'+escape(e['event_id'][:8])+'</code></td><td>'+escape(', '.join(p[:8] for p in e['parents']) or '起点')+'</td></tr>' for e in events)
    cards=''.join('<article><span class="label">'+escape(item['state'])+'</span><h3>'+escape(item['title'])+'</h3><p>'+escape(item['body'])+'</p></article>' for item in content['readiness'])
    replacements={
        'TITLE':escape(content['title']),'DATE':content['date'],'OUTCOME':escape(content['outcome']),
        'TESTS':str(validation['tests_passed']),'EVENTS':f"{load['status']['events']:,}",'MESSAGES':f"{load['status']['messages']:,}",'TASKS':f"{load['status']['steps']['succeeded']:,}",
        'SECONDS':f"{load['elapsed_seconds']:.1f}",'RATE':f"{load['canonical_steps_per_second']:.1f}",'PYTHON':escape(load['environment']['python']),'SQLITE':escape(load['environment']['sqlite']),
        'DB_MB':f"{load['database_bytes']/1024**2:.1f}",'REQUIREMENTS':rows(content['requirements']),'FAULTS':rows(content['faults']),'READINESS':cards,
        'LIMITATIONS':''.join('<li>'+escape(s)+'</li>' for s in content['limitations']),
        'TRACE_ROWS':event_rows,'TRACE_COUNT':str(len(events)),'CODE_COMMIT':validation['code_commit'],'CODE_HASH':validation['code_identity'],'TAIL_HASH':load['verification']['tail_hash'],
        'PUBLICATION':escape(publish['human_status_zh']),
        'CHECK_DETAIL':escape(validation['unit_tests']['output']),
        'META':escape(json.dumps({'milestone':'M1.1','version':'1.0','code_commit':validation['code_commit'],'code_identity':validation['code_identity'],'load_tail_hash':load['verification']['tail_hash'],'publication_status':publish['status'],'proof_verified':False},ensure_ascii=False,indent=2))
    }
    html=(root/paths[-1]).read_text()
    for key,value in replacements.items(): html=html.replace('@@'+key+'@@',value)
    if re.search(r'@@[A-Z_]+@@',html): raise ValueError('Unexpanded template field')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(html)
    inputs=paths+['tools/build_runtime_milestone.py']+[p.relative_to(root).as_posix() for p in sorted(snapshot.glob('*.py'))]
    evidence={'schema_version':'1.0','milestone':'M1.1','code_commit':validation['code_commit'],'inputs':[{'path':p,'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest()} for p in inputs],'scientific_validity_checked':False}
    args.output.with_suffix('.evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'html':str(args.output),'bytes':args.output.stat().st_size,'tests':validation['tests_passed'],'trace_events':len(events)}))


if __name__=='__main__': main()
