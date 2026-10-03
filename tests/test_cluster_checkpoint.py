import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from cluster.checkpoint_population import capture_once


class ClusterCheckpointTests(unittest.TestCase):
    def test_backup_preserves_sqlite_and_atomic_receipts_and_keeps_two_generations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / 'source', root / 'output'
            (source / 'receipts').mkdir(parents=True)
            db = sqlite3.connect(source / 'journal.sqlite')
            db.execute('CREATE TABLE events (seq INTEGER PRIMARY KEY, value TEXT)')
            db.execute('INSERT INTO events VALUES (1, "kept")')
            db.commit(); db.close()
            budget = sqlite3.connect(source / 'budget.sqlite')
            budget.execute('CREATE TABLE calls (n INTEGER)')
            budget.execute('INSERT INTO calls VALUES (3)')
            budget.commit(); budget.close()
            (source / 'population.json').write_text('{"id":"p1"}\n')
            (source / 'receipts' / 'one.json').write_text('{"receipt":1}\n')

            first = capture_once(source, output)
            receipt = output / 'checkpoints' / first['checkpoint']
            check = sqlite3.connect(receipt / 'journal.sqlite')
            self.assertEqual(check.execute('SELECT value FROM events').fetchone()[0], 'kept')
            check.close()
            self.assertTrue((receipt / 'receipts' / 'one.json').is_file())
            manifest = json.loads((receipt / 'checkpoint.json').read_text())
            self.assertEqual(manifest['receipt_count'], 1)
            self.assertEqual(json.loads((output / 'latest-checkpoint.json').read_text())['checkpoint'], first['checkpoint'])

            capture_once(source, output)
            third = capture_once(source, output)
            self.assertEqual(len(list((output / 'checkpoints').glob('checkpoint-*'))), 2)
            self.assertTrue((output / 'checkpoints' / third['checkpoint'] / 'journal.sqlite').is_file())


if __name__ == '__main__':
    unittest.main()
