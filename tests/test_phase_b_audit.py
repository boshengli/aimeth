import json
from pathlib import Path
import tempfile
import unittest

from tools.verify_p2_controls_run import ARMS, audit
from tools.rt_run import finalize_fenced_tasks
from aimeth_rt.control_arms import Budget


class PhaseBAuditTest(unittest.TestCase):
    def test_fenced_started_task_is_recorded_unknown_and_never_restarted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "arc2-independent.jsonl"
            events = root / "arc2-independent.events.jsonl"
            events.write_text(json.dumps({"event": "task_started", "task_id": "arc1", "rep": 0}) + "\n")
            fenced = {("arc1", 0)}
            kwargs = {"kind": "arc", "arm": "independent", "provider": "deepseek",
                      "model": "deepseek-flash", "budget": Budget(8, 262144),
                      "model_max_tokens": 262144, "seed": 1000, "run_name": "arc2-independent"}
            self.assertEqual(finalize_fenced_tasks(out, events, fenced, **kwargs), 1)
            self.assertEqual(finalize_fenced_tasks(out, events, fenced, **kwargs), 0)
            rows = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["dispatch_outcome"], "unknown")
            self.assertEqual(rows[0]["stop_reason"], "started_task_outcome_unknown_not_retried")
            self.assertIsNone(rows[0]["calls_used"])
            self.assertIsNone(rows[0]["completion_reasoning_tokens_used"])
            event_rows = [json.loads(line) for line in events.read_text().splitlines()]
            self.assertEqual(sum(row["event"] == "task_started" for row in event_rows), 1)
            self.assertEqual(sum(row["event"] == "task_finalized_unknown" for row in event_rows), 1)

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

    def test_audit_preserves_unknown_usage_without_inventing_zero_calls(self):
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
                    unknown = family == "arc2" and arm == "independent"
                    row = {"arm": arm, "kind": kind, "task_id": task, "rep": 0,
                           "provider": "deepseek", "model": "deepseek-flash",
                           "budget": {"calls": 8, "completion_reasoning_tokens": 262144},
                           "calls_used": None if unknown else 1,
                           "completion_reasoning_tokens_used": None if unknown else 8,
                           "final_eval_id": None if unknown else "eval1",
                           "cost_estimate_cny": None if unknown else 0.01,
                           "dispatch_outcome": "unknown" if unknown else "settled",
                           "steps": [] if unknown else [{"requested_max_tokens": 32768, "ok": True}]}
                    out.write_text(json.dumps(row) + "\n")
                    out.with_suffix(".events.jsonl").write_text(json.dumps({
                        "event": "task_started", "task_id": task, "rep": 0}) + "\n")
                    if unknown:
                        with out.with_suffix(".events.jsonl").open("a") as stream:
                            stream.write(json.dumps({"event": "task_finalized_unknown",
                                                     "task_id": task, "rep": 0}) + "\n")
            result = audit(run_dir, arc, bio)
            self.assertTrue(result["complete"], result["integrity_failures"])
            counts = result["results"]["arc2/independent"]
            self.assertEqual(counts["unknown_dispatch_outcomes"], 1)
            self.assertEqual(counts["tasks_with_unknown_token_usage"], 1)
            self.assertEqual(counts["completion_reasoning_tokens_known_sum"], 0)


if __name__ == "__main__":
    unittest.main()
