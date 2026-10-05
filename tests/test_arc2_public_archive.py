from __future__ import annotations

import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from aimeth_rt.arc_data import load_arc2_evaluation
from tools.build_arc2_public_archive import build


class Arc2PublicArchiveTests(unittest.TestCase):
    def test_archive_keeps_train_outputs_and_drops_test_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "evaluation"
            source.mkdir()
            for i in range(120):
                tid = f"{i:08x}"
                (source / f"{tid}.json").write_text(json.dumps({
                    "train": [{"input": [[i]], "output": [[i + 1]]}],
                    "test": [{"input": [[i + 2]], "output": [[987654321]]}],
                }))
            manifest = root / "tasks.json"
            manifest.write_text(json.dumps([f"{i:08x}" for i in range(40)]))
            archive = root / "public.tar.gz"
            digest = build(source, manifest, archive)

            views = load_arc2_evaluation(archive)
            self.assertEqual(len(views), 120)
            self.assertEqual(views["00000000"]["train"][0]["output"], [[1]])
            self.assertEqual(views["00000000"]["test"], [{"input": [[2]]}])
            with tarfile.open(archive, "r:gz") as tar:
                content = b"".join(tar.extractfile(m).read() for m in tar.getmembers())
            self.assertNotIn(b"987654321", content)
            self.assertEqual(len(digest), 64)


if __name__ == "__main__":
    unittest.main()
