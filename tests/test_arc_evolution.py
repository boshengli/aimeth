import unittest

from aimeth_arc.data import ArcTask
from aimeth_arc.evolution import evolutionary_search
from aimeth_arc.executor import run_program


class MockMutator:
    def __init__(self):
        self.calls = []

    def mutate(self, task, parent, call_id):
        self.calls.append(call_id)
        return "def transform(grid):\n    return [[x+1 for x in row] for row in grid]"


class EvolutionTests(unittest.TestCase):
    def test_two_task_smoke_respects_call_budget_and_training_only(self):
        if run_program("def transform(grid):\n    return grid", [[[1]]]).status == "sandbox_unavailable":
            self.skipTest("OS sandbox unavailable")
        for task_id in ("00000001", "00000002"):
            task = ArcTask(task_id,
                           ({"input": [[1]], "output": [[2]]},),
                           ({"input": [[3]], "output": [[4]]},))
            mutator = MockMutator()
            result = evolutionary_search(task, mutator, call_budget=2, seed=17)
            self.assertEqual(result["calls_attempted"], 2)
            self.assertEqual(len(mutator.calls), 2)
            self.assertEqual(result["best_training_correct"], 1)
            self.assertNotIn("test_success", result)


if __name__ == "__main__":
    unittest.main()
