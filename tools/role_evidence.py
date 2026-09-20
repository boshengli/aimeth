"""Shared offline interpretation of frozen role-pilot receipts, never score repair."""
from collections import Counter
import json
from aimeth_runtime.store import canonical
from aimeth_design.role_routing import no_duplicates, parse_envelope


def envelope_reason(content, allowed):
    try:
        if not isinstance(content,str) or len(content.encode())>8192:return 'content_limit'
        obj=json.loads(content,object_pairs_hook=no_duplicates,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')))
        if not isinstance(obj,dict) or set(obj)!={'candidate','justification','objections','used_messages'}:return 'envelope_keys'
        if not isinstance(obj['candidate'],dict) or len(canonical(obj['candidate']))>512:return 'candidate_shape_or_limit'
        if not isinstance(obj['justification'],str) or len(obj['justification'])>512:return 'justification_limit'
        if not isinstance(obj['objections'],list) or len(obj['objections'])>3 or any(not isinstance(x,str) or len(x)>160 for x in obj['objections']):return 'objection_limit'
        used=obj['used_messages']
        if not isinstance(used,list) or len(used)>2 or any(not isinstance(x,str) for x in used) or len(set(used))!=len(used) or not set(used)<=set(allowed):return 'invalid_dependency_reference'
        peer={'envelope':obj,'envelope_status':'valid','proof_verification_status':'unverified'}
        if len(canonical(peer))>2048:return 'combined_envelope_limit'
        return 'valid'
    except (ValueError,TypeError,RecursionError,OverflowError):return 'json_parse'


def metrics(events):
    usage=Counter();finishes=Counter();failures=Counter();reasons=Counter();states={};enqueued={};sent=[]
    active=set();peak=0;reserved=0;request_bytes=0;unknown=0;references=0
    config=events[0]['payload']['manifest'];role_mode=config['identities']['policy']=='role-envelope.v1'
    for e in events:
        p=e['payload']
        if e['kind']=='step.enqueued':enqueued[e['step_id']]=p['request']
        if e['kind']=='attempt.started':active.add(e['attempt_id']);peak=max(peak,len(active))
        if e['kind']=='observation.budget_reserved':reserved+=1;request_bytes+=p['input_request_bytes']
        if e['kind'] in ('attempt.received','attempt.late_received'):
            active.discard(e['attempt_id']);receipt=p['receipt'];response=receipt.get('response',{})
            u=response.get('usage') if isinstance(response,dict) else None
            if not isinstance(u,dict) or type(u.get('total_tokens')) is not int:unknown+=1
            else:
                for key in ('prompt_tokens','completion_tokens','total_tokens'):
                    if type(u.get(key)) is int:usage[key]+=u[key]
            for choice in response.get('choices',[]) if isinstance(response,dict) else []:finishes[str(choice.get('finish_reason'))]+=1
            if p.get('failure'):failures[p['failure']]+=1
            if 'error' in receipt:failures['http_'+str(receipt['error'].get('http_status')) if receipt['error'].get('http_status') else receipt['error'].get('category','unknown')]+=1
            if p['accepted'] and role_mode:
                content=response['choices'][0]['message']['content']
                context=json.loads(enqueued[e['step_id']]['messages'][-1]['content'].split('\n',1)[1])
                allowed=[m['message_id'] for m in context['incoming']]
                reason=envelope_reason(content,allowed);state,_=parse_envelope(content,allowed)
                assert (reason=='valid')==(state['envelope_status']=='valid')
                reasons[reason]+=1
                if reason=='valid':references+=len(state['envelope']['used_messages'])
        if e['kind']=='checkpoint.saved':states[(e['agent_id'],e['round_index'])]=p['state']
        if e['kind']=='message.sent':sent.append(e)
    return {'usage':dict(usage),'finish_reasons':dict(finishes),'failure_labels':dict(failures),
            'accepted_envelope_diagnostics':dict(reasons),'model_reported_valid_references':references,
            'dispatched_requests':reserved,'input_request_bytes':request_bytes,'unknown_usage_attempts':unknown,
            'peak_claimed_attempts':peak,'messages_sent':len(sent),
            'messages_consumed':sum(e['kind']=='message.bound' for e in events if (e['agent_id'],e['round_index']) in states)}
