import sqlite3
import tempfile
import unittest
from pathlib import Path
from thoughtos_server.database_admin import merge, snapshot


class DatabaseAdminTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name) / 'source.db'
        self.dst = Path(self.tmp.name) / 'target.db'
        for path in (self.src, self.dst):
            with sqlite3.connect(path) as c:
                c.execute('CREATE TABLE notes(id TEXT PRIMARY KEY, text TEXT)')

    def put(self, path, records):
        with sqlite3.connect(path) as c:
            c.executemany('INSERT INTO notes VALUES (?, ?)', records)

    def rows(self, path):
        with sqlite3.connect(path) as c:
            return c.execute('SELECT * FROM notes ORDER BY id').fetchall()

    def test_merge_preserves_both_sides_and_is_idempotent(self):
        self.put(self.src, [('a', 'original')])
        self.put(self.dst, [('b', 'server')])
        self.assertEqual(merge(self.src, self.dst)['notes']['inserted'], 1)
        self.assertEqual(merge(self.src, self.dst)['notes']['identical'], 1)
        self.assertEqual(self.rows(self.dst), [('a', 'original'), ('b', 'server')])
        self.assertEqual(self.rows(self.src), [('a', 'original')])

    def test_conflict_rolls_back_prior_inserts(self):
        self.put(self.src, [('a', 'new'), ('b', 'different')])
        self.put(self.dst, [('b', 'server')])
        with self.assertRaises(ValueError):
            merge(self.src, self.dst)
        self.assertEqual(self.rows(self.dst), [('b', 'server')])

    def test_schema_mismatch_is_rejected(self):
        self.put(self.src, [('a', 'note')])
        with sqlite3.connect(self.dst) as c:
            c.execute('ALTER TABLE notes ADD COLUMN extra TEXT')
        with self.assertRaises(ValueError):
            merge(self.src, self.dst)

    def test_snapshot_includes_committed_wal_and_is_independent(self):
        conn = sqlite3.connect(self.src)
        self.addCleanup(conn.close)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute("INSERT INTO notes VALUES ('a', 'committed')")
        conn.commit()
        snapshot(self.src, self.dst)
        self.assertEqual(self.rows(self.dst), [('a', 'committed')])
        self.assertEqual(self.dst.stat().st_mode & 0o777, 0o600)

    def test_snapshot_cannot_replace_live_source(self):
        with self.assertRaises(ValueError):
            snapshot(self.src, self.src)


if __name__ == '__main__':
    unittest.main()
