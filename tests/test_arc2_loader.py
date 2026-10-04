import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from aimeth_rt.arc_data import grade_arc_attempts, load_arc2_evaluation, select_arc2_pilot


class Arc2LoaderTest(unittest.TestCase):
    def test_synthetic_archive_exposes_only_training_pairs_and_test_inputs(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "arc.tgz"
            with tarfile.open(path, "w:gz") as archive:
                for i in range(120):
                    name = f"arc2/data/evaluation/{i:08x}.json"
                    raw = {"train": [{"input": [[i % 10]], "output": [[(i + 1) % 10]]}],
                           "test": [{"input": [[3]], "output": [[9]]}]}
                    data = json.dumps(raw).encode()
                    info = tarfile.TarInfo(name)
                    info.size = len(data)
                    import io
                    archive.addfile(info, io.BytesIO(data))
            tasks = load_arc2_evaluation(path)
            self.assertEqual(len(tasks), 120)
            self.assertEqual(set(tasks["00000000"]["test"][0]), {"input"})
            self.assertEqual(tasks["00000000"]["train"][0]["output"], [[1]])

    def test_loader_requires_fixed_evaluation_count(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "arc.tgz"
            with tarfile.open(path, "w:gz") as archive:
                data = b'{"train":[{"input":[[1]],"output":[[1]]}],"test":[{"input":[[1]],"output":[[1]]}]}'
                info = tarfile.TarInfo("arc2/data/evaluation/00000000.json")
                info.size = len(data)
                import io
                archive.addfile(info, io.BytesIO(data))
            with self.assertRaisesRegex(ValueError, "expected 120"):
                load_arc2_evaluation(path)

    def test_grader_accepts_at_most_two_hidden_output_attempts(self):
        truth = [[[1]], [[2]]]
        self.assertTrue(grade_arc_attempts([[[[1]], [[0]]], [[[2]]]], truth))
        self.assertFalse(grade_arc_attempts([[[[0]], [[3]]], [[[1]]]], truth))
        self.assertFalse(grade_arc_attempts([[[[1]], [[0]], [[1]]], [[[2]]]], truth))

    def test_hash_pilot_selection_is_repeatable_and_outcome_blind(self):
        ids = [f"{i:08x}" for i in range(120)]
        first = select_arc2_pilot(ids)
        self.assertEqual(first, select_arc2_pilot(list(reversed(ids))))
        self.assertEqual(len(first), 40)
        self.assertEqual(len({x["task_id"] for x in first}), 40)

    def test_hash_pilot_rejects_duplicate_ids(self):
        with self.assertRaises(ValueError):
            select_arc2_pilot(["a", "a"], n=1)


if __name__ == "__main__":
    unittest.main()
