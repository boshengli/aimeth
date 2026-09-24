#!/usr/bin/env python3
"""Verify restricted snapshots, then publish endpoint-redacted derivatives."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',choices=['v1','v2'],required=True)
args=p.parse_args();sys.path.insert(0,str(ROOT/'archives'/('role-contract-'+args.batch)))
from aimeth_runtime.store import Store,digest
from contract_evidence import metrics,aggregate

source=ROOT/'runs'/('role-contract-'+args.batch)/'remote/results'
out=ROOT/'reports'/('role-contract-'+args.batch);out.mkdir(parents=True,exist_ok=True)
data=json.loads((source/'summary-private.json').read_text())
data['experiment']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
data['batch']=args.batch
data['raw_summary_sha256']=hashlib.sha256((source/'summary-private.json').read_bytes()).hexdigest()
with (out/'events.jsonl').open('w') as stream:
    for result in data['results']:
        rid=result['case']['case_id'];export=source/'records'/rid/'export'
        with tempfile.TemporaryDirectory() as tmp:
            snap=Path(tmp)/'snapshot.sqlite';shutil.copy2(export/'snapshot.sqlite',snap)
            with Store(snap) as store:assert store.verify(rid)==result['verification']
        events=[json.loads(x) for x in (export/'events.jsonl').read_text().splitlines()]
        previous='0'*64;seen=set()
        for e in events:
            assert e['prev_hash']==previous and set(e['parents'])<=seen
            assert digest({k:v for k,v in e.items() if k not in ('seq','event_hash')})==e['event_hash']
            previous=e['event_hash'];seen.add(e['event_id']);item=copy.deepcopy(e);redacted=[]
            if e['kind']=='run.created':
                item['payload']['manifest']['transport']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
                redacted=['payload.manifest.transport.endpoint']
            stream.write(json.dumps({'redacted_fields':redacted,'event':item},ensure_ascii=False,sort_keys=True)+'\n')
        assert previous==result['verification']['tail_hash']
        result['metrics']=metrics(events)
        for kind in ('events.jsonl','snapshot.sqlite'):
            result['raw_'+kind.replace('.','_')+'_sha256']=hashlib.sha256((export/kind).read_bytes()).hexdigest()
data['aggregates']=aggregate(data)
assert data['aggregates']['requests']==data['budget']['reserved_calls']
assert data['aggregates']['known_tokens']==data['budget']['known_total_tokens']
assert data['aggregates']['unknown_usage_attempts']==data['budget']['unknown_usage_attempts']
data['public_trace_policy']='First-event endpoint redacted; original event hash retained and requires restricted original for reconstruction. All later requests/receipts/checkpoints/selection/verdicts can replay offline.'
(out/'summary.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'batch':args.batch,'started':len(data['results']),'unstarted':len(data['unstarted']),**{k:v for k,v in data['aggregates'].items() if k!='groups'}},indent=2))
