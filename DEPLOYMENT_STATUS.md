# Home-server consolidation — 2026-09-20 UTC

## Completed

- Preserved and merged the home-server Git history/model preference, including its
  visual-exploration design note. Both checkouts track `fix/shared-database-path`;
  changes are pushed in PR #2. Main is not merged by this operation.
- Installed the Git checkout as a wheel into the home-server virtualenv. The
  `thoughtos-home` wrapper supplies the canonical DB path and machine preferences.
- Took consistent private backups of both databases before consolidation, keeping
  both originals on both machines. No DB contents, credentials or backups in Git.
- Additively imported six Mac notes into the existing server DB. A second import
  inserted zero records and skipped six identical records.
- Verified every original record from BOTH databases is preserved exactly. Final
  counts: 47 notes, 47 tasks, 241 entities, 128 relationships; financial/calendar
  records unchanged. All 18 user table contents match the Mac snapshot.
- Mac `context_os.db` is now a mode-0400 read-only snapshot. Server DB is mode0600.
- Codex and Claude MCP configs now use SSH through `thoughtos-remote`; prior configs
  backed up and three old local-only MCP processes stopped.
- `thoughtos-sync` downloads a consistent validated snapshot; `--deploy` additionally
  fast-forwards Git and installs the package. Both paths tested against home-server.
- Found and fixed a pre-existing retrieval issue: an existing graph entity hid newer
  unextracted text matches. Queries now include both without creating/approving links.
- 13 focused tests passed on Mac and Linux. SSH MCP initialize, tool enumeration
  (13 tools), and query retrieval passed against the merged database. No paid model
  calls; cloud standardization and graph LLM extraction remain disabled.

## Entry points

- Canonical DB: `home-server:/home/hardik/Projects/ThoughtOS/context_os.db`.
- Server command: `/home/hardik/Projects/ThoughtOS/scripts/thoughtos-home`.
- Server `~/.local/bin/thoughtos` points to that wrapper (previous launcher backed up).
- Mac commands in `~/.local/bin`: `thoughtos-sync`, `thoughtos-remote`, `thoughtos`
  (the last is a convenience alias to the remote CLI).
- Mac sync config: `~/.config/thoughtos/sync.json`.
- Server preferences: `~/.config/thoughtos/server.env`, owner-only, local Ollama
  `gemma3:27b` preference retained but extraction disabled.

## Rollback / remaining work

Pre-cutover backups are under Mac
`~/.local/share/thoughtos/backups/home-cutover-20260920T191028Z/` and server
`~/Projects/ThoughtOS/backups/*before-merge-20260920T191028Z.db`.
The Mac directory also contains original Codex/Claude configuration copies. Restore
only after stopping writes and accounting for any NEW server records; blindly
restoring pre-merge DBs would discard later work.

Restart existing Claude/Codex sessions so they reload MCP configuration. Other
machines still need SSH access, the package and the documented MCP/sync config.
Existing HTTP/OpenClaw connectors have not been migrated or verified; SSH CLI/MCP
is the verified transport. No public listener/background worker was installed.
Automatic encrypted/off-host backup retention, offline writable replication,
periodic graph enrichment and nightly review remain separate work. See
`MULTI_MACHINE.md` for operation and limitations.
