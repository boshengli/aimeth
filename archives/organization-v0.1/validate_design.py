#!/usr/bin/env python3
"""Fresh model-free M2 evidence; never overwrite a prior evidence directory."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import re
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_design.organizations import compile_arm, graph_summary, submission_plan, pilot_schedule
from aimeth_design.execution import dry_run
from aimeth_runtime.store import Store, digest
from aimeth_evaluation.controls import public_tasks, evaluate


def save(path, record):
    with path.open('x') as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    tests = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                           cwd=ROOT, capture_output=True, text=True)
    (output/'unittest.txt').write_text(tests.stdout + tests.stderr)
    if tests.returncode:
        raise SystemExit('Validation failed; evidence retained')
    test_count = int(re.search(r'Ran (\d+) tests', tests.stderr).group(1))
    records = []
    task = public_tasks()[0]
    for arm in ('S', 'I', 'L', 'X'):
        config = compile_arm(arm, task=task)
        save(output/(arm+'.manifest.json'), config)
        started = time.monotonic()
        result = dry_run(output/(arm+'.sqlite'), 'm2-'+arm, config)
        result['wall_seconds'] = round(time.monotonic()-started, 6)
        result['arm'] = arm
        result['graph'] = graph_summary(config)
        result['manifest_sha256'] = digest(config)
        save(output/(arm+'.trace.json'), result)
        records.append(result)
    large = compile_arm('X', population=10000)
    save(output/'X-10000.manifest.json', large)
    plan = submission_plan(large, prompt_token_cap=4096)
    with Store(output/'X-10000-admission.sqlite') as store:
        store.create_run('plan-10000', large)
        plan['manifest_journal_acceptance'] = store.verify('plan-10000')
        plan['executed_steps'] = store.status('plan-10000')['materialized_steps']
    save(output/'plan-10000.json', plan)
    fixtures = {
        'poly-square': ({'coefficients': [1,2,1]}, {'coefficients': [1,1,1]}),
        'poly-difference': ({'coefficients': [-12,5,2]}, {'coefficients': [-12,4,2]}),
        'integral-cubic': ({'coefficients': [0,1,1,1]}, {'coefficients': [1,1,1,1]}),
        'integral-rational': ({'coefficients': [0,0,'-1/2',0,'1/4']}, {'coefficients': [0,0,'-1/2',0,'1/3']}),
        'bezout': ({'a': -9,'b':47}, {'a':9,'b':47}),
        'prime-counterexample': ({'n':40,'d':41}, {'n':0,'d':41}),
    }
    math_checks = []
    for task_id, pair in fixtures.items():
        for kind, certificate in zip(('valid-fixture', 'invalid-fixture'), pair):
            verdict = evaluate(task_id, certificate)
            assert verdict['passed'] == (kind == 'valid-fixture')
            math_checks.append({'task_id': task_id, 'fixture_kind': kind,
                                'certificate_sha256': digest(certificate), 'verdict': verdict})
    schedule = pilot_schedule([task['id'] for task in public_tasks()])
    save(output/'pilot-schedule.json', schedule)
    summary = {
        'schema_version': '1.0', 'scope': 'M2.1 model-free engineering and evaluator validation',
        'python': platform.python_version(), 'sqlite': sqlite3.sqlite_version,
        'platform': platform.platform(),
        'baseline_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        'unit_tests': {'returncode': tests.returncode, 'log_sha256': hashlib.sha256((output/'unittest.txt').read_bytes()).hexdigest(),
                       'count': test_count},
        'trace_runs': records, 'large_plan': plan, 'math_fixture_checks': math_checks,
        'planned_population_runs': schedule['run_count'],
        'actual_model_calls': 0, 'actual_cluster_jobs': 0,
        'organization_effect_estimated': False, 'frontier_proof_verified': False,
        'limitations': ['No model-generated mathematical answers evaluated',
                        'Public algebra controls are evaluator fixtures, not held-out performance',
                        '10K run only compiled and journal-admitted; no 10K inference or routing execution here',
                        'Global token/GPU budget admission and cluster supervision remain unimplemented'],
        'development_corrections': ['Initial integration test failed on verifier valid/status API mismatch; corrected before successful evidence run'],
    }
    save(output/'validation.json', summary)
    print(json.dumps({'status':'passed', 'tests':test_count, 'trace_steps':sum(r['status']['materialized_steps'] for r in records),
                      'trace_messages':sum(r['status']['messages'] for r in records),
                      'math_fixture_checks':len(math_checks), 'model_calls':0}, indent=2))


if __name__ == '__main__':
    main()
