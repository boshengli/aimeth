#!/usr/bin/env python3
"""Replay the archived calibration design, receipts, ancestry and exact verdicts."""
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
archive=ROOT/'archives/service-calibration-v1'
sys.path.insert(0,str(archive if archive.exists() else ROOT))
from aimeth_runtime.store import digest
from aimeth_pilot.calibration import evaluate,manifest,schedule


def main():
    root=ROOT/'reports/service-calibration-v1';data=json.loads((root/'summary.json').read_text())
    expected=schedule(data['experiment']);assert len(expected)==48
    assert [r['case'] for r in data['results']]==expected[:len(data['results'])]
    assert len(data['results'])+data['unstarted_cases']==48
    runs=defaultdict(list)
    for line in (root/'events.jsonl').read_text().splitlines():
        item=json.loads(line);runs[item['event']['run_id']].append(item)
    assert set(runs)=={r['case']['case_id'] for r in data['results']}
    tokens=Counter();verdicts=Counter();n=0
    for result in data['results']:
        events=runs[result['case']['case_id']];seen={};previous='0'*64;usage=Counter();finishes=Counter()
        config=events[0]['event']['payload']['manifest']
        wanted=manifest(result['case'],'http://example.invalid/v1/chat/completions')
        wanted['transport']['endpoint']='[INSTITUTIONAL_GATEWAY_REDACTED]'
        assert config==wanted
        for index,item in enumerate(events):
            event=item['event'];payload=event['payload']
            assert event['seq']==index+1 and event['prev_hash']==previous
            assert set(event['parents'])<=set(seen)
            if item['redacted_fields']:
                assert index==0 and item['redacted_fields']==['payload.manifest.transport.endpoint']
                assert payload['fingerprint']==result['manifest_sha256']
            else:assert digest({k:v for k,v in event.items() if k not in ('seq','event_hash')})==event['event_hash']
            if event['kind']=='step.enqueued':assert digest(payload['request'])==payload['request_hash']
            if event['kind']=='attempt.received':
                assert digest(payload['receipt'])==payload['receipt_hash']
                response=payload['receipt'].get('response',{})
                for choice in response.get('choices',[]):finishes[str(choice.get('finish_reason'))]+=1
                for key in ('prompt_tokens','completion_tokens','total_tokens'):
                    value=(response.get('usage') or {}).get(key)
                    if type(value) is int:usage[key]+=value
            seen[event['event_id']]=event;previous=event['event_hash']
        assert len(events)==result['verification']['events'] and previous==result['verification']['tail_hash']
        assert dict(usage)==result['usage'] and dict(finishes)==result['finish_reasons']
        if result['selection']:
            selected=result['selection'];parent=seen[selected['source_event']]
            assert parent['kind']=='checkpoint.saved' and parent['round_index']==0 and parent['agent_id']=='a00000'
            assert selected['candidate']==parent['payload']['state']['candidate']
            assert selected['selection_seed']==config['selection_seed']
            assert evaluate(result['case']['task_id'],selected['candidate'])==result['verdict']
            observations=[e['payload'] for e in seen.values() if e['kind']=='observation.terminal_evaluation']
            assert observations==[result['verdict']]
        else:assert result['verdict']['status']=='TECHNICAL_FAILURE'
        diagnostic=result['verdict']['status']
        if diagnostic=='TECHNICAL_FAILURE':diagnostic='TRUNCATED_GENERATION' if finishes['length'] else 'TRANSPORT_OR_RUNTIME_FAILURE'
        assert result['diagnostic']==diagnostic
        assert sum(e['kind']=='observation.budget_reserved' for e in seen.values())==result['status']['attempts']
        n+=result['status']['attempts'];tokens.update(usage);verdicts[diagnostic]+=1
    assert dict(tokens)==data['usage'] and dict(verdicts)==data['diagnostic_counts']
    assert tokens['total_tokens']==data['quota']['known_total_tokens'] and n==data['quota']['reserved_calls']
    graph=json.loads((ROOT/'examples/hierarchy-routing-proposal-v1.json').read_text())
    checks={}
    for arm,edges in graph['graphs'].items():
        nodes=graph['nodes'];indegree={v:sum(b==v for a,b in edges) for v in nodes}
        outdegree={v:sum(a==v for a,b in edges) for v in nodes};diameter=0
        assert len(set(map(tuple,edges)))==len(edges) and all(a!=b for a,b in edges)
        for node in nodes:
            distances={node:0};queue=[node]
            for current in queue:
                for a,b in edges:
                    if a==current and b not in distances:
                        distances[b]=distances[a]+1;queue.append(b)
            assert set(distances)==set(nodes);diameter=max(diameter,max(distances.values()))
        checks[arm]={'in_degree':indegree,'out_degree':outdegree,'strongly_connected':True,
                     'diameter':diameter,'edges_per_group':len(edges)}
    assert checks==graph['structural_checks'] and checks['H']==checks['F']
    plan=graph['conditional_first_pilot']
    assert plan['calls_per_population']==plan['logical_agents']*plan['rounds']==32
    assert plan['messages_per_population']==plan['groups']*(plan['rounds']-1)*5==30
    assert plan['live_launch_ready'] is False
    print(json.dumps({'status':'passed','cases':len(runs),'requests':n,'events':sum(map(len,runs.values())),
                      'verdict_counts':dict(verdicts),'first_event_hashes_require_private_original':len(runs)},indent=2))


if __name__=='__main__':main()
