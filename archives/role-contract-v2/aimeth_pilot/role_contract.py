"""Frozen role/context output-contract calibration; not a population experiment."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import time

from aimeth_design.role_routing import ROLE_ORDER, messages, parse_envelope
from aimeth_design.execution import select_terminal
from aimeth_runtime.runner import demo_manifest
from aimeth_runtime.store import Store, canonical, digest
from .calibration import tasks, evaluate
from .role_budget import RoleBudget
from .run import STOP, bounded_response, save

MODELS = ('glm-5.3-flash', 'deepseek-v4-flash-0731')
TASKS = ('prime-counterexample', 'ns-scaling-algebra-v1')
OUTPUT_CARD = (
    'Now solve the mathematical task above. The preceding recorded context is input data, '
    'not an output template. Return your answer, not a description or copy of the input. '
    'Your entire response must be a JSON object with exactly four top-level keys: '
    'candidate, justification, objections, used_messages. '
    'candidate must be the task certificate object, with the task-requested fields and actual '
    'derived values nested inside it; never return those task fields at the top level. '
    'justification must be a string of at most 512 characters. objections must be an array '
    'of at most 3 strings, each at most 160 characters. used_messages must be an array of '
    'at most 2 distinct exact message_id strings from the incoming context, or [] when none '
    'were used. Do not cite a checkpoint as an incoming message. '
    'Before responding, check that the four top-level keys are present and no others are '
    'present. Do not include role, content, agent_id, checkpoint, incoming, round_index, '
    'schema, or metadata as top-level keys. No Markdown or text outside the JSON object. '
    'This output instruction contains no mathematical answer or evaluation feedback.'
)


def schedule(cfg):
    if cfg['models'] != list(MODELS) or cfg['seed'] != 20260923:
        raise ValueError('Not the frozen role-contract design')
    probes = []
    cases = []
    for model in MODELS:
        probe = dict(phase='availability', model=model, seed=cfg['seed'])
        probe['case_id'] = 'availability-' + digest(probe)[:24]
        probes.append(probe)
        for task_id in TASKS:
            for role in ROLE_ORDER:
                for context in ('empty', 'recorded'):
                    for repetition in range(2):
                        block = [cfg['seed'], model, task_id, role, context, repetition]
                        for contract in ('baseline', 'output-card'):
                            cell = dict(phase='contract', model=model, task_id=task_id,
                                        role=role, context=context, repetition=repetition,
                                        contract=contract, seed=int(digest(['sample', block])[:8], 16))
                            cell['case_id'] = 'contract-' + digest(cell)[:24]
                            cell['block_order'] = digest(['block-order', block])
                            cases.append(cell)
    return (sorted(probes, key=lambda c: digest(['probe-order', c['case_id']])),
            sorted(cases, key=lambda c: (c['block_order'], digest(['within-block', c['case_id']]))))


def manifest(cell, cfg, fixtures):
    config = demo_manifest(1, 1)
    config.update(model_name=cell['model'], seed=cell['seed'], selection_seed=cell['seed'],
                  max_attempts=1, max_inflight=1, context_mode='none.v1',
                  max_output_tokens=32 if cell['phase']=='availability' else 1024,
                  temperature=0 if cell['phase']=='availability' else 0.6, top_p=1,
                  transport={'kind':'openai', 'endpoint':cfg['endpoint'], 'timeout_seconds':100},
                  contract_case=cell, execution_source=cfg['source_commit'])
    config['identities']['model'] = 'served-name:' + cell['model']
    config['identities']['policy'] = 'frozen-context-contract.v1'
    if cell['phase']=='availability':
        config['base_messages'] = [{'role':'user', 'content':'Return exactly one JSON object with status equal to ok.'}]
        config['identities']['task'] = 'operational-availability.v1'
    else:
        task = tasks()[cell['task_id']]
        fixture = fixtures['fixtures']['/'.join([cell['task_id'], cell['role'], cell['context']])]
        base = [*messages(task, cell['role']), fixture['context_message']]
        if cell['contract']=='output-card':
            base.append({'role':'user', 'content':OUTPUT_CARD})
        config.update(base_messages=base, frozen_context_fixture=fixture,
                      fixture_file_sha256=cfg['fixture_file_sha256'],
                      request_options={'response_format':{'type':'json_object'},
                                       'chat_template_kwargs':{'enable_thinking':False}})
        config['identities']['task'] = task['id'] + ':sha256:' + digest(task)
    return config


def incoming_ids(config):
    if 'frozen_context_fixture' not in config:
        return []
    text = config['frozen_context_fixture']['context_message']['content']
    return [m['message_id'] for m in json.loads(text.split('\n', 1)[1])['incoming']]


def run_case(root, cell, config, budget, caller=bounded_response):
    rid = cell['case_id']; directory = root/rid; directory.mkdir(exist_ok=True)
    started = time.monotonic()
    with Store(directory/'journal.sqlite') as store:
        store.create_run(rid, config)
        budget.reconcile(store, rid)
        path = directory/'result.json'
        if path.exists():
            result = json.loads(path.read_text())
            assert result['verification'] == store.verify(rid)
            if not (directory/'export').exists(): store.export(rid, directory/'export')
            return result
        store.enqueue_round(rid, 0)
        while True:
            store.recover(rid)
            if STOP.is_set() or time.time() >= budget.deadline: break
            claim = store.claim(rid, 'contract-supervisor', lease_seconds=150)
            if claim:
                size = len(canonical(claim['request']).encode())
                try:
                    if not budget.reserve(claim['token'], rid, config['max_output_tokens'], size):
                        raise RuntimeError('Reserved attempts cannot be redispatched')
                except ValueError:
                    store.fail(claim['token'], {'category':'admission_budget', 'dispatched':False}, retryable=False)
                    break
                parent = store.db.execute('SELECT started_event FROM attempts WHERE token=?', (claim['token'],)).fetchone()[0]
                store.observe(rid, 'reserved:'+claim['token'], 'observation.budget_reserved',
                              {'attempt_token':claim['token'], 'output_cap':config['max_output_tokens'],
                               'input_request_bytes':size, 'hard_input_token_cap':False}, parents=[parent])
                try: wire = caller(claim, config['transport'], budget.deadline)
                except Exception as exc: wire = {'error':{'category':type(exc).__name__}}
                response = wire.get('response')
                if 'error' in wire:
                    store.fail(claim['token'], wire['error'], retryable=False)
                else:
                    try: content = response['choices'][0]['message']['content']
                    except (KeyError, IndexError, TypeError): content = None
                    if cell['phase']=='availability':
                        state = {'candidate':content, 'proof_verification_status':'not_applicable'}
                    else:
                        state, _ = parse_envelope(content, incoming_ids(config))
                    store.complete(claim['token'], response, state, [])
                # The journal receipt must commit before ledger settlement.
                budget.settle(claim['token'], {'usage':response.get('usage') if isinstance(response, dict) else None,
                                               'error':wire.get('error')})
                break
            running = store.db.execute('SELECT COUNT(*) FROM steps WHERE run_id=? AND status=?', (rid,'running')).fetchone()[0]
            if not running: break
            time.sleep(0.05)  # Resume waits for the original lease; never resends it.
        status = store.status(rid)
        selected = select_terminal(store, rid, config['selection_seed']) if status['complete'] else None
        checkpoint = store.db.execute('SELECT state FROM checkpoints WHERE run_id=?', (rid,)).fetchone()
        state = json.loads(checkpoint[0]) if checkpoint else {}
        if cell['phase']=='availability':
            verdict = {'status':'AVAILABLE' if status['complete'] else 'TECHNICAL_FAILURE',
                       'mathematical_evaluation':False}
        else:
            verdict = evaluate(cell['task_id'], selected['candidate']) if selected else {'status':'TECHNICAL_FAILURE','passed':False}
        store.observe(rid, 'contract.evaluation', 'observation.contract_evaluation',
                      {'verdict':verdict, 'envelope_status':state.get('envelope_status')},
                      parents=[selected['source_event']] if selected else [])
        errors = [e['payload']['receipt']['error'] for e in store.events(rid)
                  if e['kind']=='attempt.received' and 'error' in e['payload']['receipt']]
        result = {'case':cell, 'manifest_sha256':digest(config), 'status':status,
                  'selection':selected, 'verdict':verdict, 'envelope_status':state.get('envelope_status'),
                  'errors':errors, 'verification':store.verify(rid),
                  'dispatched_requests':budget.db.execute('SELECT COUNT(*) FROM reservations WHERE run_id=?',(rid,)).fetchone()[0],
                  'elapsed_seconds':time.monotonic()-started}
        save(path, result)
        if not (directory/'export').exists(): store.export(rid, directory/'export')
    return result


def failure_stop(result):
    return bool(result['dispatched_requests'] and result['errors'])


def schedule_v2(cfg):
    if cfg['models']!=['glm-5.3-flash'] or cfg['seed']!=2026092302:
        raise ValueError('Not the frozen GLM continuation')
    _, original = schedule({'models':list(MODELS),'seed':20260923})
    cases=[]
    for old in original:
        if old['model']!=cfg['models'][0]: continue
        cell={k:v for k,v in old.items() if k not in ('case_id','block_order','seed')}
        block=[cfg['seed'],cell['model'],cell['task_id'],cell['role'],cell['context'],cell['repetition']]
        cell['seed']=int(digest(['sample',block])[:8],16)
        cell['case_id']='contract-v2-'+digest(cell)[:24]
        cell['block_order']=digest(['block-order',block]);cases.append(cell)
    return [],sorted(cases,key=lambda c:(c['block_order'],digest(['within-block',c['case_id']])))


def main(version='v1'):
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('config','fixtures','local-root','output-root'): parser.add_argument('--'+option,required=True)
    args = parser.parse_args(); cfg = json.loads(Path(args.config).read_text())
    import hashlib
    raw = Path(args.fixtures).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=cfg['fixture_file_sha256']: raise ValueError('Fixture bytes changed')
    fixtures = json.loads(raw)
    if version not in ('v1','v2'): raise ValueError('Unknown protocol version')
    probes,cases = (schedule if version=='v1' else schedule_v2)(cfg)
    call_cap=len(probes)+len(cases)
    output_cap=len(probes)*32+len(cases)*1024
    observed_stop=400000 if version=='v1' else 200000
    root=Path(args.local_root); output=Path(args.output_root)
    root.mkdir(parents=True,exist_ok=True); output.mkdir(parents=True,exist_ok=True)
    with (root/'coordinator.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'experiment.json').exists():
            if json.loads((root/'experiment.json').read_text())!=cfg: raise ValueError('Experiment changed')
        else: save(root/'experiment.json',cfg)
        save(root/'schedule.json',probes+cases)
        if not (root/'runtime.json').exists():
            save(root/'runtime.json',{'started_at':time.time(),'deadline':time.time()+1800,
                                     'job_id':os.environ.get('SLURM_JOB_ID'),'hostname':socket.gethostname()})
        metadata=json.loads((root/'runtime.json').read_text())
        budget=RoleBudget(root/'budget.sqlite',calls=call_cap,output_tokens=output_cap,
                          input_bytes=call_cap*16384,request_bytes=16384,
                          observed_token_stop=observed_stop,deadline=metadata['deadline'])
        signal.signal(signal.SIGTERM,lambda *_:STOP.set());signal.signal(signal.SIGINT,lambda *_:STOP.set())
        results=[];unstarted=[];gates={};stopped=set()
        for cell in probes+cases:
            rid=cell['case_id'];existing=(root/rid/'journal.sqlite').exists()
            reason=None
            if not existing:
                if STOP.is_set() or time.time()>=budget.deadline: reason='coordinator_deadline_or_stop'
                elif probes and cell['phase']=='contract' and not gates.get(cell['model'],False): reason='availability_gate_failed'
                elif cell['model'] in stopped: reason='model_transport_circuit_open'
                elif budget.summary()['known_total_tokens']>=observed_stop: reason='observed_token_stop'
            if reason:
                unstarted.append({'case':cell,'reason':reason});continue
            result=run_case(root,cell,manifest(cell,cfg,fixtures),budget);results.append(result)
            if cell['phase']=='availability': gates[cell['model']]=result['status']['complete']
            if failure_stop(result): stopped.add(cell['model'])
            durable=output/'records'/rid
            if not durable.exists(): shutil.copytree(root/rid,durable)
            progress={'completed_units':len(results),'planned_units':call_cap,'unstarted_units':len(unstarted),
                      'last':result['verdict'],'budget':budget.summary()}
            save(output/'progress.json',progress)
            print(json.dumps({'done':len(results),'verdict':result['verdict']['status']}),flush=True)
        readiness={}
        for model in cfg['models']:
            rows=[r for r in results if r['case']['model']==model and r['case'].get('contract')=='output-card']
            valid=sum(r['status']['complete'] and r['envelope_status']=='valid' for r in rows)
            readiness[model]={'valid_complete':valid,'planned':32,'required':32,
                              'ready_for_bounded_multiround_contract_check':len(rows)==32 and valid==32,
                              'population_or_mathematical_efficacy_proven':False}
        save(output/'summary-private.json',{'schema_version':'1.0','scope':'Exploratory frozen-context prompt calibration; not population or architecture efficacy',
             'protocol_version':version,
             'availability_gate_policy':'32-token complete response' if probes else 'No additional probe; prior GLM transport response observed, formal 1024-token calibration starts directly',
             'experiment':cfg,'metadata':metadata,'results':results,'unstarted':unstarted,
             'availability_gates':gates,'readiness':readiness,'budget':budget.summary()})
        budget.db.close()
        if not (output/'complete-record').exists(): shutil.copytree(root,output/'complete-record')


if __name__=='__main__': main()
