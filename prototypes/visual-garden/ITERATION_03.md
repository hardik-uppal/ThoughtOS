# Desk iteration 03 — implementation checkpoint

Based on baseline `06ea758`. This checkpoint contains iteration 03 and the first browser-feedback pass. The home-server deployment has not been updated. See `NEXT_SESSION.md` for the next requested change.

## Latest browser-feedback pass

- Replaced the large framed chain diagram with the full selected thought beside a grid of all other notes. Unconnected notes are interleaved from the first row; All / Unconnected / Connected selectors keep every note reachable, including notes without shared tags or model matches. Traversal and reading never create links.
- Removed the promotional heading and multiple toolbar rows. A single quiet toolbar leads straight into notes. Secondary tools are in the ••• menu.
- Collections drawer is collapsed by default, supports Escape/B, and closes after choosing a collection. Its background is inert while open.
- Moved tags out of the drawer into a dedicated, responsive word cloud with collision-checked weighted typography. Tag clicks reveal matching notes. The cloud updates from the current note tags.
- Replaced the fixed collection enum with validated user-provided names. Collections derive from saved notes; a new name appears when its first note is saved. Blank captures use Unsorted. Existing names normalise case and whitespace on assignment. No silent inference or automatic regrouping.
- `tests/feedback.mjs` verifies all five comments, above-fold unconnected notes at 1203×781, persistence, counts, cloud collisions, and 390px mobile layout. Both earlier browser suites still pass, including actual local embeddings and restore safety.

## Implemented

- Wider desk with compact cards, one toolbar and no persistent reader. Comfortable density remains available. Reader opens on a card click or “Read full thought”; Close/Escape returns the space to the desk. Plain `F` opens global Find.
- Freeform capture focuses on original text; structured capture exposes metadata. First-line/keyword suggestions are deterministic, explicitly reviewable, and never rewrite the note body. Unaccepted tags are not saved. Capture preference persists.
- Exact `#tag` / `tag:name` filters combine. Optional local `nomic-embed-text` embeddings add separately labelled meaning matches and nearby suggestions. Tags remain hard constraints; exact text matches remain first. Meaning/collection/recent arrangement is selectable; without vectors, nearby arrangement uses shared tags.
- Named and directional connections with one authoritative record per pair. Labels can be edited from either endpoint; arrows preserve the original source and target. Legacy links migrate as unnamed, undirected relationships without invented meanings.
- Named browser-local snapshots with notes, edges and settings; restore first saves a safety copy and aborts if that write fails. Restore a safety copy to reverse a restore. Optional completed-edit recording is off by default. No keystrokes are recorded.

## Storage and scope

The original `thoughtos.visual-garden.v1` key now stores envelope version 2. Before the first migrated write, the version-1 payload is backed up at `thoughtos.visual-garden.v1.pre-v3`. Old prototype code must not overwrite version-2 data. Malformed saved graphs are preserved and reported.

Snapshots use a separate localStorage key, `thoughtos.visual-garden.experiments.v1`. Ownership is the browser profile and origin; there is no cross-device sharing or server-side snapshot API. Keep up to 50 manual snapshots until explicitly deleted, and the latest 20 each of automatic and safety snapshots. Quota/corruption failures are surfaced; writes are atomic. Browser-data deletion removes these copies. Restore preserves the current recording/model-consent settings rather than opting the user in from a saved snapshot.

The earlier `experiment_store.py` SQLite draft remains unused. This iteration deliberately keeps snapshots in the existing browser-only data boundary; durable server storage and authenticated multi-device ownership are still future work. The canonical ThoughtOS database is never accessed.

## Local meaning search

Server opt-in: `ENABLE_SEMANTIC=1 npm start`. Browser opt-in: Settings or Find → local meaning matches. The endpoint sends bounded batches only to fixed loopback Ollama (`127.0.0.1:11434`), with model `nomic-embed-text` and `num_gpu: 0`. Embeddings are cached in browser memory. No cloud calls or corpus ingestion occurs. The Mac model was installed and exercised against invented sample notes; Ollama reported zero VRAM use.

Meaning search is a ranking aid, not proof of a relationship. Long notes are truncated to the model context window. The tiny sample corpus is sufficient for interaction testing, not a relevance benchmark. Unavailable/busy models show a status and retain text/tag search.

## Validation

- `npm test`: 17 unit tests for sample data, filters, metadata, graph migration/direction/validation, snapshot retention/deletion/failure safety, and embedding input/output validation.
- `tests/browser.mjs`: existing desk, keyboard, connection/traversal, edit, persistence, XSS escaping, undo/reset and mobile regression flows.
- `tests/iteration03.mjs`: freeform/structured capture, untouched body whitespace, reader/density, named directional edges, reversible snapshot restore, opt-in recording, quota failure, corrupt storage, real local semantic search, tag constraints, unavailable-model fallback and legacy-storage backup.
- API boundary checks reject cross-origin and invalid-Host embedding requests, deny arbitrary files and snapshot writes. Reviewed fixed upstream/model, body/batch limits, CPU setting, CSP, HTML escaping, stale-response suppression and browser-storage failure paths.
- Desktop/mobile, capture, connection, snapshots and semantic-search screenshots visually inspected. The sample-only prototype is not production authentication or a full security audit.

## Preserved earlier direction

Feedback IDs in canonical ThoughtOS: `a49db0ea-ba5e-4a9a-8023-7ab309f0271e`, `35b7ca1f-65ca-400c-a8a1-f4b7dfd1b4a8`, `388ab5d5-8f84-4dd7-a5dd-e4bb467d4a84`.

The home-server version-02 archive remains recorded at `/home/hardik/.local/share/thoughtos/visual-garden/releases/desk-v02-20260920T205813Z.tar.gz`, SHA256 `2b1125edd2afd0a9a9f028fa53adf84116d791100fadcb2d9c1af50aaf10ed44`. It is a code baseline, not a backup of browser edits.

Personal-source ingestion remains future direction, outside this UI iteration. Retain explicit scope and source/author provenance for any later import. See `../../FUTURE_DIRECTION.md`.
