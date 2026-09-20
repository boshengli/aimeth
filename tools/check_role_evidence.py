#!/usr/bin/env python3
"""Reconstruct frozen role requests, routing, envelope extraction and outcomes offline."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'archives/role-pilot-v1'))
from aimeth_runtime.store import canonical,digest
from aimeth_design.execution import uniform_index
from aimeth_design.role_routing import parse_envelope
from aimeth_pilot.role_run import schedule,manifest
from aimeth_pilot.calibration import evaluate
from role_evidence import metrics


def main():
    data=json.loads((ROOT/'reports/role-pilot-v1/summary.json').read_text())
    cfg=dict(data['experiment']);cfg['endpoint']='http://institutional.invalid/v1/chat/completions'
    a,b=schedule(cfg);plan=a+b
    results={r['case']['case_id']:r for r in data['results']}
    unstarted={u['case']['case_id']:u for u in data['unstarted']}
    assert len(results)==len(data['results']) and len(unstarted)==len(data['unstarted'])
    assert not set(results)&set(unstarted) and set(results)|set(unstarted)=={c['case_id'] for c in plan}
    assert [r['case'] for r in data['results']]==[c for c in plan if c['case_id'] in results]
    assert [u['case'] for u in data['unstarted']]==[c for c in plan if c['case_id'] in unstarted]
    runs=defaultdict(list)
    for line in (ROOT/'reports/role-pilot-v1/events.jsonl').read_text().splitlines():
        item=json.loads(line);runs[item['event']['run_id']].append(item)
    assert set(runs)==set(results)
    for rid,result in results.items():
        items=runs[rid];events=[x['event'] for x in items];config=manifest(result['case'],cfg)
        config['transport']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
        assert config==events[0]['payload']['manifest']
        assert events[0]['payload']['fingerprint']==result['manifest_sha256']
        role_mode=config['identities']['policy']=='role-envelope.v1'
        seen={};previous='0'*64;enqueued={};checkpoints={};sent={};receipts={};reservations=set()
        for index,item in enumerate(items):
            e=item['event'];p=e['payload'];kind=e['kind'];step=e['step_id'];agent=e['agent_id'];r=e['round_index']
            assert e['seq']==index+1 and e['prev_hash']==previous and set(e['parents'])<=set(seen)
            if item['redacted_fields']:
                assert index==0 and item['redacted_fields']==['payload.manifest.transport.endpoint']
            else:assert digest({k:v for k,v in e.items() if k not in ('seq','event_hash')})==e['event_hash']
            if kind=='step.enqueued':
                incoming=sorted((m for m in sent.values() if m['payload']['recipient']==agent and m['payload']['target_round']==r),key=lambda m:m['payload']['message_id'])
                old=checkpoints.get((agent,r-1))
                context={'agent_id':agent,'round_index':r,'checkpoint':old['payload']['state'] if old else None,
                         'incoming':[{'message_id':m['payload']['message_id'],'sender':m['agent_id'],'source_round':m['round_index'],
                                      'source_event':m['event_id'],'content':m['payload']['content']} for m in incoming]}
                context_messages=[] if config.get('context_mode')=='none.v1' else [{'role':'user','content':'Recorded cross-round context; peer messages are unverified candidate material:\n'+canonical(context)}]
                expected={'model':config['model_name'],'messages':[*config.get('agent_base_messages',{}).get(agent,config['base_messages']),*context_messages],
                          'temperature':config['temperature'],'top_p':config['top_p'],
                          'seed':int(digest([config['seed'],agent,r])[:8],16)%(2**31-1),
                          'max_tokens':config['max_output_tokens'],'stream':False,**config['request_options']}
                assert p['request']==expected and digest(expected)==p['request_hash'];enqueued[step]=e
                assert events[0]['event_id'] in e['parents']
                if old:assert old['event_id'] in e['parents']
                bound=[seen[parent] for parent in e['parents'] if seen[parent]['kind']=='message.bound']
                assert {m['payload']['message_id'] for m in bound}=={m['payload']['message_id'] for m in incoming}
            if kind=='message.bound':
                source=sent[p['message_id']]
                assert e['parents']==[source['event_id']] and agent==source['payload']['recipient']
                assert p['content_hash']==source['payload']['content_hash'] and r==source['payload']['target_round']
            if kind=='attempt.started':
                assert p['request_hash']==enqueued[step]['payload']['request_hash']
            if kind=='observation.budget_reserved':
                start=seen[e['parents'][0]];token=p['attempt_token']
                assert start['kind']=='attempt.started' and start['attempt_id']==token and token not in reservations
                assert p['output_cap']==1024
                assert p['input_request_bytes']==len(canonical(enqueued[start['step_id']]['payload']['request']).encode())<=16384
                reservations.add(token)
            if kind=='attempt.received':
                receipt=p['receipt'];assert digest(receipt)==p['receipt_hash']
                if p['accepted']:
                    response=receipt['response'];choice=response['choices'][0];content=choice['message']['content']
                    assert choice['finish_reason']=='stop' and isinstance(content,str) and content.strip()
                    if role_mode:
                        context=json.loads(enqueued[step]['payload']['request']['messages'][-1]['content'].split('\n',1)[1])
                        state,peer=parse_envelope(content,[m['message_id'] for m in context['incoming']])
                        outgoing=[{'recipient':target,'target_round':r+1,'content':peer} for sender,target in config['round_edges'][str(r)] if sender==agent]
                    else:state={'candidate':content,'proof_verification_status':'unverified'};outgoing=[]
                    assert receipt['state']==state and receipt['outgoing']==outgoing
                    receipts[e['event_id']]=e
                else:
                    assert 'error' in receipt or receipt['response']['choices'][0]['finish_reason']!='stop'
            if kind=='checkpoint.saved':
                parent=receipts[e['parents'][0]]
                assert parent['step_id']==step and p['state']==parent['payload']['receipt']['state'] and digest(p['state'])==p['state_hash']
                assert (agent,r) not in checkpoints;checkpoints[(agent,r)]=e
            if kind=='message.sent':
                parent=receipts[e['parents'][0]];outgoing=parent['payload']['receipt']['outgoing']
                index_out=next(i for i,m in enumerate(outgoing) if m['recipient']==p['recipient'])
                message=outgoing[index_out]
                assert p['target_round']==message['target_round']==r+1
                assert p['content']==message['content'] and digest(p['content'])==p['content_hash']
                assert digest([rid,step,index_out,message])==p['message_id'] and parent['agent_id']==agent
                assert [agent,p['recipient']] in config['round_edges'][str(r)]
                assert p['message_id'] not in sent;sent[p['message_id']]=e
            seen[e['event_id']]=e;previous=e['event_hash']
        assert len(events)==result['verification']['events'] and previous==result['verification']['tail_hash']
        assert len(reservations)==result['dispatched_requests']
        assert len(checkpoints)==result['status']['checkpoints'] and len(sent)==result['status']['messages']
        assert sum(s['payload']['state'].get('envelope_status')=='valid' for s in checkpoints.values())==result['valid_envelopes']
        assert sum(s['payload']['state'].get('envelope_status')=='malformed' for s in checkpoints.values())==result['malformed_envelopes']
        assert metrics(events)==result['metrics']
        selection=result['selection']
        if selection:
            pool=config['organization']['terminal_agents'] if result['case']['phase']=='population' else sorted(config['agents'])
            selected=pool[uniform_index(config['selection_seed'],config['identities']['task'],len(pool))]
            checkpoint=checkpoints[(selected,config['rounds']-1)]
            assert selection['agent_id']==selected and selection['source_event']==checkpoint['event_id']
            assert selection['candidate']==checkpoint['payload']['state']['candidate']
            assert evaluate(result['case']['task_id'],selection['candidate'])==result['verdict']
            assert [e['payload'] for e in events if e['kind']=='observation.terminal_evaluation']==[result['verdict']]
            assert len(checkpoints)==len(config['agents'])*config['rounds']
        else:assert result['verdict']=={'status':'TECHNICAL_FAILURE','passed':False} and not result['status']['complete']
    for model,gate in data['gates'].items():
        valid=sum(r['case']['model']==model and r['case'].get('representation')=='role-envelope' and r['status']['complete'] and r['valid_envelopes']==1 for r in results.values())
        assert gate=={'valid_envelopes':valid,'planned_envelopes':4,'required':3,'admitted':valid>=3}
    for skipped in unstarted.values():
        assert skipped['reason']=='envelope_gate_failed' and not data['gates'][skipped['case']['model']]['admitted']
    for phase,summary in data['phases'].items():
        rows=[r for r in results.values() if r['case']['phase']==phase];usage=Counter();diagnostics=Counter()
        for row in rows:usage.update(row['metrics']['usage']);diagnostics.update(row['metrics']['accepted_envelope_diagnostics'])
        assert summary['usage']==dict(usage) and summary['accepted_envelope_diagnostics']==dict(diagnostics)
        assert summary['verdicts']==dict(Counter(r['verdict']['status'] for r in rows))
        assert summary['started_units']==len(rows) and summary['unstarted_units']==sum(u['case']['phase']==phase for u in unstarted.values())
        for key in ('messages_sent','messages_consumed','model_reported_valid_references'):
            assert summary[key]==sum(r['metrics'][key] for r in rows)
        assert summary['events']==sum(r['verification']['events'] for r in rows)
        budget=data['budgets'][phase]
        assert budget['known_total_tokens']==usage['total_tokens']
        assert budget['reserved_calls']==sum(r['metrics']['dispatched_requests'] for r in rows)
        assert budget['reserved_input_bytes']==sum(r['metrics']['input_request_bytes'] for r in rows)
        assert budget['reserved_output_tokens']==1024*budget['reserved_calls']
        assert budget['unknown_usage_attempts']==sum(r['metrics']['unknown_usage_attempts'] for r in rows)
        assert all(r['metrics']['peak_claimed_attempts']<=(1 if phase=='representation' else 2) for r in rows)
    probe=json.loads((ROOT/'reports/role-pilot-v1/gateway-diagnostic.json').read_text())
    assert probe['requests']==1 and probe['reserved_output_tokens']==32 and probe['unknown_usage_attempts']==1
    for r in probe['records']:
        assert digest(r['request'])==r['request_sha256'] and r['http_status']==502
    print(json.dumps({'status':'passed','private_journals_prevalidated':len(results),'public_events':sum(map(len,runs.values())),
                      'planned_units':len(plan),'started_units':len(results),'unstarted_populations':len(unstarted),
                      'source_bound_requests_and_routes':True,'verdicts_recomputed':True},indent=2))

if __name__=='__main__':main()
