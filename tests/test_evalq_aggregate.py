import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from aimeth_rt.private_aggregate import handle_aggregate


class AggregatePrivacyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "private").mkdir()
        (self.root / "done").mkdir()
        self.cfg = {"root": str(self.root)}

    def tearDown(self):
        self.tmp.cleanup()

    def add_arc(self, eid, prediction, train_frac):
        (self.root / "private" / f"{eid}.json").write_text(json.dumps({
            "job": {"kind": "arc", "task_id": "t1"}, "test_preds": [prediction]}))
        (self.root / "done" / f"{eid}.json").write_text(json.dumps({
            "status": "ok", "train_frac": train_frac}))

    def test_arc_vote_tie_uses_best_visible_train_score_and_hides_grids(self):
        left, right = [[1, 2]], [[2, 1]]
        self.add_arc("e1", left, 0.5)
        self.add_arc("e2", right, 1.0)
        visible, private = handle_aggregate({"task_id": "t1", "source_kind": "arc",
                                              "mode": "vote", "eval_ids": ["e1", "e2"]}, self.cfg)
        self.assertEqual(private["test_preds"], [right])
        self.assertEqual(visible["agreement_by_test"], [1])
        self.assertEqual(visible["contributor_eval_ids"], ["e2"])
        self.assertNotIn("test_preds", visible)
        self.assertNotIn("output", json.dumps(visible))

    def test_arc_vote_counts_consensus_without_exposing_predictions(self):
        grid = [[1, 2]]
        self.add_arc("e1", grid, 0.5)
        self.add_arc("e2", grid, 0.5)
        visible, private = handle_aggregate({"task_id": "t1", "source_kind": "arc",
                                              "mode": "vote", "eval_ids": ["e1", "e2"]}, self.cfg)
        self.assertEqual(private["test_preds"], [grid])
        self.assertEqual(visible["agreement_by_test"], [2])
        self.assertEqual(set(visible["contributor_eval_ids"]), {"e1", "e2"})

    def test_cross_task_private_source_rejected(self):
        self.add_arc("e1", [[1]], 0.5)
        with self.assertRaises(ValueError):
            handle_aggregate({"task_id": "another-task", "source_kind": "arc",
                              "mode": "vote", "eval_ids": ["e1"]}, self.cfg)

    def test_traversal_and_duplicate_source_ids_rejected(self):
        for ids in (["../outside"], ["e1", "e1"]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                handle_aggregate({"task_id": "t1", "source_kind": "arc",
                                  "mode": "vote", "eval_ids": ids}, self.cfg)

    def test_callus_predictions_are_averaged_privately(self):
        ids = []
        for index, values in enumerate(([[1.0, 3.0]], [[3.0, 5.0]]), 1):
            eid = f"b{index}"
            ids.append(eid)
            np.save(self.root / "private" / f"{eid}.npy", np.asarray(values, dtype=np.float32))
            (self.root / "private" / f"{eid}.json").write_text(json.dumps({
                "job": {"kind": "bio", "task_id": "bio1"}, "pred_file": f"{eid}.npy"}))
            (self.root / "done" / f"{eid}.json").write_text(json.dumps({
                "status": "ok", "val_pattern_r": 0.1 * index}))
        visible, private = handle_aggregate({"task_id": "bio1", "source_kind": "bio",
                                              "mode": "average", "eval_ids": ids}, self.cfg)
        self.assertTrue(np.allclose(private["pred_array"], [[2.0, 4.0]]))
        self.assertAlmostEqual(visible["source_mean_visible_score"], 0.15)
        self.assertNotIn("pred_array", visible)


if __name__ == "__main__":
    unittest.main()
