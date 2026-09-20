# ThoughtOS storage and multiple machines

## Current state

Code is versioned in Git; private notes and graph data are not. On the current Mac,
Claude/Codex configure `THOUGHTOS_DB_PATH=/Users/hardikuppal/ThoughtOS/context_os.db`.
Pushing source code does not upload or synchronize that database. The Wardrub seed
notes remain local. No remote service, daemon, periodic graph worker, review skill,
or cross-machine sync has been installed by this change.

The shared path resolver now applies to graph, note/task storage and the legacy
embedding store. `THOUGHTOS_DB_PATH` is preferred; use an absolute path. Defaults
and explicit relative paths are anchored to the installed package/repository root,
not whichever project launched the CLI/MCP process. For a packaged/production
installation, always set an absolute path in a writable data directory.
Explicit intake `db_path` overrides apply to notes/tasks as well as the graph.
Restart existing MCP clients after upgrading to load the change.

No database was moved, merged, cleared or re-extracted. This corrects future
reads/writes; it does not automatically recover stray databases from old working
directories. Inspect those separately before importing/deduplicating records.
`THOUGHTOS_LLM_ENABLED=0` now also disables legacy Gemini note standardization,
not just graph extraction. This does not disable explicit embedding/re-extraction
commands that intentionally call a provider; do not run those without consent.

## Recommended first multi-machine deployment (proposed)

Use one always-on private host with one canonical SQLite database on its local
persistent disk. Clients on each Mac/PC connect to that host. Do not maintain an
independently writable database copy per machine.

```text
Mac / second computer / coding harness
              | authenticated private connection
              v
        ThoughtOS on one host
              |
       local persistent SQLite
              |
       encrypted tested backups
```

An initial bridge can use **SSH stdio MCP**: the client launches an MCP process
on the canonical host and forwards its stdin/stdout. All server processes use the
same absolute database path on that host. SSH handles encryption/authentication;
no public HTTP MCP endpoint is necessary. Example client command, after provisioning:

```text
ssh -T thoughtos-host env THOUGHTOS_DB_PATH=/srv/thoughtos/context_os.db THOUGHTOS_LLM_ENABLED=0 /srv/thoughtos/.venv/bin/thoughtos mcp
```

Use SSH keys, a restricted dedicated OS account, verified host keys, private
network access (e.g. Tailscale), and no interactive shell banners on stdout. This
example is a deployment design, not an already-configured host.

For a shared HTTP daemon later, add authenticated MCP transport and a thin stdio
bridge. Bind privately and use TLS/token validation. **Do not expose the existing
`mcp --port` handler publicly**: it currently binds all interfaces and lacks the
necessary remote authorization. The current local HTTP auth assumptions are not
an audited multi-user service. Existing MCP handlers are single-owner tooling.

SQLite is sufficient for a single personal server and modest concurrency. A
PostgreSQL migration becomes useful for multiple API replicas/high concurrent
writes; it is not needed merely to connect a second laptop. Graph tables can
remain relational. Do not use a live SQLite file over SMB/NFS/shared drive mounts.

## Backups and migration

- Do not sync a live `.db`, `-wal` or `-shm` file through Git, Google Drive, Dropbox
  or iCloud. File sync does not coordinate SQLite transactions and can lose updates.
- Use SQLite's backup API (including committed WAL data), not a blind file copy
  while processes may be writing. Keep snapshots outside the repository.
- Encrypt backups, restrict permissions, set retention, and regularly test a restore.
- For the first server migration: stop local writes, take a consistent snapshot,
  copy through an encrypted channel, restore to the canonical host, validate
  `PRAGMA integrity_check` plus note/task/entity counts, then point all clients to
  the host. Keep the old database read-only as rollback until verified.
- If a client is offline, initially report unavailable rather than silently creating
  a divergent local database. Durable offline capture/outbox, stable operation IDs,
  retries and conflict resolution should be a separate implemented milestone.

`.gitignore` covers SQLite data and sidecars. Historical `data/sunya.db` is already
tracked as an empty file; ignore rules do not untrack existing files. Never stage
private database contents. A future encrypted backup destination still needs to
be selected; nothing is uploaded by this documentation.

## Verification for this change

`THOUGHTOS_LLM_ENABLED=0 .venv/bin/python -m unittest discover -s tests -v`

Tests use disposable databases only: alternate working directories, absolute and
relative configuration, explicit per-call DB override, override restoration,
shared notes/tasks/graph tables and disabled cloud standardization. No model calls
or automatic changes to existing private notes.
