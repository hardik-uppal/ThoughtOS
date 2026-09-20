import importlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from thoughtos_server.graph_store import GraphStore


class NoteQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / 'query.db')
        with patch.dict(os.environ, {'THOUGHTOS_DB_PATH': self.db}), patch.object(GraphStore, 'init'):
            self.module = importlib.import_module('thoughtos_server.mcp_server')
        with sqlite3.connect(self.db) as c:
            c.executescript('''
            CREATE TABLE notes(note_id TEXT PRIMARY KEY, user_id TEXT, title TEXT,
              raw_text TEXT, summary TEXT, note_type TEXT, created_at TEXT);
            CREATE TABLE relationships(source_entity_id TEXT, target_entity_id TEXT, source_note_id TEXT);
            ''')
            c.executemany('INSERT INTO notes VALUES (?,?,?,?,?,?,?)', [
                ('old', 'local@thoughtos', 'Older linked note', 'Older text', '', '', '2026-01-01'),
                ('new', 'local@thoughtos', 'Fresh note', 'Wardrub original, not extracted', '', '', '2026-02-01'),
                ('other', 'another-user', 'Wardrub private', 'Wardrub other owner', '', '', '2026-03-01'),
            ])
        self.graph = MagicMock()
        self.graph.find_entities.return_value = [{'entity_id': 'e', 'source_note_id': 'old', 'name': 'Wardrub'}]
        for p in [patch.object(self.module, 'config', SimpleNamespace(db_path=self.db)), patch.object(self.module, 'graph', self.graph)]:
            p.start(); self.addCleanup(p.stop)

    def test_existing_entity_does_not_hide_unextracted_notes(self):
        result = self.module.handle_query_notes({'entityName': 'Wardrub'})
        self.assertEqual([n['note_id'] for n in result['details']['notes']], ['new', 'old'])

    def test_lexical_fallback_is_owner_scoped(self):
        self.graph.find_entities.return_value = []
        result = self.module.handle_query_notes({'entityName': 'Wardrub'})
        self.assertEqual([n['note_id'] for n in result['details']['notes']], ['new'])
