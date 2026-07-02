# ThoughtOS Terminal Notes + Vault Sync Plan

## Goal

Make ThoughtOS easy to use from the terminal/Pi while keeping ThoughtOS as the source of truth for notes, tasks, and future Obsidian/Google Drive vault sync.

## Current MVP

### Backend

New local-first endpoints:

- `POST /api/notes/intake` — capture rough notes, standardize them, extract tasks
- `GET /api/notes` — list/search notes
- `GET /api/tasks` — list tasks
- `PATCH /api/tasks/{task_id}` — update task status
- `POST /api/vault-sources` — register an Obsidian vault source
- `GET /api/vault-sources` — list registered vault sources

Local terminal clients can call these endpoints from `127.0.0.1` without Google browser auth. Remote callers still need the normal Bearer token.

### Pi extension

Installed at:

```text
~/.pi/agent/extensions/thoughtos/index.ts
```

Commands:

```text
/note <rough notes>       Capture a general note
/call <rough notes>       Capture a meeting/call note
/task <task text>         Capture a task
/tasks                   Show open tasks
/notes [query]            Show recent/search notes
/thoughtos-clear          Clear the ThoughtOS widget
```

Tools available to the Pi agent:

```text
thoughtos_capture_note
thoughtos_list_tasks
```

## Usage

Start the ThoughtOS backend:

```bash
cd /home/hardik/Projects/ThoughtOS
source venv/bin/activate
PYTHONDONTWRITEBYTECODE=1 uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In Pi, reload extensions or restart Pi:

```text
/reload
```

Then capture notes:

```text
/call Ravi dashboard should show pending tasks. Need to fix telegram. Send build tomorrow.
```

List tasks:

```text
/tasks
```

Search notes:

```text
/notes telegram
```

## Data model

New tables:

- `notes`
- `tasks`
- `note_links`
- `vault_sources`

Important rule: raw notes are always preserved in `notes.raw_text`. AI-structured data is stored separately in `notes.structured_payload` so notes can be reprocessed later.

## Multiple Obsidian vaults from multiple Google Drives

The intended model is:

```text
Google Drive account/folder/file
  -> vault_sources row
  -> local sync cache / mounted folder
  -> ThoughtOS markdown importer/exporter
  -> notes/tasks tables
```

Each vault should be registered independently:

```json
{
  "name": "Personal Vault",
  "provider": "google_drive",
  "remote_id": "GOOGLE_DRIVE_FOLDER_ID",
  "local_path": "/home/hardik/Vaults/personal",
  "sync_direction": "bidirectional",
  "metadata": {
    "drive_account": "personal@gmail.com",
    "obsidian": true
  }
}
```

Next implementation step for vault sync:

1. Add `logic/vault_sync.py`.
2. For each `vault_sources` row:
   - discover markdown files from local path or Google Drive folder
   - parse frontmatter/body
   - create/update ThoughtOS `notes`
   - create/update `tasks` from markdown checkboxes
3. Add conflict policy:
   - ThoughtOS wins
   - Obsidian wins
   - newest modified wins
   - manual review
4. Add export path:
   - ThoughtOS notes/tasks -> standardized markdown in selected vault

Recommended first sync strategy: local filesystem sync via Google Drive mounted/synced folders. Direct Google Drive API sync can come later.
