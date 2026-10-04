import json
from pathlib import Path
import unittest

from aimeth_arc.data import load_arc1_evaluation
from aimeth_arc.executor import run_program
from aimeth_arc.grading import exact_match, grade_attempts, grade_test_outputs, score_training


ARCHIVE = Path("/Volumes/Expand/0023-AIMeth_scratch/datasets/arc-agi-data.tgz")


class ArcHarnessTests(unittest.TestCase):
    @unittest.skipUnless(ARCHIVE.exists(), "local ARC archive unavailable")
    def test_loader_hides_test_answers_from_public_view(self):
        tasks = load_arc1_evaluation(ARCHIVE)
        self.assertEqual(len(tasks), 400)
        task = next(iter(tasks.values()))
        self.assertIn("output", task.test[0])
        self.assertNotIn("output", task.public_view()["test"][0])
        self.assertEqual(len(task.test_outputs()), len(task.test))

    def test_exact_grading_and_attempt_limit(self):
        target = [[1, 2], [3, 4]]
        self.assertFalse(exact_match([[1, 2], [4, 3]], target))
        self.assertFalse(exact_match([[True, 2], [3, 4]], target))
        self.assertTrue(grade_attempts([[[0]], target], target))
        with self.assertRaises(ValueError):
            grade_attempts([target, target, target], target)

    def test_sandbox_runs_numpy_and_rejects_io(self):
        inp = [[1, 2], [3, 4]]
        identity = run_program("def transform(grid):\n    return grid", [inp])
        if identity.status == "sandbox_unavailable":
            self.skipTest("OS sandbox unavailable")
        self.assertEqual(identity.status, "ok", identity.error)
        self.assertEqual(identity.outputs, [inp])
        rotated = run_program("import numpy as np\ndef transform(grid):\n    return np.rot90(np.array(grid)).tolist()", [inp])
        self.assertEqual(rotated.status, "ok", rotated.error)
        self.assertEqual(rotated.outputs, [[[2, 4], [1, 3]]])
        self.assertEqual(run_program("def transform(grid):\n    return open('/etc/passwd')", [inp]).status,
                         "execution_error")
        self.assertEqual(run_program("def transform(grid):\n    return grid.tofile('/tmp/x')", [inp]).status,
                         "invalid_program")
        self.assertEqual(run_program("import os\ndef transform(grid):\n    return grid", [inp]).status,
                         "invalid_program")

    def test_wall_timeout_stops_unbounded_program(self):
        result = run_program("def transform(grid):\n    while True:\n        pass", [[[1]]], timeout_s=0.5)
        if result.status == "sandbox_unavailable":
            self.skipTest("OS sandbox unavailable")
        self.assertEqual(result.status, "timeout")

    @unittest.skipUnless(ARCHIVE.exists(), "local ARC archive unavailable")
    def test_train_scoring_and_hidden_test_grading(self):
        task = next(iter(load_arc1_evaluation(ARCHIVE).values()))
        correct, total = score_training(task, lambda grid: task.train[0]["output"])
        self.assertGreaterEqual(correct, 1)
        self.assertEqual(total, len(task.train))
        target = task.test_outputs()
        self.assertTrue(grade_test_outputs(task, [[out] for out in target]))
        self.assertFalse(grade_test_outputs(task, [[[[0]]] for _ in target]))


if __name__ == "__main__":
    unittest.main()
