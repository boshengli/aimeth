"""Bounded task-schema diagnostic through an existing gateway; no GPU allocation."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

from aimeth_pilot.role_budget import RoleBudget
from aimeth_pilot.role_contract import manifest as legacy_manifest, run_case, failure_stop
from aimeth_pilot.run import STOP, bounded_response, save
from aimeth_runtime.store import digest

ROOT = Path(__file__).resolve().parents[1]
MODELS = ('glm-5.3-flash', 'deepseek-v4-flash-0731')
TASKS = ('prime-counterexample', 'ns-scaling-algebra-v1')
REPLACEMENTS = {
    'prime-counterexample': (
        'Return JSON {"n":integer,"d":integer}, where d is a proper divisor of the displayed value.',
        'Put exactly the integer fields n and d inside candidate in the role envelope, '
        'where d is a proper divisor of the displayed value.'),
    'ns-scaling-algebra-v1': (
        'Return only JSON with exactly integer fields a,b,c,d,e2,e3.',
        'Put exactly the integer fields a,b,c,d,e2,e3 inside candidate in the role envelope.'),
}


def schedule():
    cases = []
    for model in MODELS:
        for task_id in TASKS:
            for repetition in range(2):
                block = [2026092801, model, task_id, repetition]
                for contract in ('legacy-card', 'unified-task-schema'):
                    cell = dict(phase='contract', model=model, task_id=task_id, role='E0',
                                context='empty', repetition=repetition, contract=contract,
                                seed=int(digest(['sample', block])[:8], 16),
                                block_order=digest(['block', block]))
                    cell['case_id'] = 'task-schema-' + digest(cell)[:24]
                    cases.append(cell)
    return sorted(cases, key=lambda c: (c['block_order'], digest(['within', c['case_id']])))


def manifest(cell, cfg, fixtures):
    config = legacy_manifest({**cell, 'contract':'output-card'}, cfg, fixtures)
    config['contract_case'] = cell
    config['identities']['policy'] = 'task-schema-diagnostic.v1'
    if cell['contract'] == 'unified-task-schema':
        before, after = REPLACEMENTS[cell['task_id']]
        statement = config['base_messages'][1]['content']
        if statement.count(before) != 1:
            raise ValueError('Task schema source changed')
        config['base_messages'][1]['content'] = statement.replace(before, after)
    config['rendered_task_sha256'] = digest(config['base_messages'][1])
    return config


def execute(root, cfg, fixtures, caller=bounded_response):
    """Resume receipt-first journals with the original deadline and no retries."""
    runtime = root/'runtime.json'
    if not runtime.exists():
        save(runtime, dict(started_at=time.time(), deadline=time.time()+900,
                           execution_mode='local-client-to-existing-institutional-gateway',
                           hostname=socket.gethostname(), slurm_job_id=None))
    meta = json.loads(runtime.read_text())
    budget = RoleBudget(root/'budget.sqlite', calls=16, output_tokens=16384,
                        input_bytes=262144, request_bytes=16384,
                        observed_token_stop=60000, deadline=meta['deadline'])
    results = []; unstarted = []; stopped = set()
    try:
        for cell in schedule():
            reason = None
            if not (root/cell['case_id']/'journal.sqlite').exists():
                if STOP.is_set() or time.time() >= meta['deadline']:
                    reason = 'deadline_or_stop'
                elif cell['model'] in stopped:
                    reason = 'model_transport_circuit_open'
                elif budget.summary()['known_total_tokens'] >= 60000:
                    reason = 'observed_token_stop'
            if reason:
                unstarted.append({'case':cell, 'reason':reason}); continue
            result = run_case(root, cell, manifest(cell, cfg, fixtures), budget, caller)
            results.append(result)
            if failure_stop(result): stopped.add(cell['model'])
            save(root/'progress.json', {'started':len(results), 'planned':16,
                                       'last':result['verdict'], 'budget':budget.summary()})
            print(json.dumps({'completed':len(results), 'model':cell['model'],
                              'contract':cell['contract'], 'verdict':result['verdict']['status']}), flush=True)
        summary = {'schema_version':'1.0', 'scope':'Exploratory paired task-schema diagnostic; not populations',
                   'experiment':cfg, 'metadata':meta, 'results':results, 'unstarted':unstarted,
                   'budget':budget.summary(), 'frontier_proof_verified':False,
                   'population_efficacy_verified':False}
        save(root/'summary-private.json', summary)
        return summary
    finally:
        budget.db.close()


def freeze_records(root, cfg, source_archive):
    """Repair an interrupted prepare, but never replace conflicting evidence."""
    expected = {'experiment.json':cfg, 'schedule.json':schedule(),
                'source-archive.json':{'source_commit':cfg['source_commit'],
                                      'sha256':hashlib.sha256(source_archive).hexdigest(),
                                      'bytes':len(source_archive)}}
    for name,value in expected.items():
        path=root/name
        if path.exists():
            if json.loads(path.read_text()) != value: raise ValueError('Frozen artifact changed: '+name)
        else: save(path,value)
    path=root/'submitted-source.tar.gz'
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected['source-archive.json']['sha256']:
            raise ValueError('Source archive changed')
    else:
        temporary=root/'submitted-source.tar.gz.tmp'
        temporary.write_bytes(source_archive);temporary.replace(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--endpoint', required=True)
    p.add_argument('--source-commit', required=True)
    p.add_argument('--allow-live', action='store_true')
    p.add_argument('--credential-file', type=Path)
    args = p.parse_args()
    head = subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip()
    if head != args.source_commit or subprocess.check_output(['git','diff','HEAD','--name-only'], cwd=ROOT):
        raise ValueError('Use the clean frozen source commit')
    subprocess.run(['git','ls-files','--error-unmatch','aimeth_pilot/task_continuation.py',
                    'docs/task-continuation-v1.md','tests/test_task_continuation.py'],
                   cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    raw = (ROOT/'examples/role-contract-contexts-v1.json').read_bytes()
    cfg = {'protocol':'task-schema-diagnostic.v1', 'models':list(MODELS), 'seed':2026092801,
           'endpoint':args.endpoint, 'source_commit':head,
           'fixture_file_sha256':hashlib.sha256(raw).hexdigest(),
           'protocol_sha256':hashlib.sha256((ROOT/'docs/task-continuation-v1.md').read_bytes()).hexdigest()}
    root = args.root; root.mkdir(parents=True, exist_ok=True)
    with (root/'coordinator.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
        archive=subprocess.check_output(['git','archive','--format=tar.gz',head],cwd=ROOT)
        freeze_records(root,cfg,archive)
        if not args.allow_live:
            print(json.dumps({'prepared':True,'calls_cap':16,'source_commit':head})); return
        if not args.credential_file: raise ValueError('Explicit native credential location required')
        from tools.run_public_sanity import credential
        keys = [s.removeprefix('export ').split('=',1)[0].strip()
                for s in args.credential_file.read_text().splitlines()
                if '=' in s and not s.lstrip().startswith('#')]
        keys = [s for s in keys if s.endswith('API_KEY')]
        if len(keys) != 1: raise ValueError('Ambiguous API key variable')
        os.environ['AIMETH_API_KEY'] = credential(args.credential_file, keys[0])
        signal.signal(signal.SIGTERM, lambda *_:STOP.set())
        signal.signal(signal.SIGINT, lambda *_:STOP.set())
        try: execute(root, cfg, json.loads(raw))
        finally: os.environ.pop('AIMETH_API_KEY', None)


if __name__ == '__main__': main()
