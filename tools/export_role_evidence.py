#!/usr/bin/env python3
"""Validate private journals before publishing reviewed redacted role-pilot traces."""
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'archives/role-pilot-v1'))
from aimeth_runtime.store import Store,digest
from role_evidence import metrics


def main():
    source=ROOT/'runs/hf-pilot-v1/remote/results';out=ROOT/'reports/role-pilot-v1';out.mkdir(parents=True,exist_ok=True)
    summary=json.loads((source/'summary-private.json').read_text());data=copy.deepcopy(summary)
    data['experiment']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
    data['raw_summary_sha256']=hashlib.sha256((source/'summary-private.json').read_bytes()).hexdigest()
    with (out/'events.jsonl').open('w') as stream:
        for result in data['results']:
            rid=result['case']['case_id'];export=source/'records'/rid/'export'
            with tempfile.TemporaryDirectory() as temp:
                snapshot=Path(temp)/'snapshot.sqlite';shutil.copy2(export/'snapshot.sqlite',snapshot)
                with Store(snapshot) as store:assert store.verify(rid)==result['verification']
            events=[json.loads(line) for line in (export/'events.jsonl').read_text().splitlines()]
            previous='0'*64;seen=set()
            for e in events:
                assert e['prev_hash']==previous and set(e['parents'])<=seen
                assert digest({k:v for k,v in e.items() if k not in ('seq','event_hash')})==e['event_hash']
                previous=e['event_hash'];seen.add(e['event_id']);published=copy.deepcopy(e);redacted=[]
                if e['kind']=='run.created':
                    published['payload']['manifest']['transport']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
                    redacted=['payload.manifest.transport.endpoint']
                stream.write(json.dumps({'redacted_fields':redacted,'event':published},sort_keys=True,ensure_ascii=False)+'\n')
            assert previous==result['verification']['tail_hash']
            result['metrics']=metrics(events)
            result['raw_events_sha256']=hashlib.sha256((export/'events.jsonl').read_bytes()).hexdigest()
            result['raw_snapshot_sha256']=hashlib.sha256((export/'snapshot.sqlite').read_bytes()).hexdigest()
    data['public_trace_policy']='Only first-event endpoint redacted, original hash retained. First-event hash reconstruction requires restricted originals. Later events and complete requests/receipts/role routing/verdicts replay offline.'
    data['phases']={}
    for phase in ('representation','population'):
        rows=[r for r in data['results'] if r['case']['phase']==phase];usage=Counter();diagnostics=Counter()
        for r in rows:usage.update(r['metrics']['usage']);diagnostics.update(r['metrics']['accepted_envelope_diagnostics'])
        data['phases'][phase]={'started_units':len(rows),'unstarted_units':sum(u['case']['phase']==phase for u in data['unstarted']),
                              'verdicts':dict(Counter(r['verdict']['status'] for r in rows)), 'usage':dict(usage),
                              'accepted_envelope_diagnostics':dict(diagnostics),
                              'events':sum(r['verification']['events'] for r in rows),
                              'messages_sent':sum(r['metrics']['messages_sent'] for r in rows),
                              'messages_consumed':sum(r['metrics']['messages_consumed'] for r in rows),
                              'model_reported_valid_references':sum(r['metrics']['model_reported_valid_references'] for r in rows)}
        assert usage['total_tokens']==data['budgets'][phase]['known_total_tokens']
    (out/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    shutil.copy2(ROOT/'runs/hf-pilot-v1/gateway-diagnostic/public-summary.json',out/'gateway-diagnostic.json')
    print(json.dumps(data['phases'],indent=2))

if __name__=='__main__':main()
