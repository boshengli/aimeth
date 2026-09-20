import copy
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from io import StringIO

from aimeth_runtime.store import Store, Conflict, canonical, validate_manifest
from aimeth_design.role_routing import compile_roles, parse_envelope, finish_role, select_synthesizer
from aimeth_pilot.calibration import tasks
from aimeth_pilot.role_budget import RoleBudget
from aimeth_pilot.role_run import schedule, manifest, run_population
from aimeth_pilot.role_run import main as run_main
from aimeth_pilot.run import STOP

CFG = {'seed': 20260920, 'models': ['m1','m2'], 'source_commit': 'fixture',
       'endpoint': 'http://127.0.0.1:9/v1/chat/completions'}


def fixture(claim, transport=None, deadline=None):
    context = json.loads(claim['request']['messages'][-1]['content'].split('\n',1)[1])
    obj = {'candidate': {'n':40,'d':41}, 'justification':'41 divides the polynomial at n=40.',
           'objections':[], 'used_messages':[m['message_id'] for m in context['incoming']]}
    return {'response': {'choices':[{'message':{'content':canonical(obj)}, 'finish_reason':'stop'}],
                          'usage':{'prompt_tokens':9,'completion_tokens':1,'total_tokens':10}}}


def budget(root, calls=32, deadline=None):
    return RoleBudget(root/'budget.sqlite', calls=calls, output_tokens=calls*1024,
                      input_bytes=calls*16384, request_bytes=16384, observed_token_stop=999999,
                      deadline=deadline or time.time()+60)


class RoleRoutingTests(unittest.TestCase):
    def setUp(self): STOP.clear()

    def test_matched_roles_prompts_degrees_and_terminal_pool(self):
        task=tasks()['prime-counterexample'];h=compile_roles('H',task);f=compile_roles('F',task)
        self.assertEqual(h['agent_base_messages'],f['agent_base_messages'])
        self.assertEqual(h['organization']['terminal_agents'],f['organization']['terminal_agents'])
        for cfg in (h,f):
            self.assertEqual(sum(map(len,cfg['round_edges'].values())),30)
            self.assertEqual(len(cfg['agents'])*cfg['rounds'],32)
            for a in cfg['agents']:
                role=cfg['organization']['roles'][a]
                self.assertIn('Role:',cfg['agent_base_messages'][a][0]['content'])
                for direction in (0,1):
                    self.assertEqual(sum(e[direction]==a for e in h['round_edges']['0']),
                                     sum(e[direction]==a for e in f['round_edges']['0']))
                self.assertEqual(a in cfg['organization']['terminal_agents'],role=='S')

    def test_strict_envelope_references_schema_and_combined_bound(self):
        valid={'candidate':{'n':40,'d':41},'justification':'check','objections':[], 'used_messages':['incoming']}
        state,peer=parse_envelope(json.dumps(valid),['incoming'])
        self.assertEqual(state['envelope_status'],'valid');self.assertEqual(peer['envelope'],valid)
        bads=['```json\n'+json.dumps(valid)+'\n```','{"candidate":{},"candidate":{}}',
              json.dumps({**valid,'extra':1}),json.dumps({**valid,'used_messages':['invented']}),
              json.dumps({**valid,'used_messages':['incoming','incoming']}),
              json.dumps({**valid,'candidate':'{"n":40}'}),json.dumps({**valid,'justification':'x'*513}),
              json.dumps({**valid,'objections':['x'*161]}),json.dumps({**valid,'candidate':{'n':float('nan')}})]
        for bad in bads:
            state,peer=parse_envelope(bad,['incoming'])
            self.assertEqual(state['envelope_status'],'malformed');self.assertIsNone(state['candidate'])

    def test_context_omission_is_explicit_and_restricted(self):
        cell=next(c for c in schedule(CFG)[0] if c['representation']=='minimal-certificate')
        config=manifest(cell,CFG)
        with tempfile.TemporaryDirectory() as tmp, Store(Path(tmp)/'x.sqlite') as store:
            store.create_run('x',config);store.enqueue_round('x',0);claim=store.claim('x','test')
            self.assertEqual(claim['request']['messages'],config['base_messages'])
        config['rounds']=2
        with self.assertRaises(ValueError):validate_manifest(config)

    def test_per_agent_requests_bind_critic_and_synthesizer(self):
        config=compile_roles('H',tasks()['prime-counterexample'])
        with tempfile.TemporaryDirectory() as tmp,Store(Path(tmp)/'x.sqlite') as store:
            store.create_run('x',config);store.enqueue_round('x',0)
            for row in store.db.execute('SELECT agent_id,request FROM steps'):
                self.assertEqual(json.loads(row['request'])['messages'][:-1],config['agent_base_messages'][row['agent_id']])
        broken=copy.deepcopy(config);broken['agent_base_messages'].pop(config['agents'][0])
        with self.assertRaises(ValueError):validate_manifest(broken)

    def test_full_population_messages_selection_and_idempotent_resume(self):
        cell=next(c for c in schedule(CFG)[1] if c['arm']=='H' and c['task_id']=='prime-counterexample')
        config=manifest(cell,CFG);calls=[]
        def call(*args):calls.append(args[0]['step_id']);return fixture(*args)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);q=budget(root)
            result=run_population(root,cell,config,q,caller=call)
            self.assertTrue(result['verdict']['passed']);self.assertEqual(result['valid_envelopes'],32)
            self.assertEqual(result['status']['messages'],30);self.assertEqual(len(calls),32)
            self.assertIn(result['selection']['agent_id'],config['organization']['terminal_agents'])
            again=run_population(root,cell,config,q,caller=call)
            self.assertEqual(again,result);self.assertEqual(len(calls),32)
            with Store(root/cell['case_id']/'journal.sqlite') as store:
                self.assertEqual(store.verify(cell['case_id'])['status'],'verified')
                self.assertEqual(store.db.execute('SELECT COUNT(*) FROM messages WHERE consumed_event IS NOT NULL').fetchone()[0],30)
                self.assertEqual(select_synthesizer(store,cell['case_id']),result['selection'])
            q.db.close()

    def test_invalid_envelope_is_preserved_and_round_can_continue(self):
        cell=next(c for c in schedule(CFG)[1] if c['task_id']=='prime-counterexample')
        config=manifest(cell,CFG)
        def invalid(claim,*args):
            wire=fixture(claim);wire['response']['choices'][0]['message']['content']='{"candidate":{"n":40,"d":41}}'
            return wire
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);q=budget(root)
            result=run_population(root,cell,config,q,caller=invalid)
            self.assertTrue(result['status']['complete']);self.assertEqual(result['malformed_envelopes'],32)
            self.assertEqual(result['verdict']['status'],'MALFORMED');self.assertEqual(result['status']['messages'],30)
            self.assertEqual(q.summary()['reserved_calls'],32);q.db.close()

    def test_round_boundary_restart_preserves_checkpoints_and_budget(self):
        cell=next(c for c in schedule(CFG)[1] if c['task_id']=='prime-counterexample')
        config=manifest(cell,CFG);rid=cell['case_id']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=root/rid;directory.mkdir();q=budget(root)
            with Store(directory/'journal.sqlite') as store:
                store.create_run(rid,config)
                for r in range(2):
                    store.enqueue_round(rid,r)
                    while True:
                        claim=store.claim(rid,'before-restart')
                        if not claim:break
                        q.reserve(claim['token'],rid,1024,len(canonical(claim['request']).encode()))
                        finish_role(store,claim,config,fixture(claim))
                        q.reconcile(store,rid)
            calls=[]
            def call(*args):calls.append(args[0]['step_id']);return fixture(*args)
            result=run_population(root,cell,config,q,caller=call)
            self.assertTrue(result['verdict']['passed']);self.assertEqual(len(calls),16)
            self.assertEqual(q.summary()['reserved_calls'],32);q.db.close()

    def test_receipt_before_ledger_crash_reconciles_without_new_call(self):
        cell=next(c for c in schedule(CFG)[0] if c['representation']=='role-envelope')
        config=manifest(cell,CFG);rid=cell['case_id']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=root/rid;directory.mkdir();q=budget(root,calls=1)
            with Store(directory/'journal.sqlite') as store:
                store.create_run(rid,config);store.enqueue_round(rid,0);claim=store.claim(rid,'crash-fixture')
                q.reserve(claim['token'],rid,1024,len(canonical(claim['request']).encode()))
                finish_role(store,claim,config,fixture(claim))
            self.assertEqual(q.summary()['unknown_usage_attempts'],1)
            def forbidden(*_):raise AssertionError('Already committed call was repeated')
            result=run_population(root,cell,config,q,caller=forbidden)
            self.assertTrue(result['status']['complete']);self.assertEqual(q.summary()['known_total_tokens'],10)
            self.assertEqual(q.summary()['unknown_usage_attempts'],0);q.db.close()

    def test_unauthorized_route_and_length_are_not_accepted(self):
        config=compile_roles('H',tasks()['prime-counterexample'])
        with tempfile.TemporaryDirectory() as tmp,Store(Path(tmp)/'x.sqlite') as store:
            store.create_run('x',config);store.enqueue_round('x',0);claim=store.claim('x','test')
            targets={b for a,b in config['round_edges']['0'] if a==claim['agent_id']}
            wrong=next(a for a in config['agents'] if a!=claim['agent_id'] and a not in targets)
            result=store.complete(claim['token'],fixture(claim)['response'],{'candidate':'{}'},
                                  [{'recipient':wrong,'target_round':1,'content':{}}])
            self.assertFalse(result['accepted']);self.assertEqual(store.status('x')['messages'],0)
            claim=store.claim('x','test');wire=fixture(claim);wire['response']['choices'][0]['finish_reason']='length'
            result=finish_role(store,claim,config,wire)
            self.assertFalse(result['accepted']);self.assertEqual(store.status('x')['messages'],0)

    def test_schedule_preserves_paired_randomization_and_denominators(self):
        a,b=schedule(CFG);self.assertEqual((len(a),len(b)),(16,16))
        self.assertEqual(len({x['case_id'] for x in a+b}),32)
        for cell in b:
            paired=[x for x in b if (x['model'],x['task_id'],x['repetition'])==(cell['model'],cell['task_id'],cell['repetition'])]
            self.assertEqual({x['arm'] for x in paired},{'H','F'});self.assertEqual(len({x['seed'] for x in paired}),1)
            self.assertEqual(len({x['selection_seed'] for x in paired}),1)

    def test_byte_output_and_call_caps_are_atomic_and_unknown_not_refunded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);q=RoleBudget(root/'q.sqlite',calls=2,output_tokens=10,input_bytes=20,request_bytes=15,observed_token_stop=30,deadline=time.time()+60)
            self.assertTrue(q.reserve('first','r',5,12));self.assertFalse(q.reserve('first','r',5,12))
            for args in [('second','r',6,1),('second','r',5,9),('second','r',1,16)]:
                with self.assertRaises(ValueError):q.reserve(*args)
            self.assertTrue(q.reserve('second','r',5,8))
            with self.assertRaises(ValueError):q.reserve('third','r',1,1)
            self.assertEqual(q.summary()['unknown_usage_attempts'],2)
            self.assertEqual(q.summary()['reserved_input_bytes'],20)
            self.assertFalse(q.summary()['hard_input_token_cap']);q.db.close()

    def test_usage_stop_conflicting_settlement_and_changed_quota_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);deadline=time.time()+60
            q=RoleBudget(root/'q.sqlite',calls=10,output_tokens=100,input_bytes=100,request_bytes=20,observed_token_stop=10,deadline=deadline)
            q.reserve('a','r',1,5);q.settle('a',{'usage':{'total_tokens':12},'error':None})
            with self.assertRaises(ValueError):q.reserve('b','r',1,5)
            with self.assertRaises(ValueError):q.settle('a',{'usage':{'total_tokens':13}})
            q.db.close()
            with self.assertRaises(ValueError):RoleBudget(root/'q.sqlite',calls=11,output_tokens=100,input_bytes=100,request_bytes=20,observed_token_stop=10,deadline=deadline)

    def test_coordinator_restart_after_deadline_keeps_completed_units(self):
        cells=[c for c in schedule(CFG)[0] if c['representation']=='role-envelope'][:2]
        class Catalog:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self,*_):return b'{"data":[{"id":"m1"},{"id":"m2"}]}'
        class Opener:
            def open(self,*_,**__):return Catalog()
        calls=[]
        def call(*args):calls.append(args[0]['step_id']);return fixture(*args)
        def population(*args):return run_population(*args,caller=call)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'cfg.json').write_text(json.dumps(CFG))
            argv=['role-run','--config',str(root/'cfg.json'),'--local-root',str(root/'local'),'--output-root',str(root/'shared')]
            with patch('sys.argv',argv),patch('aimeth_pilot.role_run.schedule',return_value=(cells,[])),\
                 patch('aimeth_pilot.role_run.request.build_opener',return_value=Opener()),\
                 patch('aimeth_pilot.role_run.run_population',side_effect=population),patch('sys.stdout',new_callable=StringIO):
                run_main()
                future=time.time()+3000
                with patch('time.time',return_value=future):run_main()
            result=json.loads((root/'shared/summary-private.json').read_text())
            self.assertEqual(len(calls),2);self.assertEqual(len(result['results']),2)
            self.assertEqual(result['unstarted'],[])
            self.assertEqual(result['budgets']['representation']['reserved_calls'],2)


if __name__=='__main__':unittest.main()
