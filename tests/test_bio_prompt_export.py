import csv
import json
from pathlib import Path
import tempfile
import unittest

from tools.export_public_bio_prompts import export_public_prompts
from tools.rt_run import load_tasks_bio
from types import SimpleNamespace


class BioPromptExportTest(unittest.TestCase):
    def test_export_contains_only_generator_view_and_loader_checks_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bench = root / "bench"
            tasks = bench / "tasks"
            tasks.mkdir(parents=True)
            (bench / "mask_sets.json").write_text(json.dumps({
                "m": [{"id": "SolycMASK", "unused_secret_answer": "PRIVATE_TARGET_VALUE"}]}))
            (tasks / "task-1.json").write_text(json.dumps({
                "task_id": "task-1", "reference": "WT-3D-1", "target": "WT-12D-1",
                "n_masked": 1, "n_visible": 12, "mask_set": "m"}))
            annotation = root / "annotation.csv"
            with annotation.open("w", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["gene", "symbol", "group", "category"])
                writer.writerow(["SolycMASK", "MASK", "group", "Callus_development"])
            records = export_public_prompts(bench, annotation, expected_count=1)
            serialized = json.dumps(records)
            self.assertIn("SolycMASK", serialized)
            self.assertNotIn("PRIVATE_TARGET_VALUE", serialized)
            manifest = root / "prompts.json"
            manifest.write_text(json.dumps(records))
            loaded = load_tasks_bio(SimpleNamespace(bio_prompt_manifest=str(manifest), only=None,
                                                    bench=None, annot=None))
            self.assertEqual([x[0] for x in loaded], ["task-1"])
            records[0]["messages"][1]["content"] += "tamper"
            manifest.write_text(json.dumps(records))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_tasks_bio(SimpleNamespace(bio_prompt_manifest=str(manifest), only=None,
                                                bench=None, annot=None))


if __name__ == "__main__":
    unittest.main()
