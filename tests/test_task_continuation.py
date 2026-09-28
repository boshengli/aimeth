import json
from pathlib import Path
import tempfile
import unittest

from aimeth_pilot.task_continuation import schedule, manifest, execute, freeze_records, REPLACEMENTS
from aimeth_pilot.run import STOP
from aimeth_runtime.store import canonical, Store

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT/'examples/role-contract-contexts-v1.json').read_text())
CFG = {'source_commit':'unit-test','fixture_file_sha256':'fixture',
       'endpoint':'http://127.0.0.1:9/v1/chat/completions'}


class TaskContinuationTests(unittest.TestCase):
    def setUp(self): STOP.clear()

    def test_interrupted_freeze_repaired_and_conflicting_archive_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'experiment.json').write_text(json.dumps(CFG))
            freeze_records(root,CFG,b'frozen-test-source')
            self.assertEqual(json.loads((root/'schedule.json').read_text()),schedule())
            self.assertEqual((root/'submitted-source.tar.gz').read_bytes(),b'frozen-test-source')
            freeze_records(root,CFG,b'frozen-test-source')
            (root/'submitted-source.tar.gz').write_bytes(b'wrong-source')
            with self.assertRaises(ValueError):freeze_records(root,CFG,b'frozen-test-source')

    def test_paired_design_only_replaces_output_sentence(self):
        cases = schedule()
        self.assertEqual(len(cases),16)
        self.assertEqual(len({c['case_id'] for c in cases}),16)
        for a,b in zip(cases[::2],cases[1::2]):
            self.assertEqual(a['block_order'],b['block_order'])
            self.assertEqual(a['seed'],b['seed'])
            configs = {c['contract']:manifest(c,CFG,FIXTURES) for c in (a,b)}
            old = configs['legacy-card']['base_messages']
            new = configs['unified-task-schema']['base_messages']
            before,after = REPLACEMENTS[a['task_id']]
            self.assertEqual(old[:1]+old[2:],new[:1]+new[2:])
            self.assertEqual(old[1]['content'].replace(before,after),new[1]['content'])
            for config in configs.values():
                with tempfile.TemporaryDirectory() as tmp, Store(Path(tmp)/'s.sqlite') as store:
                    store.create_run('test',config);store.enqueue_round('test',0)
                    claim=store.claim('test','test')
                    self.assertLessEqual(len(canonical(claim['request']).encode()),16384)
                    self.assertNotIn('reference_solution',canonical(claim['request']))

    def test_transport_circuit_preserves_unstarted_and_resume_never_calls(self):
        calls=[]
        def wire(claim,transport,deadline):
            model=claim['request']['model'];calls.append(model)
            if model.startswith('deepseek'):
                return {'error':{'category':'http_error','http_status':502}}
            return {'response':{'choices':[{'message':{'content':'{}'},'finish_reason':'stop'}],
                                'usage':{'total_tokens':5}}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            summary=execute(root,CFG,FIXTURES,wire)
            self.assertEqual(calls.count('deepseek-v4-flash-0731'),1)
            self.assertEqual(calls.count('glm-5.3-flash'),8)
            self.assertEqual(len(summary['unstarted']),7)
            self.assertEqual(summary['budget']['unknown_usage_attempts'],1)
            again=execute(root,CFG,FIXTURES,lambda *a: self.fail('redispatched'))
            self.assertEqual(summary,again)
            self.assertFalse(any(r['verdict'].get('passed') for r in summary['results']))


if __name__=='__main__': unittest.main()
