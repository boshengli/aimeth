"""Descriptive calibration summaries; fixed scores are never repaired."""
from collections import Counter
from aimeth_design.role_routing import parse_envelope
from aimeth_pilot.role_contract import incoming_ids
from role_evidence import envelope_reason


def metrics(events):
    config=events[0]['payload']['manifest'];reserved={};receipts={};usage=Counter();finishes=Counter();reasons=Counter()
    references=0
    for e in events:
        p=e['payload']
        if e['kind']=='observation.budget_reserved': reserved[p['attempt_token']]=p
        if e['kind'] in ('attempt.received','attempt.late_received'):
            receipts[e['attempt_id']]=p
            response=p['receipt'].get('response',{})
            if isinstance(response,dict):
                for choice in response.get('choices',[]): finishes[str(choice.get('finish_reason'))]+=1
            if p['accepted'] and config['contract_case']['phase']=='contract':
                content=response['choices'][0]['message']['content'];ids=incoming_ids(config)
                state,_=parse_envelope(content,ids);reason=envelope_reason(content,ids)
                assert (reason=='valid')==(state['envelope_status']=='valid')
                reasons[reason]+=1
                if reason=='valid':references+=len(state['envelope']['used_messages'])
    unknown=0
    for token in reserved:
        response=receipts.get(token,{}).get('receipt',{}).get('response',{})
        u=response.get('usage') if isinstance(response,dict) else None
        if not isinstance(u,dict) or type(u.get('total_tokens')) is not int or u['total_tokens']<0: unknown+=1
        else:
            for k in ('prompt_tokens','completion_tokens','total_tokens'):
                if type(u.get(k)) is int: usage[k]+=u[k]
    return {'dispatched_requests':len(reserved),'input_request_bytes':sum(r['input_request_bytes'] for r in reserved.values()),
            'reserved_output_tokens':sum(r['output_cap'] for r in reserved.values()),'usage':dict(usage),
            'unknown_usage_attempts':unknown,'finish_reasons':dict(finishes),
            'envelope_diagnostics':dict(reasons),'valid_fixture_references':references}


def valid(row):
    return bool(row['status']['complete'] and row['envelope_status']=='valid')


def aggregate(data):
    results=data['results'];contract=[r for r in results if r['case']['phase']=='contract']
    all_cases=[r['case'] for r in results+data['unstarted'] if r['case']['phase']=='contract']
    groups=[]
    for dimensions in [('model','contract'),('model','contract','role'),('model','contract','context'),
                       ('model','contract','task_id'),('model','contract','role','context')]:
        for key in sorted({tuple(c[d] for d in dimensions) for c in all_cases}):
            rows=[r for r in contract if tuple(r['case'][d] for d in dimensions)==key]
            planned=sum(tuple(c[d] for d in dimensions)==key for c in all_cases)
            groups.append({'dimensions':dict(zip(dimensions,key)),'planned':planned,'started':len(rows),
               'unstarted':planned-len(rows),'format_valid':sum(valid(r) for r in rows),
               'malformed':sum(r['status']['complete'] and not valid(r) for r in rows),
               'technical':sum(not r['status']['complete'] for r in rows),
               'math_passed':sum(r['verdict'].get('passed',False) for r in rows),
               'known_tokens':sum(r['metrics']['usage'].get('total_tokens',0) for r in rows)})
    blocks={}
    for row in contract: blocks.setdefault(row['case']['block_order'],{})[row['case']['contract']]=row
    paired=Counter();complete_pairs=0
    for rows in blocks.values():
        if set(rows)!={'baseline','output-card'}:continue
        a,b=valid(rows['baseline']),valid(rows['output-card']);complete_pairs+=1
        paired['both_valid' if a and b else 'card_only_valid' if b else 'baseline_only_valid' if a else 'neither_valid']+=1
    return {'groups':groups,'executed_pairs':complete_pairs,'paired_format_outcomes':dict(paired),
            'events':sum(r['verification']['events'] for r in results),
            'requests':sum(r['metrics']['dispatched_requests'] for r in results),
            'known_tokens':sum(r['metrics']['usage'].get('total_tokens',0) for r in results),
            'unknown_usage_attempts':sum(r['metrics']['unknown_usage_attempts'] for r in results)}
