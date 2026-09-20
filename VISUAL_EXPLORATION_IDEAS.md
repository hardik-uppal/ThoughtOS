# ThoughtOS — Visual Exploration Ideas

Status: desk-first sample-data prototype 02 implemented; real-data integration is not enabled. User direction: notebook for tablets, Zettel desk for laptops/computers, constellation for a later AR/spatial experience. Focus now is intuitive desktop editing, tags, linking and branching traversal. See [`prototypes/visual-garden/README.md`](prototypes/visual-garden/README.md) for preview/tests and [`DESK_DIRECTION.md`](prototypes/visual-garden/DESK_DIRECTION.md) for source readiness.

## User's direction

ThoughtOS needs to be more visual and interactive. Traversing thoughts should be fun: like looking through a notebook of personal scribbles. A word cloud could offer an entry point into the notes.

Three requested visual directions:

1. **Futuristic digital graphs** — explore connected thoughts spatially.
2. **Notebook-style notes** — a personal notebook of scribbles, sketches and annotations.
3. **Zettelkasten-style chits** — small, tangible note cards to browse and connect.

## Proposed interpretation (assistant suggestions, awaiting validation)

Use one underlying note/link model with three interchangeable exploration views, not three disconnected collections. Carry the selected note and search/filter context across views.

- Graph: click an idea to reveal a small neighbourhood, follow labelled connections, and keep a breadcrumb trail. Avoid an overwhelming all-notes graph.
- Notebook: browse pages or spreads, arrange excerpts and annotations, and open a note to read/edit it. Handwritten styling is optional; body text stays legible.
- Cards: spread, stack, link and open chits. Show backlinks and distinguish user-created links from suggested connections.
- Topic/word cloud: clicking a topic filters or opens its relevant notes; it is a navigation tool rather than decoration. Explain whether word size represents frequency or another measure.

Shared requirements: search, accessible keyboard navigation, clear back/undo, readable text, reduced-motion support, and a list view fallback. Visual placement must not silently modify semantic links or note content.

## Suggested next step

Prototype the same 15–30 representative, non-sensitive notes in all three views. Test finding a known note, discovering a related idea, creating a link, and returning to the starting point. Then choose one view for the first functional implementation.

The dependency-free browser application in `prototypes/visual-garden/` is separate from the archived frontend. Version 01 explored three views; version 02 parks notebook/constellation and concentrates on the desk, focused thought chains and an accessible list. It retains 20 invented notes and prior browser edits, with explicit connection search, tag chips, global Find and branch/back/forward navigation. Canonical ThoughtOS data and syncing are untouched. Read-only inventory found 47 real notes, 41 open tasks, but zero explicit note links and no registered Obsidian vault. Validate source scope and authentication before connecting real data.

## Capture status

The ThoughtOS capture tool returned `fetch failed`, so this note was saved locally in the repository instead. It has not been confirmed ingested into ThoughtOS.
