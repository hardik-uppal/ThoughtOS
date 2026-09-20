# ThoughtOS across machines

## Deployment

The canonical live database is on `home-server` (Tailscale SSH alias,
`hardik@100.76.207.86`): `/home/hardik/Projects/ThoughtOS/context_os.db`.
The repository is `/home/hardik/Projects/ThoughtOS`; its package is installed in
that directory's `venv`. All live captures and graph changes belong on this host.

MCP clients launch `scripts/thoughtos-home mcp` through authenticated SSH stdio.
This runs a server-side process per client, sharing the canonical local SQLite
file. No public HTTP listener, background HTTP daemon, or socket worker is needed.
Do not expose the existing unauthenticated `mcp --port` transport publicly.

The Mac database at `~/ThoughtOS/context_os.db` becomes a **read-only snapshot**,
not a second writable primary. Old local MCP processes must be stopped during
cutover; restart Claude/Codex sessions to load their updated SSH configuration.
An offline server causes an explicit connection failure, never a silent local write.

## Everyday commands

After installing this package and the local sync config:

```sh
thoughtos-remote note "An original note"    # write on home-server
thoughtos-remote tasks                     # read live server data
thoughtos-remote stats
thoughtos-sync                             # pull a consistent read-only snapshot
thoughtos-sync --deploy                    # snapshot, fast-forward Git, install package
```

`thoughtos-sync` is deliberately NOT bidirectional database replication. It uses
SQLite's backup API (including committed WAL data), transfers over SSH, validates
integrity, then atomically replaces the local snapshot. It never uploads the local
snapshot over the live server database. Keep local snapshots on private encrypted
disks; they contain the whole personal database, not just notes.

`--deploy` refuses tracked server edits or divergent Git history; it does not
reset the server. Push reviewed code first. Restart MCP sessions after deployment
so existing processes use the new package. A failed deployment reports an error;
Git/package deployment is not an atomic release manager. Roll back code by checking
out the previous known commit and reinstalling the package; do not roll back the
live database casually. No background schedule is installed by these commands.

## Configuring another machine

Install the package from the desired Git ref and set up authenticated SSH/Tailscale
access (verify host keys). Put this in `~/.config/thoughtos/sync.json`, substituting
the local snapshot path for that machine:

```json
{
  "host": "home-server",
  "remote_repo": "/home/hardik/Projects/ThoughtOS",
  "remote_python": "/home/hardik/Projects/ThoughtOS/venv/bin/python",
  "remote_db": "/home/hardik/Projects/ThoughtOS/context_os.db",
  "remote_command": "/home/hardik/Projects/ThoughtOS/scripts/thoughtos-home",
  "branch": "fix/shared-database-path",
  "local_snapshot": "~/ThoughtOS/context_os.db"
}
```

Set the MCP command to `thoughtos-remote` with arguments `["mcp"]` (use its absolute
installed path if the harness doesn't inherit your PATH). Or use:

```text
command: ssh
args: [-T, -o, BatchMode=yes, home-server, /home/hardik/Projects/ThoughtOS/scripts/thoughtos-home, mcp]
```

Protect SSH keys and allow only trusted devices/accounts. This is single-owner
personal tooling, not an audited multi-tenant service. No API keys belong in Git.
The wrapper reads optional owner-only `~/.config/thoughtos/server.env`. Server model
preferences belong there rather than as uncommitted edits to package defaults.
LLM standardization/extraction and rule generation stay off until explicitly enabled.
The preserved home-server model preference is `gemma3:27b` on local Ollama.

## Initial database/history consolidation

The home-server's existing code history and uncommitted model preference were
preserved in `sync/home-server-preferences` and merged into the feature history.
The machine-specific model preference is then moved into environment configuration.
Code changes and history go through Git; private database content never does.

Before merging databases, take consistent snapshots of **both** databases into
owner-only backup directories, then stop local writers. The additive importer is:

```sh
python -m thoughtos_server.database_admin snapshot SOURCE.db BACKUP.db
python -m thoughtos_server.database_admin merge SOURCE-SNAPSHOT.db LIVE-TARGET.db
```

It inserts missing primary-key records, skips byte/value-identical records, and
rolls back the entire import on differing duplicate IDs, schema mismatches, missing
keys or failed integrity/foreign-key checks. It never deletes records, overwrites
conflicting content, guesses the newest timestamp or re-extracts notes. Review any
conflict manually; this is one-time conservative consolidation, not general sync.
The Mac's six seed notes share the existing `local@thoughtos` owner namespace.

## Storage, retention and limitations

- Configure one absolute `THOUGHTOS_DB_PATH`; notes, tasks and graph use it consistently.
- No live SQLite file syncing through Git/Drive/Dropbox/iCloud or SMB/NFS mounts.
- Local snapshots are refreshable caches, not historical/versioned backups.
- Keep periodic encrypted off-host backups with retention and restore testing. The
  migration makes point-in-time backups, but automatic backup scheduling/encryption
  and an off-host retention destination are still to be configured.
- SQLite is sufficient for a personal host and modest concurrency. PostgreSQL is
  appropriate if multiple API replicas/high write concurrency become necessary.
- Offline writable copies need stable operation IDs, an outbox, deletion tombstones
  and explicit conflict handling; not implemented here.
- Inferred graph changes still need review; this migration does not approve existing
  inferred knowledge or enable a periodic extraction/nightly-review worker.
- `.gitignore` covers DB files/sidecars. Historical `data/sunya.db` is tracked but
  empty; do not stage any private database or backup.

## Tests

`THOUGHTOS_LLM_ENABLED=0 .venv/bin/python -m unittest discover -s tests -v`

Disposable DB tests cover path isolation, capture/graph consistency, cloud-off
standardization, additive/idempotent merging, full conflict rollback, schema refusal
and snapshots containing committed WAL data. No provider calls are required.
