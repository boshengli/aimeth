#!/usr/bin/env python3
"""Publish reviewed mathematical traces; redact only the private gateway URL.

Original event hashes are preserved. The first event cannot be recomputed from
the redacted public manifest; every subsequent event can. This is deliberately
not advertised as a complete public replica of the private SQLite journal.
"""
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
from aimeth_runtime.store import Store, digest
from aimeth_design.execution import select_terminal


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def export(source,output):
    summary_path=source/'summary-private.json'
    summary=json.loads(summary_path.read_text())
    output.mkdir(parents=True,exist_ok=True)
    results=[]; totals=Counter(); finishes=Counter(); response_models=Counter()
    with (output/'events.jsonl').open('w') as public:
        for result in summary['results']:
            rid=result['run_id']; raw=source/'records'/rid
            # Verify a copy to keep the original file identity unchanged.
            with tempfile.TemporaryDirectory() as tmp:
                copied=Path(tmp)/'journal.sqlite';shutil.copy2(raw/'export/snapshot.sqlite',copied)
                with Store(copied) as store:
                    assert store.verify(rid)==result['verification']
                    if result['selection']:
                        assert select_terminal(store,rid,result['selection']['selection_seed'])==result['selection']
            events=[json.loads(line) for line in (raw/'export/events.jsonl').read_text().splitlines()]
            previous='0'*64;seen=set();usage=Counter();kinds=Counter();stop=Counter()
            for event in events:
                assert event['prev_hash']==previous and set(event['parents'])<=seen
                assert digest({k:v for k,v in event.items() if k not in ('seq','event_hash')})==event['event_hash']
                seen.add(event['event_id']);previous=event['event_hash'];kinds[event['kind']]+=1
                redactions=[]; published=copy.deepcopy(event)
                if event['kind']=='run.created':
                    published['payload']['manifest']['transport']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
                    redactions=['payload.manifest.transport.endpoint']
                if event['kind']=='attempt.received':
                    response=event['payload']['receipt'].get('response',{})
                    for key in ('prompt_tokens','completion_tokens','total_tokens'):
                        value=(response.get('usage') or {}).get(key)
                        if type(value) is int:usage[key]+=value
                    for choice in response.get('choices',[]):stop[str(choice.get('finish_reason'))]+=1
                    if response.get('model'):response_models[response['model']]+=1
                public.write(json.dumps({'redacted_fields':redactions,'event':published},ensure_ascii=False,sort_keys=True)+'\n')
            assert previous==result['verification']['tail_hash']
            assert usage['total_tokens']==result['status']['known_total_tokens']
            record=copy.deepcopy(result)
            record.update(usage=dict(usage),event_kinds=dict(kinds),finish_reasons=dict(stop),
                          raw_events_sha256=sha(raw/'export/events.jsonl'),
                          raw_snapshot_sha256=sha(raw/'export/snapshot.sqlite'))
            results.append(record);totals.update(usage);finishes.update(stop)
    experiment=copy.deepcopy(summary['experiment']);experiment['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
    metadata={k:v for k,v in summary['metadata'].items() if k!='hostname'}
    report={'schema_version':'1.0','scope':summary['scope'],'experiment':experiment,'metadata':metadata,
            'planned_populations':summary['planned_populations'],'unstarted_populations':summary['unstarted_populations'],
            'quota':summary['quota'],'results':results,'usage':dict(totals),'finish_reasons':dict(finishes),
            'response_models':dict(response_models),'raw_summary_sha256':sha(summary_path),
            'public_trace_policy':'Original event hashes retained; only run.created gateway URL redacted. First-event hash requires restricted original; all later hashes, request/receipt hashes, selection and exact verdicts publicly replayable.',
            'frontier_proof_verified':False,'weights_independently_attested':False}
    write(output/'summary.json',report)
    print(json.dumps({'output':str(output),'populations':len(results),'usage':dict(totals),'verdicts':dict(Counter(r['verdict']['status'] for r in results))}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();export(args.source,args.output)
