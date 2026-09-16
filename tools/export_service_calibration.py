#!/usr/bin/env python3
"""Review private single-step journals and export URL-redacted public evidence."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aimeth_runtime.store import Store,digest
from aimeth_pilot.calibration import evaluate,schedule


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')


def export(source,output):
    raw_summary=source/'summary-private.json';summary=json.loads(raw_summary.read_text())
    assert [r['case'] for r in summary['results']]==schedule(summary['experiment'])[:len(summary['results'])]
    output.mkdir(parents=True,exist_ok=True)
    results=[];total_usage=Counter()
    with (output/'events.jsonl').open('w') as public:
        for original in summary['results']:
            result=copy.deepcopy(original);rid=result['case']['case_id'];raw=source/'records'/rid/'export'
            with tempfile.TemporaryDirectory() as tmp:
                p=Path(tmp)/'snapshot.sqlite';shutil.copy2(raw/'snapshot.sqlite',p)
                with Store(p) as store:assert store.verify(rid)==result['verification']
            events=[json.loads(l) for l in (raw/'events.jsonl').read_text().splitlines()]
            usage=Counter();finishes=Counter();errors=[];previous='0'*64;seen=set()
            for event in events:
                assert event['prev_hash']==previous and set(event['parents'])<=seen
                assert digest({k:v for k,v in event.items() if k not in ('seq','event_hash')})==event['event_hash']
                previous=event['event_hash'];seen.add(event['event_id'])
                published=copy.deepcopy(event);redacted=[]
                if event['kind']=='run.created':
                    published['payload']['manifest']['transport']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
                    redacted=['payload.manifest.transport.endpoint']
                if event['kind']=='attempt.received':
                    payload=event['payload'];response=payload['receipt'].get('response',{})
                    for choice in response.get('choices',[]):finishes[str(choice.get('finish_reason'))]+=1
                    if 'error' in payload['receipt']:errors.append(payload['receipt']['error'])
                    for key in ('prompt_tokens','completion_tokens','total_tokens'):
                        value=(response.get('usage') or {}).get(key)
                        if type(value) is int:usage[key]+=value
                public.write(json.dumps({'redacted_fields':redacted,'event':published},sort_keys=True,ensure_ascii=False)+'\n')
            assert previous==result['verification']['tail_hash']
            if result['selection']:assert evaluate(result['case']['task_id'],result['selection']['candidate'])==result['verdict']
            diagnostic=result['verdict']['status']
            if diagnostic=='TECHNICAL_FAILURE':diagnostic='TRUNCATED_GENERATION' if finishes['length'] else 'TRANSPORT_OR_RUNTIME_FAILURE'
            result.update(diagnostic=diagnostic,usage=dict(usage),finish_reasons=dict(finishes),errors=errors,
                          raw_events_sha256=sha(raw/'events.jsonl'),raw_snapshot_sha256=sha(raw/'snapshot.sqlite'))
            results.append(result);total_usage.update(usage)
    assert total_usage['total_tokens']==summary['quota']['known_total_tokens']
    data=copy.deepcopy(summary);data['experiment']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
    data.update(results=results,usage=dict(total_usage),raw_summary_sha256=sha(raw_summary),
                diagnostic_counts=dict(Counter(r['diagnostic'] for r in results)),
                public_trace_policy='Only first-event gateway URL redacted; original hashes retained. All later event/request/receipt hashes and exact verdicts replayable; first-event reconstruction requires restricted original.')
    write(output/'summary.json',data)
    print(json.dumps({'cases':len(results),'usage':dict(total_usage),'diagnostics':data['diagnostic_counts']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();export(args.source,args.output)
