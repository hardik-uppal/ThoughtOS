"""Private, capability-scoped experiment snapshots. Never opens the canonical ThoughtOS DB."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import uuid
from datetime import datetime, timezone


def run(request, path):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.umask(0o077)
    owner = request['owner']
    if len(owner) != 64 or any(c not in '0123456789abcdef' for c in owner):
        raise ValueError('Invalid experiment namespace')
    db = sqlite3.connect(path, timeout=10)
    os.chmod(path, 0o600)
    db.row_factory = sqlite3.Row
    try:
        db.execute('''CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
            kind TEXT NOT NULL, created_at TEXT NOT NULL, note_count INTEGER NOT NULL,
            event_count INTEGER NOT NULL, build_id TEXT NOT NULL, payload TEXT NOT NULL)''')
        db.execute('CREATE INDEX IF NOT EXISTS snapshots_owner ON snapshots(owner, created_at DESC)')
        action = request['action']
        if action == 'list':
            rows = db.execute('SELECT id,title,kind,created_at,note_count,event_count,build_id FROM snapshots WHERE owner=? ORDER BY created_at DESC LIMIT 100', (owner,)).fetchall()
            return {'snapshots': [dict(row) for row in rows]}
        if action == 'save':
            kind = request.get('kind', 'manual')
            if kind not in {'manual', 'auto', 'safety'}:
                raise ValueError('Invalid snapshot kind')
            if kind == 'manual' and db.execute("SELECT COUNT(*) FROM snapshots WHERE owner=? AND kind='manual'", (owner,)).fetchone()[0] >= 50:
                raise ValueError('50 named snapshots saved. Delete an old snapshot before saving another.')
            payload = request['payload']
            if len(json.dumps(payload).encode()) > 2_000_000:
                raise ValueError('Snapshot is too large')
            ident = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            with db:
                db.execute('INSERT INTO snapshots VALUES (?,?,?,?,?,?,?,?,?)', (
                    ident, owner, str(request.get('title', 'Untitled experiment'))[:120], kind, now,
                    len(payload['notes']), len(payload.get('events', [])), payload['buildId'], json.dumps(payload)))
                # Named snapshots are never automatically deleted. Keep the last 20 autosaves/safety copies.
                if kind != 'manual':
                    db.execute('DELETE FROM snapshots WHERE owner=? AND kind=? AND id NOT IN (SELECT id FROM snapshots WHERE owner=? AND kind=? ORDER BY created_at DESC LIMIT 20)', (owner, kind, owner, kind))
            return {'id': ident, 'created_at': now}
        ident = request.get('id', '')
        row = db.execute('SELECT * FROM snapshots WHERE id=? AND owner=?', (ident, owner)).fetchone()
        if not row:
            raise LookupError('Snapshot not found')
        if action == 'get':
            return {'id': row['id'], 'title': row['title'], 'payload': json.loads(row['payload'])}
        if action == 'delete':
            with db:
                db.execute('DELETE FROM snapshots WHERE id=? AND owner=?', (ident, owner))
            return {'deleted': True}
        raise ValueError('Unknown operation')
    finally:
        db.close()


if __name__ == '__main__':
    try:
        request = json.load(sys.stdin)
        result = run(request, os.environ.get('EXPERIMENTS_DB', str(Path.home()/'.local/share/thoughtos/visual-garden/experiments.sqlite3')))
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps({'error': str(error)}))
        sys.exit(1)
