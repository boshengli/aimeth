#!/usr/bin/env python3
"""Replay public request/receipt hashes, event ancestry, selector and verdicts."""
import json
from collections import Counter,defaultdict
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
# Pin the evaluator/compiler used at execution, once the release archive exists.
archive=ROOT/'archives/cluster-pilot-v1'
sys.path.insert(0,str(archive if archive.exists() else ROOT))
from aimeth_runtime.store import digest
from aimeth_design.execution import uniform_index
from aimeth_evaluation.controls import evaluate,public_tasks


def check(directory):
    summary=json.loads((directory/'summary.json').read_text());runs=defaultdict(list)
    for line in (directory/'events.jsonl').read_text().splitlines():
        item=json.loads(line);runs[item['event']['run_id']].append(item)
    assert set(runs)=={r['run_id'] for r in summary['results']}
    counts=Counter();total_usage=Counter()
    tasks={t['id']:t for t in public_tasks()}
    for result in summary['results']:
        envelopes=runs[result['run_id']];previous='0'*64;seen={};kinds=Counter();usage=Counter()
        config=envelopes[0]['event']['payload']['manifest']
        assert config['identities']['task']==result['task_id']+':sha256:'+digest(tasks[result['task_id']])
        for index,item in enumerate(envelopes):
            event=item['event'];payload=event['payload'];kinds[event['kind']]+=1
            assert event['seq']==index+1
            assert event['prev_hash']==previous and set(event['parents'])<=set(seen)
            if item['redacted_fields']:
                assert index==0 and event['kind']=='run.created'
                assert item['redacted_fields']==['payload.manifest.transport.endpoint']
                assert config['transport']['endpoint']=='[INSTITUTIONAL_GATEWAY_REDACTED]'
                assert payload['fingerprint']==result['manifest_sha256']
            else:
                assert digest({k:v for k,v in event.items() if k not in ('seq','event_hash')})==event['event_hash']
            if event['kind']=='step.enqueued':assert digest(payload['request'])==payload['request_hash']
            if event['kind']=='attempt.received':
                assert digest(payload['receipt'])==payload['receipt_hash']
                response=payload['receipt'].get('response',{})
                for key in ('prompt_tokens','completion_tokens','total_tokens'):
                    value=(response.get('usage') or {}).get(key)
                    if type(value) is int:usage[key]+=value
            seen[event['event_id']]=event;previous=event['event_hash']
        assert previous==result['verification']['tail_hash']
        assert len(envelopes)==result['verification']['events']
        assert dict(kinds)==result['event_kinds'] and dict(usage)==result['usage']
        assert kinds['attempt.started']==result['status']['attempts']
        assert kinds['observation.budget_reserved']==kinds['attempt.started']
        if result['selection']:
            selected=result['selection'];names=sorted(config['agents'])
            assert selected['agent_id']==names[uniform_index(config['selection_seed'],config['identities']['task'],len(names))]
            parent=seen[selected['source_event']]
            assert parent['kind']=='checkpoint.saved' and parent['agent_id']==selected['agent_id']
            assert parent['round_index']==config['rounds']-1
            assert parent['payload']['state']['candidate']==selected['candidate']
            observations=[e['payload'] for e in seen.values() if e['kind']=='observation.terminal_selection']
            assert observations==[selected]
            assert evaluate(result['task_id'],selected['candidate'])==result['verdict']
            assert result['status']['complete']
        else:assert result['verdict']['status']=='TECHNICAL_FAILURE'
        counts.update(kinds);total_usage.update(usage)
    assert dict(total_usage)==summary['usage']
    assert counts['attempt.started']==summary['quota']['reserved_calls']
    assert total_usage['total_tokens']==summary['quota']['known_total_tokens']
    assert len(runs)+summary['unstarted_populations']==summary['planned_populations']
    return {'trial':directory.name,'populations':len(runs),'calls':counts['attempt.started'],
            'events':sum(counts.values()),'message_events':counts['message.sent'],
            'exact_verdicts_replayed':sum(bool(r['selection']) for r in summary['results']),
            'first_event_hashes_require_private_original':len(runs)}


if __name__=='__main__':
    directories=[Path(p) for p in sys.argv[1:]] or sorted((ROOT/'reports/cluster-pilot-v1').glob('v[23]'))
    assert directories
    print(json.dumps({'status':'passed','runs':[check(p) for p in directories]},indent=2))
