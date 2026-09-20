# Desk direction and source readiness

## User feedback / product decision

- Notebook is primarily a tablet/pad experience.
- Zettel desk is for computers/laptops and is the current focus.
- Constellation is a later spatial/AR-glasses direction, not the current desktop priority.
- Connecting thoughts was too hard to discover; editing and tagging were unclear.
- New thought should use Cmd+N; find should use Cmd+F. Respect platform shortcut constraints and offer reliable fallback controls.
- From a thought, traversal should branch in multiple directions, not stop at a flat list.
- Existing Obsidian notes and Claude todo/reminder usage should inform the eventual real dataset.

## Implemented in prototype 02

Visible Edit/Tags/Connect actions, searchable source-labelled connection picker, new-and-connect flow, chip tags, global Find, focused chain traversal, back/forward and breadcrumbs, separately labelled shared-tag suggestions, keyboard reference and undo. Browser-only sample data is preserved from the first prototype. Notebook/constellation are parked rather than presented as equally mature desktop modes.

## Read-only local inventory

These are inspection-time counts, not live UI metrics. No note contents were imported or published.

Canonical SQLite database: `/home/hardik/Projects/ThoughtOS/context_os.db`.

| Source/table | Found |
|---|---:|
| ThoughtOS notes | 47 |
| ThoughtOS tasks | 47 (41 open, 6 done) |
| Extracted entities | 241 |
| Entity relationships | 128 |
| Explicit note_links | 0 |
| Registered vault_sources | 0 |
| Local Claude task JSON records | 18 (15 pending, 2 in_progress, 1 completed) |

No `.obsidian` vault directory was found in the searched local home locations (depth-limited search). This does not establish that no vault exists elsewhere; the user's Mac is a likely place to check after receiving its vault path/access. The old vault-sync planning document exists, but no working vault importer was found in the inspected current modules.

Local Claude task files are in `~/.claude/tasks`. Task records may belong to past sessions and are not proof of active reminders or scheduled notifications. Their relationship to the user's actual reminder workflow needs clarification. Counts from ThoughtOS and Claude must not be added together as unique tasks without deduplication.

The entity graph and note graph are different: relationships between entities cannot be presented as explicit user-authored note-to-note links. Shared entities/tags can generate *candidates*, which should be labelled and reviewed separately.

## Proposed integration sequence (not yet implemented)

1. **Read-only ThoughtOS adapter:** choose an approved owner/scope. Bring in notes and source-linked tasks; preserve raw text, stable IDs and provenance. Keep this separate from the current demo and browser edits. Add authentication/scoping before serving real content beyond loopback.
2. **Obsidian preview:** obtain the actual vault path or a user-selected export. Preview Markdown files, frontmatter tags, `[[wikilinks]]`, relative links and checkboxes. Preserve source paths and unresolved/ambiguous links. Do not write back to the vault.
3. **Claude/reminder source confirmation:** determine whether the user means Claude Code tasks, captured notes, Apple Reminders, or another service. Import only the chosen scope; preserve status and due dates without inventing a schedule.
4. **Unified provenance:** display source badges, stable source identifiers and “open original” paths where appropriate. Detect duplicates/updated versions before merging, with a review stage.
5. **Link proposals:** distinguish explicit source links, manual ThoughtOS links, and inferred/shared-topic suggestions. Do not silently promote suggestions into knowledge.
6. **Edits/sync later:** require an explicit policy for ownership, conflicts, deletions, retention and reversible writes before bidirectional syncing.

## What to test with the user

- Can they create a connection without opening Help?
- Are Tags and Connect clearly different?
- Can they follow three branches and return to the starting point?
- Does the connected-note view provide enough context without duplicating too much of the reader?
- Which sources should appear first: existing ThoughtOS notes, a selected Obsidian folder, or captured task notes?
