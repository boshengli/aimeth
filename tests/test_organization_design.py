import copy
import json
from pathlib import Path
import tempfile
import unittest

from aimeth_design.organizations import compile_arm, graph_summary, submission_plan, pilot_schedule
from aimeth_design.execution import dry_run, select_terminal, uniform_index
from aimeth_runtime.store import Store, Conflict
from aimeth_evaluation.controls import evaluate, public_tasks


class OrganizationTests(unittest.TestCase):
    def test_degree_budget_and_cross_group_contrast_at_four_scales(self):
        for n in (32, 128, 1000, 10000):
            local = graph_summary(compile_arm('L', n))
            cross = graph_summary(compile_arm('X', n))
            self.assertEqual(local['in_degree_range'], [2, 2])
            self.assertEqual(cross['in_degree_range'], [2, 2])
            self.assertEqual(local['out_degree_range'], cross['out_degree_range'])
            self.assertEqual(local['total_planned_messages'], cross['total_planned_messages'])
            self.assertEqual(local['cross_group_edges'], 0)
            self.assertEqual(cross['cross_group_edges'], n)
            self.assertEqual(cross['edges_per_communicating_round'], 2*n)

    def test_connectivity_is_local_or_global_as_specified(self):
        for arm, expected in [('L', 8), ('X', 32)]:
            config = compile_arm(arm)
            for reverse in (False, True):
                adjacency = {a: [] for a in config['agents']}
                for a, b in config['round_edges']['0']:
                    if reverse:
                        a, b = b, a
                    adjacency[a].append(b)
                visited, todo = set(), [config['agents'][0]]
                while todo:
                    item = todo.pop()
                    if item not in visited:
                        visited.add(item)
                        todo.extend(adjacency[item])
                self.assertEqual(len(visited), expected)

    def test_determinism_permutation_and_no_final_messages(self):
        self.assertEqual(compile_arm('X'), compile_arm('X'))
        self.assertNotEqual(compile_arm('X', seed=1)['organization']['groups'],
                            compile_arm('X', seed=2)['organization']['groups'])
        for arm in ('S', 'I', 'L', 'X'):
            config = compile_arm(arm)
            self.assertEqual(config['round_edges'][str(config['rounds']-1)], [])
            self.assertEqual(graph_summary(config)['canonical_call_slots'], 96)

    def test_randomized_pilot_preserves_paired_blocks(self):
        schedule = pilot_schedule(['a', 'b'], repeats=3)
        self.assertEqual(schedule, pilot_schedule(['a', 'b'], repeats=3))
        self.assertEqual(schedule['run_count'], 24)
        self.assertEqual(len({b['seed'] for b in schedule['blocks']}), 6)
        self.assertEqual(len({b['block_id'] for b in schedule['blocks']}), 6)
        for block in schedule['blocks']:
            self.assertEqual(set(block['arm_order']), {'S', 'I', 'L', 'X'})
            self.assertFalse(block['executed'])

    def test_manifest_event_size_is_checked_before_submission(self):
        with self.assertRaisesRegex(ValueError, '2 MiB'):
            compile_arm('X', population=10000, rounds=10)

    def test_invalid_configuration_fails(self):
        for kwargs in [{'population': 31}, {'group_size': 2}, {'population': 8},
                       {'rounds': True}, {'concurrency': 0}, {'seed': True}]:
            with self.assertRaises(ValueError):
                compile_arm('X', **kwargs)
        with self.assertRaises(ValueError):
            compile_arm('unknown')

    def test_budget_bounds_include_retries_and_unknown_inputs(self):
        config = compile_arm('X', 10000, output_tokens=512)
        plan = submission_plan(config)
        self.assertEqual(plan['max_attempts_total'], 90000)
        self.assertEqual(plan['max_output_tokens_all_attempts'], 46080000)
        self.assertIsNone(plan['max_total_tokens_all_attempts'])
        self.assertFalse(plan['live_launch_ready'])
        known = submission_plan(config, 4096)
        self.assertEqual(known['max_total_tokens_all_attempts'], 414720000)
        self.assertLess(known['client_inflight_cap'], known['logical_population'])

    def test_real_journal_inboxes_selection_and_resume(self):
        with tempfile.TemporaryDirectory() as temp:
            for arm in ('S', 'I', 'L', 'X'):
                config = compile_arm(arm, population=8, rounds=2, group_size=4)
                config['selection_seed'] = 700
                path = Path(temp) / (arm + '.sqlite')
                result = dry_run(path, arm, config)
                expected = graph_summary(config)['total_planned_messages']
                self.assertEqual(result['delivered_and_consumed_messages'], expected)
                self.assertTrue(result['status']['complete'])
                self.assertFalse(result['mathematical_effect_measured'])
                with Store(path) as store:
                    for row in store.db.execute('SELECT * FROM steps WHERE run_id=?', (arm,)):
                        prompt = json.loads(row['request'])['messages'][-1]['content']
                        context = json.loads(prompt.split('\n', 1)[1])
                        pairs = set(map(tuple, config['round_edges'].get(str(row['round_index']-1), [])))
                        for message in context['incoming']:
                            self.assertIn((message['sender'], row['agent_id']), pairs)
                            self.assertEqual(message['source_round'], row['round_index']-1)
                        self.assertEqual(context['checkpoint'] is None, row['round_index'] == 0)
                        if arm in ('I', 'S'):
                            self.assertEqual(context['incoming'], [])
                    with self.assertRaises(Conflict):
                        select_terminal(store, arm, 701)
                resumed = dry_run(path, arm, config)
                self.assertEqual(result, resumed)

    def test_no_live_calls_and_no_early_selection(self):
        config = compile_arm('I')
        config['selection_seed'] = 12
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'dry.sqlite'
            with Store(path) as store:
                store.create_run('test', config)
                with self.assertRaises(Conflict):
                    select_terminal(store, 'test', 12)
            config['transport'] = {'kind': 'openai'}
            with self.assertRaisesRegex(ValueError, 'cannot make model calls'):
                dry_run(path, 'test', config)

    def test_selection_is_content_blind_and_repeatable(self):
        self.assertEqual(uniform_index(1, 'task', 32), uniform_index(1, 'task', 32))
        self.assertEqual(uniform_index(1, 'task', 1), 0)
        for seed in range(100):
            self.assertIn(uniform_index(seed, 'task', 32), range(32))


class ExactControlTests(unittest.TestCase):
    # These witnesses are public development fixtures, NEVER held-out answers.
    good = {
        'poly-square': {'coefficients': [1, 2, 1]},
        'poly-difference': {'coefficients': [-12, 5, 2]},
        'integral-cubic': {'coefficients': [0, 1, 1, 1]},
        'integral-rational': {'coefficients': [0, 0, '-1/2', 0, '1/4']},
        'bezout': {'a': -9, 'b': 47},
        'prime-counterexample': {'n': 40, 'd': 41},
    }

    def test_every_public_task_accepts_an_exact_witness(self):
        self.assertEqual({t['id'] for t in public_tasks()}, set(self.good))
        for name, candidate in self.good.items():
            result = evaluate(name, json.dumps(candidate))
            self.assertEqual(result['status'], 'VERIFIED_WITHIN_SCOPE')
            self.assertFalse(result['frontier_proof_verified'])

    def test_rejects_plausible_wrong_mathematics(self):
        bad = {'poly-square': {'coefficients': [1, 1, 1]},
               'poly-difference': {'coefficients': [-12, 4, 2]},
               'integral-cubic': {'coefficients': [1, 1, 1, 1]},
               'integral-rational': {'coefficients': [0, 0, '-1/2', 0, '1/3']},
               'bezout': {'a': 9, 'b': 47},
               'prime-counterexample': {'n': 0, 'd': 41}}
        for name, candidate in bad.items():
            self.assertEqual(evaluate(name, candidate)['status'], 'INVALID_CERTIFICATE')

    def test_alternative_certificates_and_global_identity(self):
        self.assertTrue(evaluate('bezout', {'a': 14, 'b': -73})['passed'])
        self.assertTrue(evaluate('prime-counterexample', {'n': 41, 'd': 41})['passed'])
        # A polynomial agreeing at x=0 but different elsewhere must fail.
        self.assertFalse(evaluate('poly-square', {'coefficients': [1, 3, 1]})['passed'])
        self.assertTrue(evaluate('poly-square', {'coefficients': [1, 2, 1, 0]})['passed'])

    def test_untrusted_schema_and_overclaims(self):
        for value in [True, 1.0, '1/0', '__import__("os")', '9'*100]:
            self.assertEqual(evaluate('poly-square', {'coefficients': [value]})['status'], 'MALFORMED')
        for candidate in ['{"a":-9,"a":0,"b":47}', '[1,2]', 'I proved it',
                          '{"a":true,"b":47}', '{"a":-9,"b":47,"verified":true}', 'x'*8193]:
            self.assertEqual(evaluate('bezout', candidate)['status'], 'MALFORMED')
        self.assertEqual(evaluate('navier-stokes', {'proof': 'By consensus'})['status'], 'UNVERIFIED')


if __name__ == '__main__':
    unittest.main()
