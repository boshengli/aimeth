import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.verify_artifacts import verify


class ArtifactIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        content = b"Synthetic evidence; no mathematical result.\n"
        (self.root / "payload.txt").write_bytes(content)
        self.record = {"id": "synthetic-1", "path": "payload.txt", "bytes": len(content),
                       "sha256": hashlib.sha256(content).hexdigest()}
        self.path = self.root / "manifest.json"
        self.write([self.record])

    def write(self, records):
        self.path.write_text(json.dumps({"schema_version": "1.0", "artifacts": records}))

    def test_original_is_valid_but_not_scientifically_verified(self):
        result = verify(self.path)
        self.assertEqual(result["artifacts_checked"], 1)
        self.assertFalse(result["scientific_validity_checked"])

    def test_same_length_tampering_is_detected(self):
        p = self.root / "payload.txt"
        p.write_bytes(p.read_bytes().replace(b"Synthetic", b"synthetic"))
        with self.assertRaisesRegex(ValueError, "changed"):
            verify(self.path)

    def test_missing_artifact_is_rejected(self):
        (self.root / "payload.txt").unlink()
        with self.assertRaises(ValueError):
            verify(self.path)

    def test_duplicate_id_is_rejected(self):
        self.write([self.record, self.record.copy()])
        with self.assertRaises(ValueError):
            verify(self.path)

    def test_duplicate_resolved_path_is_rejected(self):
        self.write([self.record, {**self.record, "id": "alias", "path": "./payload.txt"}])
        with self.assertRaises(ValueError):
            verify(self.path)

    def test_path_escape_is_rejected(self):
        self.write([{**self.record, "path": "../outside.txt"}])
        with self.assertRaisesRegex(ValueError, "inside"):
            verify(self.path)

    def test_symbolic_link_is_rejected(self):
        (self.root / "alias.txt").symlink_to(self.root / "payload.txt")
        self.write([{**self.record, "path": "alias.txt"}])
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            verify(self.path)

    def test_empty_manifest_is_not_a_success(self):
        self.write([])
        with self.assertRaises(ValueError):
            verify(self.path)


if __name__ == "__main__":
    unittest.main()
