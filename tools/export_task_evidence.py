#!/usr/bin/env python3
"""Verify private journals and export endpoint-redacted task diagnostics."""
import argparse
import copy
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from aimeth_runtime.store import Store, digest
from aimeth_design.role_routing import parse_envelope
from aimeth_pilot.calibration import evaluate
from aimeth_pilot.role_contract import incoming_ids
from aimeth_pilot.task_continuation import schedule
from contract_evidence import metrics


def aggregates(data):
    groups=[]
    all_cases=[r['case'] for r in data['results']+data['unstarted']]
    for model,contract,task in sorted({(c['model'],c['contract'],c['task_id']) for c in all_cases}):
        rows=[r for r in data['results'] if (r['case']['model'],r['case']['contract'],r['case']['task_id'])==(model,contract,task)]
        planned=sum((c['model'],c['contract'],c['task_id'])==(model,contract,task) for c in all_cases)
        groups.append(dict(model=model,contract=contract,task_id=task,planned=planned,started=len(rows),
            valid=sum(r['status']['complete'] and r['envelope_status']=='valid' for r in rows),
            math_passed=sum(r['verdict'].get('passed',False) for r in rows),
            technical=sum(not r['status']['complete'] for r in rows),unstarted=planned-len(rows)))
    pairs=defaultdict(dict);paired=defaultdict(Counter)
    for r in data['results']:pairs[r['case']['block_order']][r['case']['contract']]=r
    for block in pairs.values():
        if set(block)!={'legacy-card','unified-task-schema'}:continue
        a,b=block['legacy-card'],block['unified-task-schema'];model=a['case']['model']
        paired[model]['executed_pairs']+=1
        if not(a['status']['complete'] and b['status']['complete']):continue
        paired[model]['complete_pairs']+=1
        av=a['envelope_status']=='valid';bv=b['envelope_status']=='valid'
        paired[model]['both_valid' if av and bv else 'unified_only' if bv else 'legacy_only' if av else 'neither_valid']+=1
    return {'groups':groups,'paired_format':dict(paired),
            'planned':len(all_cases),'started':len(data['results']),'unstarted':len(data['unstarted']),
            'events':sum(r['verification']['events'] for r in data['results']),
            'requests':sum(r['metrics']['dispatched_requests'] for r in data['results']),
            'known_total_tokens':sum(r['metrics']['usage'].get('total_tokens',0) for r in data['results']),
            'unknown_usage_attempts':sum(r['metrics']['unknown_usage_attempts'] for r in data['results'])}


def validate_rows(data, traces, *, redacted):
    expected={c['case_id']:c for c in schedule()}
    actual=[r['case'] for r in data['results']+data['unstarted']]
    assert len(actual)==len(expected)==16
    assert {c['case_id']:c for c in actual}==expected
    assert set(traces)=={r['case']['case_id'] for r in data['results']}
    for row in data['results']:
        events=traces[row['case']['case_id']];seen=set();previous='0'*64
        assert events[0]['kind']=='run.created'
        for i,e in enumerate(events):
            assert e['prev_hash']==previous and set(e['parents'])<=seen
            if not(redacted and i==0):
                assert digest({k:v for k,v in e.items() if k not in ('seq','event_hash')})==e['event_hash']
            previous=e['event_hash'];seen.add(e['event_id'])
        assert previous==row['verification']['tail_hash']
        assert len(events)==row['verification']['events']
        cfg=events[0]['payload']['manifest']
        assert cfg['execution_source']==data['experiment']['source_commit']
        assert cfg['contract_case']==row['case']
        assert row['metrics']==metrics(events)
        if row['status']['complete']:
            receipts=[e['payload']['receipt']['response'] for e in events
                      if e['kind']=='attempt.received' and e['payload']['accepted']]
            assert len(receipts)==1
            state,_=parse_envelope(receipts[0]['choices'][0]['message']['content'],incoming_ids(cfg))
            assert state['envelope_status']==row['envelope_status']
            assert state['candidate']==row['selection']['candidate']
            assert evaluate(row['case']['task_id'],state['candidate'])==row['verdict']
    agg=aggregates(data)
    assert agg==data['aggregates']
    for a,b in [('requests','reserved_calls'),('known_total_tokens','known_total_tokens'),('unknown_usage_attempts','unknown_usage_attempts')]:
        assert agg[a]==data['budget'][b]
    return agg


def export(source,out):
    out.mkdir(parents=True,exist_ok=True)
    data=json.loads((source/'summary-private.json').read_text());traces={}
    data['raw_summary_sha256']=hashlib.sha256((source/'summary-private.json').read_bytes()).hexdigest()
    data['source_archive']=json.loads((source/'source-archive.json').read_text())
    assert hashlib.sha256((source/'submitted-source.tar.gz').read_bytes()).hexdigest()==data['source_archive']['sha256']
    for row in data['results']:
        rid=row['case']['case_id'];record=source/rid/'export'
        with tempfile.TemporaryDirectory() as tmp:
            snap=Path(tmp)/'snapshot.sqlite';shutil.copy2(record/'snapshot.sqlite',snap)
            with Store(snap) as s:assert s.verify(rid)==row['verification']
        traces[rid]=[json.loads(s) for s in (record/'events.jsonl').read_text().splitlines()]
        row['metrics']=metrics(traces[rid])
        row['raw_events_sha256']=hashlib.sha256((record/'events.jsonl').read_bytes()).hexdigest()
        row['raw_snapshot_sha256']=hashlib.sha256((record/'snapshot.sqlite').read_bytes()).hexdigest()
    data['aggregates']=aggregates(data);validate_rows(data,traces,redacted=False)
    data['experiment']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
    data['metadata']['hostname']='[LOCAL_CLIENT_REDACTED]'
    data['public_trace_policy']='Only first-event endpoint redacted; retained original first hash requires private original for full chain reconstruction. Later hashes and outcomes replay offline.'
    with (out/'events.jsonl').open('w') as stream:
        for rows in traces.values():
            for e in rows:
                item=copy.deepcopy(e);fields=[]
                if e['kind']=='run.created':
                    item['payload']['manifest']['transport']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
                    fields=['payload.manifest.transport.endpoint']
                stream.write(json.dumps({'redacted_fields':fields,'event':item},ensure_ascii=False,sort_keys=True)+'\n')
    (out/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return data['aggregates']


def check(out):
    data=json.loads((out/'summary.json').read_text());traces=defaultdict(list)
    for s in (out/'events.jsonl').read_text().splitlines():
        line=json.loads(s);e=line['event']
        assert line['redacted_fields']==(['payload.manifest.transport.endpoint'] if e['kind']=='run.created' else [])
        traces[e['run_id']].append(e)
    return validate_rows(data,traces,redacted=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path);p.add_argument('--check',action='store_true')
    p.add_argument('--output',type=Path,default=ROOT/'reports/task-continuation-v1')
    args=p.parse_args()
    if args.check:result=check(args.output)
    else:
        if args.source is None:p.error('--source required for export')
        result=export(args.source,args.output)
    print(json.dumps(result,indent=2))
