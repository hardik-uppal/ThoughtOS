# ThoughtOS Thinking Desk — prototype 03

A desktop-first Zettel desk with 20 invented sample notes. No live ThoughtOS, Obsidian or Claude data is loaded. Notebook/tablet and constellation/AR remain separate future directions.

## Run locally

Node 20+, no npm runtime dependencies or build step:

```sh
cd prototypes/visual-garden
npm start
# http://127.0.0.1:4321
```

`HOST` and `PORT` select the listener. Only bind to loopback or an explicitly selected private Tailscale address; this sample prototype has no production authentication. Serve only the allowlisted public assets, never the repository root.

Optional local meaning search:

```sh
ollama pull nomic-embed-text
ENABLE_SEMANTIC=1 npm start
```

Enable **local meaning matches** in Find or Settings. Note text and query text are sent only to the fixed local Ollama instance on the machine running the server. CPU inference is requested; no cloud API or key is used. Without the model, text/tag search stays available. Find uses the documented [Ollama embedding endpoint](https://docs.ollama.com/api/embed).

The previously recorded home-server URL is `http://100.76.207.86:4321/`. The local iteration-03 edits do **not** update that deployment. The existing transient user units are `thoughtos-visual-tailnet.service` and `thoughtos-visual-prototype.service`; this iteration did not change them. Do not publish/Funnel private notes. Existing HTTPS/OpenClaw routing is untouched.

## Desk interactions

The main surface starts with notes beneath a single toolbar. Collections are in a collapsed drawer (☰ or B); snapshots, settings, undo and help are in the ••• menu.

- **Collections grow from notes:** use an existing collection name or type a new one in the editor. “Start a collection” opens its first note. The collection appears after saving, and its count grows as more notes use that name. Unassigned captures go to Unsorted. No empty collection is created by cancelling a draft.
- **Word cloud:** a separate, full-width browsing surface with weighted type, colour and slight rotations. Larger words appear in more notes. Click a word to see its matching notes below. Every tag remains reachable; above 60 tags, the remainder is accessible through the full tag list.

- **Read when needed:** click a card; close the reader with Close or Escape. Chain view offers “Read full thought”. Compact and comfortable card density are in Settings.
- **Capture:** New thought starts in freeform mode. Write the original text, optionally accept a suggested title/tag, or expand the details. Structured mode exposes title and metadata. Switching modes preserves the draft. Suggestions use first-line/keyword rules, not generated prose; original body whitespace is saved unchanged.
- **Connect:** every card has Connect. Choose another thought, optionally name why they relate, and mark direction if it matters. Both endpoints show the same relationship; Name in the reader edits it. Old links stay unnamed until reviewed.
- **Explore:** the complete thought sits in the center, with other notes on both sides and unconnected notes in the first row. Named connection reasons sit above their note titles; Add reason names a legacy link. Green means shared tags, lavender means local-model similarity, and neutral paper means elsewhere, each also labelled in text. Switch between All, Unconnected and Connected. Shared tags/local meaning influence order, but notes with no similarity remain available. Opening or reading one never creates a link. Back/Forward and breadcrumbs preserve the trail.
- **Find:** globally searches title/text and exact tags (`#tag`, `tag:name`), independently of desk filters. Multiple tags combine. Optional meaning matches follow exact matches, preserve tag constraints and are explicitly labelled. Desk filtering itself remains text/tag based.
- **Arrange:** recent, collection, or similar thoughts around the last selected note. Similar uses local vectors when available and shared tags otherwise.
- **Snapshots:** name the current experiment, restore one, restore its safety copy to go back, or delete a snapshot. Notes, named edges and desk preferences are included. Current model/recording consent is kept during restore.
- **Recording:** Settings can opt into completed-edit snapshots. No draft/keystroke recording. Keeps 20 automatic and 20 safety copies; up to 50 manual snapshots remain until deleted. Snapshots are local to this browser/address and are removed by clearing its storage.
- **Undo / reset:** undo the last 30 note/connection changes this visit. Reset requires confirmation and resets the sample desk while keeping snapshots.

## Keyboard

| Keys | Action |
|---|---|
| B | Open / close collections |
| N | New thought |
| Cmd/Ctrl+N | New thought when the browser delivers this reserved shortcut |
| F, Cmd/Ctrl+F, Cmd/Ctrl+K, `/` | Find globally |
| E / T / C / X | Edit / Tags / Connect / Explore selected thought |
| Arrows + Enter | Move between cards, then open |
| Alt+Left / Alt+Right | Back / Forward in the trail |
| Cmd/Ctrl+S | Save open note editor |
| Escape | Close dialog/reader; discard unsaved dialog draft |
| ? | Help |

Plain-letter shortcuts never intercept typing. Browsers may reserve Cmd/Ctrl+N for a new window; use N or the visible button as a reliable fallback. Native editor undo is preserved.

## Storage and boundaries

The `thoughtos.visual-garden.v1` localStorage key now contains `{ version: 2, notes }`. Version-1 edits migrate in memory and are backed up to `.pre-v3` before the first write. Existing malformed data is reported and left untouched. Failed saves retain the in-memory edit with a warning.

Each pair has one source-owned `connections` entry `{ target, label, directed }`; legacy string `links` become empty after migration. Both endpoints read the same record, so reverse traversal cannot invent or desynchronise a second label.

Preferences and snapshots use separate localStorage keys. No SQLite database is opened. `experiment_store.py` is an unused earlier draft, not an active API. Restoring requires a successfully saved recovery copy. Browser-only storage is not a durable or cross-device backup.

The server allowlists public assets. `/api/semantic` is the only POST endpoint, disabled by default, requiring matching Origin/Host and JSON requests. It bounds request/batch sizes and connects only to a fixed loopback model. No repository files, canonical notes, source adapters, external fonts, analytics or cloud services are exposed.

## Tests

```sh
npm test

# Set these to your installed Playwright and Chrome paths as needed.
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs \
CHROME_PATH=/path/to/chrome \
PROTOTYPE_URL=http://127.0.0.1:4321 node tests/browser.mjs

# Requires ENABLE_SEMANTIC=1 server and local nomic-embed-text model.
PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs \
CHROME_PATH=/path/to/chrome \
PROTOTYPE_URL=http://127.0.0.1:4321 node tests/iteration03.mjs
```

Run `tests/feedback.mjs` with the same browser environment to check the five browser-feedback changes, including growing collections, all unconnected notes, word-cloud overlap, and mobile layouts.

Screenshots are written to `/tmp/thoughtos-*-v3.png`. See `ITERATION_03.md` for implementation status, validation and limitations; `DESK_DIRECTION.md` for source-readiness notes.

Not implemented: real-source adapters/imports, cross-device sync, durable server snapshots, reminder scheduling, drag/stack layouts, handwriting, attachments or production authentication.
