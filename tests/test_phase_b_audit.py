import json
from pathlib import Path
import tempfile
import unittest

from tools.verify_p2_controls_run import ARMS, audit


class PhaseBAuditTest(unittest.TestCase):
    def test_complete_denominator_and_budget_check(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            arc = root / "arc.json"
            bio = root / "bio.json"
            arc.write_text(json.dumps({"tasks": [{"task_id": "arc1"}]}))
            bio.write_text(json.dumps([{"task_id": "bio1"}]))
            run_dir = root / "runs"
            for family, kind, task in (("arc2", "arc", "arc1"), ("callus", "bio", "bio1")):
                for arm in ARMS:
                    out = run_dir / f"{family}-{arm}.jsonl"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    row = {"arm": arm, "kind": kind, "task_id": task, "rep": 0,
                           "provider": "deepseek", "model": "deepseek-flash",
                           "budget": {"calls": 8, "completion_reasoning_tokens": 262144},
                           "calls_used": 1, "completion_reasoning_tokens_used": 8,
                           "final_eval_id": "eval1", "cost_estimate_cny": 0.01,
                           "steps": [{"requested_max_tokens": 262144 if arm == "single_long" else 32768,
                                      "ok": True}]}
                    out.write_text(json.dumps(row) + "\n")
                    out.with_suffix(".events.jsonl").write_text(json.dumps({
                        "event": "task_started", "task_id": task, "rep": 0}) + "\n")
            result = audit(run_dir, arc, bio)
            self.assertTrue(result["complete"], result["integrity_failures"])
            self.assertEqual(result["arc2_expected"], 1)
            self.assertEqual(result["callus_expected"], 1)

    def test_missing_task_is_not_dropped_from_denominator(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            arc = root / "arc.json"
            bio = root / "bio.json"
            arc.write_text(json.dumps({"tasks": [{"task_id": "arc1"}]}))
            bio.write_text(json.dumps([{"task_id": "bio1"}]))
            run_dir = root / "runs"
            result = audit(run_dir, arc, bio)
            self.assertFalse(result["complete"])
            self.assertTrue(any("denominator mismatch" in item for item in result["integrity_failures"]))


if __name__ == "__main__":
    unittest.main()
