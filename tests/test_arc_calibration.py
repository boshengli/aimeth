import csv
import json
from pathlib import Path
import tempfile
import unittest

from aimeth_arc.calibration import build_request, cost_envelope_cny, Journal
from aimeth_arc.data import ArcTask
from aimeth_arc.pilot import freeze_pilot


class CalibrationTests(unittest.TestCase):
    def test_prompt_excludes_test_answers_and_cost_is_bounded(self):
        task = ArcTask("00000001", ({"input": [[1]], "output": [[2]]},),
                       ({"input": [[3]], "output": [[9]]},))
        body = build_request(task, "deepseek")
        user_text = body["messages"][1]["content"]
        public = json.loads(user_text.split("Task data:\n", 1)[1])
        self.assertEqual(public["test"], [{"input": [[3]]}])
        self.assertEqual(body["thinking"], {"type": "enabled"})
        self.assertGreater(cost_envelope_cny(len(json.dumps(body).encode()), "deepseek"), 0)

    def test_journal_preserves_uncertain_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipts.jsonl"
            j = Journal(path)
            j.append({"event": "dispatch_started", "request_id": "r1", "reserve_cny": 1.2})
            j.append({"event": "dispatch_started", "request_id": "r2", "reserve_cny": 1.5})
            j.append({"event": "settled", "request_id": "r2", "reserve_cny": 1.5,
                      "estimated_cny": 0.2})
            resumed = Journal(path)
            self.assertEqual(resumed.started, {"r1", "r2"})
            self.assertEqual(resumed.finished, {"r2"})
            self.assertAlmostEqual(resumed.unknown_reserved_cny, 1.2)
            self.assertAlmostEqual(resumed.known_estimate_cny, 0.2)

    def test_pilot_selection_is_stratified_and_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "calibration.csv"
            archive = root / "archive.tgz"
            archive.write_bytes(b"fixture")
            fields = ["task_id", "max_input_area", "deepseek_samples", "zhipu_samples",
                      "pooled_pass_at_1"]
            with source.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for i in range(400):
                    writer.writerow({"task_id": f"{i:08x}", "max_input_area": i + 1,
                                     "deepseek_samples": 4, "zhipu_samples": 4,
                                     "pooled_pass_at_1": 0.375 if i < 80 else 0.0})
            out = root / "pilot.json"
            result = freeze_pilot(source, archive, out)
            self.assertEqual(result["pilot_count"], 40)
            manifest = json.loads(out.read_text())
            self.assertEqual(len(manifest["remaining_task_ids"]), 360)
            with self.assertRaises(FileExistsError):
                freeze_pilot(source, archive, out)


if __name__ == "__main__":
    unittest.main()
