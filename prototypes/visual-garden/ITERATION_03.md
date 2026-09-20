# Iteration 03 — recorded direction / work in progress

The live UI is still desk version 02. Do not present the next-iteration features as finished.

## Feedback preserved in canonical ThoughtOS

- `a49db0ea-ba5e-4a9a-8023-7ab309f0271e`: quieter/denser desk, tag/semantic search, N/F shortcuts, freeform vs structured capture, suggested metadata and restorable experiments.
- `35b7ca1f-65ca-400c-a8a1-f4b7dfd1b4a8`: personal-information ingestion and a small organising engine guided by user cues.
- `388ab5d5-8f84-4dd7-a5dd-e4bb467d4a84`: meaningful named connections; don't lose relationship semantics.

Broader direction: [`../../FUTURE_DIRECTION.md`](../../FUTURE_DIRECTION.md).

## Preserved baseline

Source/test/sample-data archive before version-03 edits:

`/home/hardik/.local/share/thoughtos/visual-garden/releases/desk-v02-20260920T205813Z.tar.gz`

SHA256: `2b1125edd2afd0a9a9f028fa53adf84116d791100fadcb2d9c1af50aaf10ed44`

This is a code baseline, not a snapshot of the user's browser edits. Existing browser state remains under `thoughtos.visual-garden.v1`; it has not been imported into SQLite.

## Preparatory changes only

- `public/model.js`: tag-aware `#tag` / `tag:name` search; preference defaults/normalisation; deterministic first-line/keyword metadata helper. The helper is not an AI model and is not wired into the editor yet.
- Downloaded local Ollama `nomic-embed-text` model (~274 MB). No embedding endpoint or semantic UI is wired up yet; no private corpus was sent to it. Prefer CPU inference for this small corpus so other GPU work is unaffected.
- `experiment_store.py`: draft capability-scoped, separate SQLite store. Not exposed by the current server or connected to browser controls. It must receive API validation, access scoping, tests and explicit opt-in recording controls before use.

## Outstanding implementation / validation

1. Quieter desktop layout, compact cards, reader on demand, F shortcut.
2. Freeform/structured setting with reviewable title/tag suggestions; preserve original text.
3. Optional local semantic find/nearby arrangement, labelled separately from explicit links; tag filters must remain hard constraints.
4. Named manual snapshots, reversible restore and opt-in completed-action recording. Keep the experiment store separate from canonical personal-note tables. Define ownership, retention, deletion and storage-failure handling.
5. Named/directional edges need a backwards-compatible schema, not two inconsistent labels in reciprocal note arrays. Do not guess meanings for old links.
6. Browser/model/API/store tests, security review and screenshots before claiming the iteration complete.

Personal-source ingestion is future product direction, not part of an authorised bulk import. Start with an explicitly approved sample and retain source/author provenance.
