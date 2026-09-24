#!/usr/bin/env python3
"""Replay source-bound contextual requests and strict post-response extraction."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--batch',choices=['v1','v2'],required=True)
args=p.parse_args();archive=ROOT/'archives'/('role-contract-'+args.batch)
sys.path.insert(0,str(archive))
from aimeth_runtime.store import canonical,digest
from aimeth_design.role_routing import parse_envelope
from aimeth_pilot import role_contract as protocol
from aimeth_pilot.calibration import evaluate
from contract_evidence import metrics,aggregate,valid

source=json.loads((archive/'source.json').read_text())
for f in source['files']:
    raw=(archive/f['path']).read_bytes();assert len(raw)==f['bytes'] and hashlib.sha256(raw).hexdigest()==f['sha256']
data=json.loads((ROOT/'reports'/('role-contract-'+args.batch)/'summary.json').read_text())
cfg=dict(data['experiment']);assert cfg['source_commit']==source['source_commit']
cfg['endpoint']='http://institutional.invalid/v1/chat/completions'
raw=(archive/'examples/role-contract-contexts-v1.json').read_bytes();fixtures=json.loads(raw)
assert hashlib.sha256(raw).hexdigest()==cfg['fixture_file_sha256']
fixture_source=ROOT/fixtures['source_events_file']
assert hashlib.sha256(fixture_source.read_bytes()).hexdigest()==fixtures['source_events_sha256']
original={x['event']['event_id']:x['event'] for x in map(json.loads,fixture_source.read_text().splitlines())}
for f in fixtures['fixtures'].values():
    e=original[f['source_event_id']]
    assert e['run_id']==f['source_run_id'] and e['payload']['request_hash']==f['source_request_sha256']
    assert e['payload']['request']['messages'][-1]==f['context_message']
probes,cases=(protocol.schedule if args.batch=='v1' else protocol.schedule_v2)(cfg);plan=probes+cases
results={r['case']['case_id']:r for r in data['results']};unstarted={r['case']['case_id']:r for r in data['unstarted']}
assert not set(results)&set(unstarted) and set(results)|set(unstarted)=={c['case_id'] for c in plan}
assert [r['case'] for r in data['results']]==[c for c in plan if c['case_id'] in results]
assert [r['case'] for r in data['unstarted']]==[c for c in plan if c['case_id'] in unstarted]
runs=defaultdict(list)
for x in map(json.loads,(ROOT/'reports'/('role-contract-'+args.batch)/'events.jsonl').read_text().splitlines()):runs[x['event']['run_id']].append(x)
assert set(runs)==set(results)
for rid,result in results.items():
    events=[x['event'] for x in runs[rid]];config=protocol.manifest(result['case'],cfg,fixtures)
    config['transport']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
    assert events[0]['payload']['manifest']==config
    assert events[0]['payload']['fingerprint']==result['manifest_sha256']
    previous='0'*64;seen={};request=None;accepted=None;checkpoint=None;reservations={};evaluations=[]
    for i,item in enumerate(runs[rid]):
        e=item['event'];p=e['payload'];kind=e['kind']
        assert e['seq']==i+1 and e['prev_hash']==previous and set(e['parents'])<=set(seen)
        if item['redacted_fields']:assert i==0 and item['redacted_fields']==['payload.manifest.transport.endpoint']
        else:assert digest({k:v for k,v in e.items() if k not in ('seq','event_hash')})==e['event_hash']
        if kind=='step.enqueued':
            expected={'model':config['model_name'],'messages':config['base_messages'],
                      'temperature':config['temperature'],'top_p':config['top_p'],
                      'seed':int(digest([config['seed'],'a00000',0])[:8],16)%(2**31-1),
                      'max_tokens':config['max_output_tokens'],'stream':False,**config.get('request_options',{})}
            assert p['request']==expected and p['request_hash']==digest(expected);request=e
        if kind=='attempt.started':assert p['request_hash']==request['payload']['request_hash']
        if kind=='observation.budget_reserved':
            assert p['output_cap']==config['max_output_tokens']
            assert p['input_request_bytes']==len(canonical(request['payload']['request']).encode())<=16384
            assert p['attempt_token'] not in reservations;reservations[p['attempt_token']]=p
        if kind in ('attempt.received','attempt.late_received'):
            receipt=p['receipt'];assert digest(receipt)==p['receipt_hash']
            if p['accepted']:
                choice=receipt['response']['choices'][0];content=choice['message']['content']
                assert choice['finish_reason']=='stop' and isinstance(content,str) and content.strip()
                state={'candidate':content,'proof_verification_status':'not_applicable'} if result['case']['phase']=='availability' else parse_envelope(content,protocol.incoming_ids(config))[0]
                assert receipt['state']==state and receipt['outgoing']==[];accepted=e
        if kind=='checkpoint.saved':
            assert accepted and e['parents']==[accepted['event_id']]
            assert p['state']==accepted['payload']['receipt']['state'] and digest(p['state'])==p['state_hash'];checkpoint=e
        assert kind not in ('message.sent','message.bound')
        if kind=='observation.contract_evaluation':evaluations.append(p)
        seen[e['event_id']]=e;previous=e['event_hash']
    assert previous==result['verification']['tail_hash'] and len(events)==result['verification']['events']
    assert len(reservations)==result['dispatched_requests'] and metrics(events)==result['metrics']
    if result['selection']:
        selected=result['selection'];assert selected['agent_id']=='a00000' and selected['source_event']==checkpoint['event_id']
        assert selected['candidate']==checkpoint['payload']['state']['candidate']
    assert bool(checkpoint)==result['status']['complete']
    envelope=checkpoint['payload']['state'].get('envelope_status') if checkpoint else None
    assert envelope==result['envelope_status']
    if result['case']['phase']=='availability':expected={'status':'AVAILABLE' if checkpoint else 'TECHNICAL_FAILURE','mathematical_evaluation':False}
    else:expected=evaluate(result['case']['task_id'],result['selection']['candidate']) if checkpoint else {'status':'TECHNICAL_FAILURE','passed':False}
    assert expected==result['verdict'] and evaluations==[{'verdict':expected,'envelope_status':envelope}]
assert aggregate(data)==data['aggregates']
for model,gate in data['readiness'].items():
    rows=[r for r in data['results'] if r['case']['model']==model and r['case'].get('contract')=='output-card']
    count=sum(valid(r) for r in rows)
    assert gate=={'valid_complete':count,'planned':32,'required':32,'ready_for_bounded_multiround_contract_check':len(rows)==32 and count==32,'population_or_mathematical_efficacy_proven':False}
for key,metric in [('reserved_calls','requests'),('known_total_tokens','known_tokens'),('unknown_usage_attempts','unknown_usage_attempts')]:assert data['budget'][key]==data['aggregates'][metric]
assert data['budget']['reserved_output_tokens']==sum(r['metrics']['reserved_output_tokens'] for r in results.values())
assert data['budget']['reserved_input_bytes']==sum(r['metrics']['input_request_bytes'] for r in results.values())
for skipped in unstarted.values():
    if skipped['reason']=='availability_gate_failed':assert args.batch=='v1' and not data['availability_gates'][skipped['case']['model']]
print(json.dumps({'batch':args.batch,'status':'passed','journals':len(results),'events':data['aggregates']['events'],'planned':len(plan),'unstarted':len(unstarted)}))
