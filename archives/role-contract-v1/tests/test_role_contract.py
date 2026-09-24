import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from aimeth_pilot.role_contract import (MODELS, OUTPUT_CARD, schedule, manifest,
                                      incoming_ids, run_case, failure_stop)
from aimeth_pilot.role_contract import main as contract_main
from aimeth_pilot.role_budget import RoleBudget
from aimeth_pilot.run import STOP
from aimeth_runtime.store import Store, canonical, digest, validate_manifest

ROOT = Path(__file__).resolve().parents[1]
RAW = (ROOT/'examples/role-contract-contexts-v1.json').read_bytes()
FIXTURES = json.loads(RAW)
CFG = {'seed':20260923, 'models':list(MODELS), 'source_commit':'fixture',
       'endpoint':'http://127.0.0.1:9/v1/chat/completions',
       'fixture_file_sha256':hashlib.sha256(RAW).hexdigest()}


def response(content, finish='stop'):
    return {'response':{'choices':[{'message':{'content':content},'finish_reason':finish}],
                        'usage':{'prompt_tokens':4,'completion_tokens':2,'total_tokens':6}}}


class RoleContractTests(unittest.TestCase):
    def setUp(self): STOP.clear()

    def test_frozen_factorial_pairs_and_limits(self):
        probes,cases=schedule(CFG)
        self.assertEqual((len(probes),len(cases)),(2,128))
        self.assertEqual(len({c['case_id'] for c in probes+cases}),130)
        for i in range(0,len(cases),2):
            a,b=cases[i:i+2]
            self.assertEqual(a['block_order'],b['block_order'])
            self.assertEqual(a['seed'],b['seed'])
            self.assertEqual({a['contract'],b['contract']},{'baseline','output-card'})
        for cell in probes+cases:
            cfg=manifest(cell,CFG,FIXTURES);validate_manifest(cfg)
            with tempfile.TemporaryDirectory() as tmp,Store(Path(tmp)/'x.sqlite') as s:
                s.create_run('x',cfg);s.enqueue_round('x',0);request=s.claim('x','test')['request']
                self.assertLessEqual(len(canonical(request).encode()),16384)
        self.assertEqual(sum(manifest(c,CFG,FIXTURES)['max_output_tokens'] for c in probes+cases),131136)

    def test_fixtures_are_exact_previously_recorded_contexts(self):
        path=ROOT/FIXTURES['source_events_file']
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),FIXTURES['source_events_sha256'])
        events={x['event']['event_id']:x['event'] for x in map(json.loads,path.read_text().splitlines())}
        self.assertEqual(len(FIXTURES['fixtures']),16)
        for f in FIXTURES['fixtures'].values():
            e=events[f['source_event_id']]
            self.assertEqual(e['run_id'],f['source_run_id'])
            self.assertEqual(e['payload']['request_hash'],f['source_request_sha256'])
            self.assertEqual(e['payload']['request']['messages'][-1],f['context_message'])
            self.assertEqual(e['round_index'],0 if f['context_kind']=='empty' else 2)

    def test_treatment_only_appends_card_no_changed_task_or_peer_values(self):
        cell=schedule(CFG)[1][0];a=manifest({**cell,'contract':'baseline'},CFG,FIXTURES)
        b=manifest({**cell,'contract':'output-card'},CFG,FIXTURES)
        self.assertEqual(a['base_messages'],b['base_messages'][:-1])
        self.assertEqual(b['base_messages'][-1],{'role':'user','content':OUTPUT_CARD})
        self.assertEqual(a['frozen_context_fixture'],b['frozen_context_fixture'])
        self.assertEqual(a['identities']['task'],b['identities']['task'])

    def exercise(self, wire, *, crash=False, phase='contract'):
        cells=schedule(CFG)[0 if phase=='availability' else 1]
        cell=next(c for c in cells if phase=='availability' or (c['task_id']=='prime-counterexample' and c['context']=='recorded'))
        cfg=manifest(cell,CFG,FIXTURES)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);budget=RoleBudget(root/'budget.sqlite',calls=1,output_tokens=1024,
                input_bytes=16384,request_bytes=16384,observed_token_stop=100,deadline=time.time()+60)
            if crash:
                with patch.object(budget,'settle',side_effect=RuntimeError('after receipt')):
                    with self.assertRaises(RuntimeError):run_case(root,cell,cfg,budget,lambda *args:wire(cfg))
                self.assertEqual(budget.summary()['unknown_usage_attempts'],1)
            result=run_case(root,cell,cfg,budget,lambda *args:wire(cfg))
            again=run_case(root,cell,cfg,budget,lambda *args:(_ for _ in ()).throw(AssertionError('redispatched')))
            self.assertEqual(result,again)
            self.assertEqual(budget.summary()['reserved_calls'],1)
            with Store(root/cell['case_id']/'journal.sqlite') as store:
                self.assertEqual(store.verify(cell['case_id']),result['verification'])
                self.assertFalse(any(e['kind']=='message.sent' for e in store.events(cell['case_id'])))
            accounting=budget.summary();budget.db.close()
        return result,accounting

    def test_valid_fixture_reference_and_receipt_recovery(self):
        def wire(cfg):
            return response(canonical({'candidate':{'n':40,'d':41},'justification':'check',
                         'objections':[],'used_messages':incoming_ids(cfg)[:1]}))
        result,budget=self.exercise(wire,crash=True)
        self.assertEqual(result['envelope_status'],'valid')
        self.assertTrue(result['verdict']['passed'])
        self.assertEqual(budget['known_total_tokens'],6)
        self.assertEqual(budget['unknown_usage_attempts'],0)

    def test_invalid_reference_and_bare_certificate_are_not_repaired(self):
        for content in [canonical({'n':40,'d':41}),canonical({'candidate':{'n':40,'d':41},
                         'justification':'check','objections':[],'used_messages':['invented']})]:
            result,_=self.exercise(lambda cfg:response(content))
            self.assertEqual(result['envelope_status'],'malformed')
            self.assertFalse(result['verdict']['passed'])
            self.assertIsNone(result['selection']['candidate'])

    def test_length_does_not_open_transport_circuit(self):
        result,budget=self.exercise(lambda cfg:response('{','length'))
        self.assertFalse(result['status']['complete'])
        self.assertFalse(failure_stop(result))
        self.assertEqual(budget['known_total_tokens'],6)

    def test_transport_opens_circuit_and_unknown_usage_remains(self):
        result,budget=self.exercise(lambda cfg:{'error':{'category':'http_error','http_status':502}})
        self.assertTrue(failure_stop(result));self.assertEqual(budget['unknown_usage_attempts'],1)
        self.assertIsNone(result['selection'])

    def test_availability_is_complete_response_not_math_or_json_gate(self):
        result,_=self.exercise(lambda cfg:response('operational'),phase='availability')
        self.assertEqual(result['verdict'],{'status':'AVAILABLE','mathematical_evaluation':False})

    def test_driver_retains_all_unstarted_and_does_not_call_failed_model(self):
        called=[]
        def fake(root,cell,cfg,budget):
            called.append(cell)
            directory=root/cell['case_id'];directory.mkdir()
            result={'case':cell,'status':{'complete':False},'verdict':{'status':'TECHNICAL_FAILURE'},
                    'errors':[{'category':'http_error','http_status':502}],
                    'dispatched_requests':1,'envelope_status':None}
            (directory/'result.json').write_text(json.dumps(result))
            return result
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg_path=root/'config.json';cfg_path.write_text(json.dumps(CFG))
            args=['contract','--config',str(cfg_path),'--fixtures',str(ROOT/'examples/role-contract-contexts-v1.json'),
                  '--local-root',str(root/'local'),'--output-root',str(root/'out')]
            with patch('sys.argv',args),patch('aimeth_pilot.role_contract.run_case',side_effect=fake),patch('builtins.print'):
                contract_main()
            summary=json.loads((root/'out/summary-private.json').read_text())
            self.assertEqual(len(called),2)
            self.assertTrue(all(c['phase']=='availability' for c in called))
            self.assertEqual(len(summary['unstarted']),128)
            self.assertTrue(all(c['reason']=='availability_gate_failed' for c in summary['unstarted']))
            self.assertTrue(all(not x['ready_for_bounded_multiround_contract_check'] for x in summary['readiness'].values()))


if __name__=='__main__':unittest.main()
