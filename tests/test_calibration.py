import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from aimeth_evaluation.pde_scaling import TASK,evaluate
from aimeth_pilot.calibration import schedule,manifest,run_case
from aimeth_pilot.quota import Quota


class CalibrationTests(unittest.TestCase):
    def test_scaling_certificate_and_each_wrong_component(self):
        good={'a':1,'b':2,'c':2,'d':3,'e2':-1,'e3':0}
        self.assertTrue(evaluate(json.dumps(good))['passed'])
        self.assertFalse(evaluate(good)['frontier_proof_verified'])
        for key in good:
            wrong=dict(good);wrong[key]+=1
            self.assertEqual(evaluate(wrong)['status'],'INVALID_CERTIFICATE',key)

    def test_scaling_schema_refuses_prose_duplicates_bools_and_unknown_fields(self):
        for bad in ['A proof by scaling.','{"a":1,"a":2}',{'a':True,'b':2,'c':2,'d':3,'e2':-1,'e3':0},
                    {'a':1,'b':2,'c':2,'d':3,'e2':-1,'e3':0,'proof':'QED'}]:
            self.assertEqual(evaluate(bad)['status'],'MALFORMED')

    def test_factorial_cells_budget_and_block_seeds(self):
        cfg={'models':['m1','m2'],'tasks':['integral-rational','prime-counterexample',TASK['id']],'seed':916}
        cells=schedule(cfg)
        self.assertEqual(cells,schedule(cfg));self.assertEqual(len(cells),48)
        self.assertEqual(len({c['case_id'] for c in cells}),48)
        self.assertEqual(sum(c['max_output_tokens'] for c in cells),61440)
        for model in cfg['models']:
            for task in cfg['tasks']:
                for repeat in range(2):
                    block=[c for c in cells if (c['model'],c['task_id'],c['repetition'])==(model,task,repeat)]
                    self.assertEqual(len(block),4);self.assertEqual(len({c['seed'] for c in block}),1)

    def test_real_receipt_selection_and_evaluation_are_journaled(self):
        cell=schedule({'models':['fixture'],'tasks':[TASK['id']],'seed':916})[0]
        response={'choices':[{'message':{'content':'{"a":1,"b":2,"c":2,"d":3,"e2":-1,"e3":0}'},'finish_reason':'stop'}],
                  'usage':{'prompt_tokens':99,'completion_tokens':25,'total_tokens':124}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);q=Quota(root/'q.sqlite',calls=1,output_tokens=2048,deadline=time.time()+60)
            with patch('aimeth_pilot.calibration.bounded_response',return_value={'response':response}):
                result=run_case(root,cell,'http://127.0.0.1:9/v1/chat/completions',q)
            self.assertTrue(result['verdict']['passed']);self.assertEqual(q.summary()['reserved_calls'],1)
            self.assertEqual(result['verification']['status'],'verified')
            events=[json.loads(l) for l in (root/cell['case_id']/'export/events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(e['kind']=='observation.terminal_evaluation' for e in events),1)
            q.db.close()

    def test_length_limit_retains_raw_receipt_and_never_passes(self):
        cell=schedule({'models':['fixture'],'tasks':[TASK['id']],'seed':916})[0]
        response={'choices':[{'message':{'content':'{"a":1'},'finish_reason':'length'}],
                  'usage':{'prompt_tokens':99,'completion_tokens':512,'total_tokens':611}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);q=Quota(root/'q.sqlite',calls=1,output_tokens=2048,deadline=time.time()+60)
            with patch('aimeth_pilot.calibration.bounded_response',return_value={'response':response}):
                result=run_case(root,cell,'http://127.0.0.1:9/v1/chat/completions',q)
            self.assertIsNone(result['selection']);self.assertEqual(result['verdict']['status'],'TECHNICAL_FAILURE')
            self.assertEqual(q.summary()['known_total_tokens'],611);q.db.close()


if __name__=='__main__':unittest.main()
