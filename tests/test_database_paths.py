"""All tests use disposable databases; no private data or network calls."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from thoughtos_server.paths import database_path, using_database
from thoughtos_server.config import load_config
from thoughtos_server.graph_store import GraphStore
from thoughtos_server.note_intake import intake_note
from logic import sql_engine, note_intake as legacy_intake


class DatabasePathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.db = str(self.root / 'shared.db')
        env = patch.dict(os.environ, {'THOUGHTOS_DB_PATH': self.db, 'THOUGHTOS_LLM_ENABLED': '0'})
        env.start(); self.addCleanup(env.stop)

    def test_defaults_and_config_agree_from_different_working_directories(self):
        old = os.getcwd()
        try:
            for name in ['one', 'two']:
                cwd = self.root / name; cwd.mkdir(); os.chdir(cwd)
                self.assertEqual(load_config().db_path, self.db)
                self.assertEqual(GraphStore().db_path, self.db)
                with sql_engine.get_connection() as conn:
                    self.assertEqual(conn.execute('PRAGMA database_list').fetchone()[2], self.db)
                self.assertFalse((cwd / 'context_os.db').exists())
        finally:
            os.chdir(old)

    def test_relative_config_is_anchored_to_package_root_not_cwd(self):
        with patch.dict(os.environ, {'THOUGHTOS_DB_PATH': 'relative.db'}):
            self.assertEqual(Path(database_path()).parent, Path(__file__).resolve().parents[1])

    def test_context_override_is_restored_even_after_exception(self):
        other = str(self.root / 'other.db')
        with self.assertRaises(RuntimeError):
            with using_database(other):
                self.assertEqual(database_path(), other)
                raise RuntimeError('test')
        self.assertEqual(database_path(), self.db)

    def test_capture_tasks_and_reads_share_explicit_database(self):
        other = str(self.root / 'explicit.db')
        with patch.object(legacy_intake, 'ask_gemini_json', side_effect=AssertionError('No cloud calls')):
            result = intake_note('test-user', 'TODO: send test report @Wardrub', db_path=other, extract_entities=False)
        with sqlite3.connect(other) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM notes').fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT count(*) FROM tasks').fetchone()[0], 1)
        with using_database(other):
            self.assertEqual(sql_engine.list_notes('test-user')[0]['note_id'], result['note']['note_id'])
        self.assertFalse(Path(self.db).exists())

    def test_graph_and_note_capture_share_one_database(self):
        with patch('thoughtos_server.note_intake.ExtractionPipeline.extract', return_value={
            'entities': [], 'relationships': [], 'rules_proposed': [],
        }) as extract:
            intake_note('test-user', 'A plain test note', db_path=self.db)
        extract.assert_called_once()
        with sqlite3.connect(self.db) as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({'notes', 'tasks', 'entities', 'relationships'} <= tables)
            self.assertEqual(conn.execute('SELECT count(*) FROM notes').fetchone()[0], 1)

    def test_disabling_llm_also_disables_legacy_standardization(self):
        with patch.object(legacy_intake, 'ask_gemini_json') as cloud:
            self.assertIsNone(legacy_intake._try_llm_standardize('private test text', 'quick_note'))
            cloud.assert_not_called()


if __name__ == '__main__':
    unittest.main()
