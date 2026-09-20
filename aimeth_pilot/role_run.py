"""Two-stage role-envelope calibration and matched H/F population execution."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import time
from urllib import request

from aimeth_runtime.runner import NoRedirect, demo_manifest
from aimeth_runtime.store import Store, canonical, digest
from aimeth_design.execution import select_terminal
from aimeth_design.organizations import SYSTEM
from aimeth_design.role_routing import compile_roles, messages, finish_role, select_synthesizer
from .calibration import tasks, evaluate
from .role_budget import RoleBudget
from .run import STOP, bounded_response, finish, save

DENIED_HTTP = {401, 403, 404, 429}


def schedule(cfg):
    diagnostics = []
    populations = []
    for model in cfg['models']:
        for task_id in ('integral-rational', 'ns-scaling-algebra-v1'):
            for rep in range(2):
                block = [cfg['seed'], model, task_id, rep]
                for representation in ('minimal-certificate', 'role-envelope'):
                    cell = dict(phase='representation', model=model, task_id=task_id, repetition=rep,
                                representation=representation, seed=int(digest(['sample', block])[:8], 16),
                                selection_seed=int(digest(['selection', block])[:8], 16))
                    cell['case_id'] = 'repr-' + digest(cell)[:24]
                    diagnostics.append(cell)
        for task_id in ('prime-counterexample', 'ns-scaling-algebra-v1'):
            for rep in range(2):
                block = [cfg['seed'], model, task_id, rep]
                for arm in ('H', 'F'):
                    cell = dict(phase='population', model=model, task_id=task_id, repetition=rep,
                                arm=arm, seed=int(digest(['sample', block])[:8], 16),
                                selection_seed=int(digest(['selection', block])[:8], 16))
                    cell['case_id'] = 'hf-' + digest(cell)[:24]
                    cell['block_order'] = digest(['block-order', block])
                    populations.append(cell)
    return (sorted(diagnostics, key=lambda c: digest(['order', cfg['seed'], c['case_id']])),
            sorted(populations, key=lambda c: (c['block_order'], digest(['arm-order', c['case_id']]))))


def manifest(cell, cfg):
    task = tasks()[cell['task_id']]
    if cell['phase'] == 'population':
        config = compile_roles(cell['arm'], task, population=8, rounds=4, seed=cell['seed'],
                               selection_seed=cell['selection_seed'], output_tokens=1024, concurrency=2)
    else:
        config = demo_manifest(1, 1)
        config.update(seed=cell['seed'], selection_seed=cell['selection_seed'],
                      max_attempts=1, max_inflight=1, max_output_tokens=1024, max_message_chars=2048,
                      base_messages=messages(task, 'E0') if cell['representation'] == 'role-envelope' else
                      [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': task['statement']}],
                      context_mode='recorded.v1' if cell['representation'] == 'role-envelope' else 'none.v1',
                      temperature=0.6, top_p=1)
        config['identities'].update(task=task['id']+':sha256:'+digest(task),
                                    policy='role-envelope.v1' if cell['representation']=='role-envelope' else 'minimal-certificate.v1')
    config.update(model_name=cell['model'],
                  transport={'kind': 'openai', 'endpoint': cfg['endpoint'], 'timeout_seconds': 100},
                  request_options={'chat_template_kwargs': {'enable_thinking': False}, 'response_format': {'type': 'json_object'}},
                  role_case=cell, execution_source=cfg['source_commit'])
    config['identities']['model'] = 'served-name:' + cell['model']
    return config


def run_population(root, cell, config, budget, caller=bounded_response):
    rid = cell['case_id']; directory = root/rid; directory.mkdir(exist_ok=True)
    result_path = directory/'result.json'
    started = time.monotonic()
    with Store(directory/'journal.sqlite') as store:
        store.create_run(rid, config)
        budget.reconcile(store, rid)
        if result_path.exists():
            result = json.loads(result_path.read_text())
            assert store.verify(rid) == result['verification']
            if not (directory/'export').exists(): store.export(rid, directory/'export')
            return result
        fatal_http = set()
        role_mode = config['identities']['policy'] == 'role-envelope.v1'
        with ThreadPoolExecutor(max_workers=config['max_inflight']) as pool:
            for round_index in range(config['rounds']):
                store.recover(rid)
                if STOP.is_set() or time.time() >= budget.deadline: break
                if round_index and store.db.execute('SELECT COUNT(*) FROM steps WHERE run_id=? AND round_index=? AND status!=?',
                    (rid, round_index-1, 'succeeded')).fetchone()[0]: break
                store.enqueue_round(rid, round_index)
                active = {}; halted = False
                while True:
                    if STOP.is_set() or time.time() >= budget.deadline: halted = True
                    while not halted and len(active) < config['max_inflight']:
                        claim = store.claim(rid, 'role-supervisor', lease_seconds=150)
                        if claim is None: break
                        size = len(canonical(claim['request']).encode())
                        try: reserved = budget.reserve(claim['token'], rid, config['max_output_tokens'], size)
                        except ValueError:
                            store.fail(claim['token'], {'category': 'admission_budget', 'dispatched': False}, retryable=False)
                            halted = True; break
                        if not reserved: raise ValueError('Reserved attempts cannot be redispatched')
                        parent = store.db.execute('SELECT started_event FROM attempts WHERE token=?', (claim['token'],)).fetchone()[0]
                        store.observe(rid, 'reserved:'+claim['token'], 'observation.budget_reserved',
                                      {'attempt_token': claim['token'], 'output_cap': config['max_output_tokens'],
                                       'input_request_bytes': size, 'hard_input_token_cap': False}, parents=[parent])
                        active[pool.submit(caller, claim, config['transport'], budget.deadline)] = claim
                    done = [future for future in active if future.done()]
                    for future in done:
                        claim = active.pop(future)
                        try: wire = future.result()
                        except Exception as exc: wire = {'error': {'category': type(exc).__name__}}
                        if wire.get('error', {}).get('http_status') in DENIED_HTTP:
                            fatal_http.add(wire['error']['http_status']); halted = True
                        # Journal the full receipt first; reconciliation repairs a later ledger gap.
                        (finish_role if role_mode else finish)(store, claim, config, wire)
                        response = wire.get('response')
                        budget.settle(claim['token'], {'usage': response.get('usage') if isinstance(response, dict) else None,
                                                       'error': wire.get('error')})
                    if not active:
                        if halted: break
                        if done: continue  # Refill pending slots before deciding the round is finished.
                        running = store.db.execute('SELECT COUNT(*) FROM steps WHERE run_id=? AND status=?', (rid, 'running')).fetchone()[0]
                        if not running: break
                        # A restarted coordinator must fence/expire unanswered old attempts, never resend them.
                        store.recover(rid)
                    time.sleep(0.02)
                if halted: break
        status = store.status(rid)
        if status['complete']:
            selected = select_synthesizer(store, rid) if cell['phase']=='population' else select_terminal(store, rid, config['selection_seed'])
            verdict = evaluate(cell['task_id'], selected['candidate'])
            store.observe(rid, 'terminal.evaluation', 'observation.terminal_evaluation', verdict, parents=[selected['source_event']])
        else: selected = None; verdict = {'status': 'TECHNICAL_FAILURE', 'passed': False}
        checkpoints = [json.loads(r[0]) for r in store.db.execute('SELECT state FROM checkpoints WHERE run_id=?', (rid,))]
        received = [e for e in store.events(rid) if e['kind']=='attempt.received']
        fatal_http.update(e['payload']['receipt'].get('error', {}).get('http_status') for e in received
                          if e['payload']['receipt'].get('error', {}).get('http_status') in DENIED_HTTP)
        result = {'case': cell, 'manifest_sha256': digest(config), 'status': status, 'selection': selected,
                  'verdict': verdict, 'verification': store.verify(rid), 'fatal_http': sorted(fatal_http),
                  'valid_envelopes': sum(s.get('envelope_status')=='valid' for s in checkpoints),
                  'malformed_envelopes': sum(s.get('envelope_status')=='malformed' for s in checkpoints),
                  'dispatched_requests': budget.db.execute('SELECT COUNT(*) FROM reservations WHERE run_id=?', (rid,)).fetchone()[0],
                  'elapsed_seconds': time.monotonic()-started}
        save(result_path, result)
        if not (directory/'export').exists(): store.export(rid, directory/'export')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('config', 'local-root', 'output-root'): parser.add_argument('--'+option, required=True)
    args = parser.parse_args(); cfg = json.loads(Path(args.config).read_text())
    root = Path(args.local_root); output = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True); output.mkdir(parents=True, exist_ok=True)
    lock = (root/'coordinator.lock').open('w'); fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (root/'experiment.json').exists():
        if json.loads((root/'experiment.json').read_text()) != cfg: raise ValueError('Experiment changed')
    else: save(root/'experiment.json', cfg)
    if (root/'runtime.json').exists(): metadata = json.loads((root/'runtime.json').read_text())
    else:
        metadata = {'started_at': time.time(), 'deadline': time.time()+2400, 'hostname': socket.gethostname(),
                    'job_id': os.environ.get('SLURM_JOB_ID')}
        save(root/'runtime.json', metadata)
    def stop_handler(signum, frame): STOP.set()
    signal.signal(signal.SIGTERM, stop_handler); signal.signal(signal.SIGINT, stop_handler)
    budgets = {phase: RoleBudget(root/(phase+'-quota.sqlite'), calls=calls, output_tokens=calls*1024,
                               input_bytes=calls*16384, request_bytes=16384, observed_token_stop=token_stop,
                               deadline=metadata['deadline'])
               for phase, calls, token_stop in [('representation', 16, 32768), ('population', 512, 786432)]}
    catalog_url = cfg['endpoint'].removesuffix('/chat/completions')+'/models'
    headers = {'Authorization': 'Bearer '+os.environ['AIMETH_API_KEY']} if os.environ.get('AIMETH_API_KEY') else {}
    with request.build_opener(request.ProxyHandler({}), NoRedirect()).open(request.Request(catalog_url, headers=headers), timeout=10) as response:
        catalog = json.loads(response.read(262144))
    served = {m['id'] for m in catalog.get('data', [])}
    if not set(cfg['models']) <= served: raise ValueError('Frozen model IDs absent from current catalog')
    save(output/'catalog.json', {'served_ids': sorted(served), 'observed_at': time.time()})
    diagnostics, populations = schedule(cfg)
    save(root/'schedule.json', {'representation': diagnostics, 'population': populations})
    results = []; unstarted = []; blocked = set(); gates = {}
    for cell in diagnostics+populations:
        if cell['phase']=='population' and not gates:
            for model in cfg['models']:
                valid = sum(r['case']['model']==model and r['case'].get('representation')=='role-envelope'
                            and r['status']['complete'] and r['valid_envelopes']==1 for r in results)
                gates[model] = {'valid_envelopes': valid, 'planned_envelopes': 4, 'required': 3,
                                'admitted': valid>=3 and model not in blocked}
            save(output/'gates.json', gates)
        reason = ('model_http_stop' if cell['model'] in blocked else
                  'coordinator_stop_or_deadline' if STOP.is_set() or time.time()>=metadata['deadline'] else
                  'envelope_gate_failed' if cell['phase']=='population' and not gates[cell['model']]['admitted'] else None)
        # Reconcile/finalize any existing journal even after a stop or deadline.
        # Otherwise restarting would relabel completed or dispatched units as unstarted.
        if reason and not (root/cell['case_id']/'journal.sqlite').exists():
            unstarted.append({'case': cell, 'reason': reason}); continue
        config = manifest(cell, cfg)
        result = run_population(root, cell, config, budgets[cell['phase']]); results.append(result)
        if result['fatal_http']: blocked.add(cell['model'])
        durable = output/'records'/cell['case_id']
        if not durable.exists():
            durable.parent.mkdir(parents=True, exist_ok=True); shutil.copytree(root/cell['case_id'], durable)
        progress = {'finished_units': len(results), 'planned_units': 32, 'unstarted': unstarted,
                    'gates': gates, 'last': {'case': cell, 'verdict': result['verdict']},
                    'budgets': {k: b.summary() for k, b in budgets.items()}}
        save(output/'progress.json', progress)
        print(json.dumps({'done': len(results), 'phase': cell['phase'], 'model': cell['model'],
                          'arm': cell.get('arm'), 'verdict': result['verdict']['status'],
                          'valid_envelopes': result['valid_envelopes']}), flush=True)
    summary = {'schema_version': '1.0', 'metadata': metadata, 'experiment': cfg, 'results': results,
               'unstarted': unstarted, 'gates': gates, 'planned_representation_cases': 16,
               'planned_populations': 16, 'budgets': {k: b.summary() for k, b in budgets.items()},
               'frontier_proof_verified': False, 'weights_independently_attested': False}
    save(output/'summary-private.json', summary)
    for b in budgets.values(): b.db.close()
    if not (output/'complete-record').exists(): shutil.copytree(root, output/'complete-record')
    print(json.dumps({'finished': True, 'completed_units': len(results), 'unstarted_units': len(unstarted)}), flush=True)


if __name__ == '__main__': main()
