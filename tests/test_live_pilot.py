import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from aimeth_pilot.quota import Quota
from aimeth_runtime.store import Store,validate_manifest
from aimeth_design.organizations import compile_arm
from aimeth_pilot.run import run_population
from aimeth_evaluation.controls import public_tasks

class LivePilotTests(unittest.TestCase):
    def test_options_are_frozen_in_actual_request_and_cannot_override_model(self):
        config=compile_arm('I',population=8,rounds=2,group_size=4)
        config['request_options']={'response_format':{'type':'json_object'}}
        with tempfile.TemporaryDirectory() as tmp:
            with Store(Path(tmp)/'x.sqlite') as store:
                store.create_run('test',config);store.enqueue_round('test',0)
                claim=store.claim('test','w')
                self.assertEqual(claim['request']['response_format'],{'type':'json_object'})
        config['request_options']['model']='other'
        with self.assertRaises(ValueError):validate_manifest(config)

    def test_quota_does_not_refund_failures_or_unknown_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'quota.sqlite'; deadline=time.time()+60
            q=Quota(path,calls=2,output_tokens=200,deadline=deadline)
            self.assertTrue(q.reserve('a','run',100));self.assertFalse(q.reserve('a','run',100))
            q.settle('a',{'usage':None,'error':'timeout'})
            q.reserve('b','run',100)
            with self.assertRaises(ValueError):q.reserve('c','run',1)
            self.assertEqual(q.summary()['unknown_usage_attempts'],2)
            q.db.close()
            reopened=Quota(path,calls=2,output_tokens=200,deadline=deadline)
            self.assertEqual(reopened.summary()['reserved_calls'],2)
            with self.assertRaises(ValueError):reopened.reserve('c','run',1)
            reopened.db.close()

    def test_concurrent_reservations_do_not_overspend(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'quota.sqlite'; deadline=time.time()+60
            Quota(path,calls=2,output_tokens=200,deadline=deadline).db.close()
            def reserve(i):
                q=Quota(path,calls=2,output_tokens=200,deadline=deadline)
                try:q.reserve(str(i),'run',100);return True
                except ValueError:return False
                finally:q.db.close()
            with ThreadPoolExecutor(max_workers=5) as pool:
                self.assertEqual(sum(pool.map(reserve,range(10))),2)

    def test_deadline_and_conflicting_settlement_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            q=Quota(Path(tmp)/'a.sqlite',calls=2,output_tokens=200,deadline=time.time()-1)
            with self.assertRaises(ValueError):q.reserve('x','run',100)
            q.db.close()
            q=Quota(Path(tmp)/'b.sqlite',calls=2,output_tokens=200,deadline=time.time()+60)
            q.reserve('x','run',100);q.settle('x',{'usage':{'total_tokens':4}})
            with self.assertRaises(ValueError):q.settle('x',{'usage':{'total_tokens':5}})
            self.assertEqual(q.summary()['known_total_tokens'],4);q.db.close()

    def test_supervised_population_preserves_actual_response_and_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            config=compile_arm('X',population=8,rounds=2,group_size=4,task=next(t for t in public_tasks() if t['id']=='prime-counterexample'))
            config['max_attempts']=1
            response={'id':'fixture','model':'mock','choices':[{'index':0,'message':{'role':'assistant','content':'{"n":40,"d":41}'},'finish_reason':'stop'}],
                      'usage':{'prompt_tokens':20,'completion_tokens':10,'total_tokens':30}}
            q=Quota(root/'quota.sqlite',calls=16,output_tokens=8192,deadline=time.time()+60)
            with patch('aimeth_pilot.run.bounded_response',return_value={'response':response}):
                result=run_population(root,'run',config,q,'prime-counterexample')
            self.assertTrue(result['status']['complete'])
            self.assertTrue(result['verdict']['passed'])
            self.assertEqual(result['status']['messages'],16)
            self.assertEqual(q.summary()['known_total_tokens'],480)
            self.assertEqual(q.summary()['reserved_calls'],16)
            self.assertTrue((root/'run/export/events.jsonl').exists())
            q.db.close()

    def test_wrong_evaluation_task_is_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); config=compile_arm('I',population=8,rounds=2,group_size=4)
            q=Quota(root/'quota.sqlite',calls=16,output_tokens=8192,deadline=time.time()+60)
            with self.assertRaisesRegex(ValueError,'does not match'):
                run_population(root,'run',config,q,'prime-counterexample')
            self.assertEqual(q.summary()['reserved_calls'],0)
            q.db.close()
