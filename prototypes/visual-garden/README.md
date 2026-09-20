# ThoughtOS Thinking Desk — prototype 02

Desktop-first Zettel desk with **20 invented sample notes**. The earlier notebook/tablet and constellation/AR directions are parked while the desk's interaction model is polished. No live ThoughtOS/Obsidian/Claude data is loaded into the browser.

## Open it

**http://100.76.207.86:4321/** from a Tailscale-connected device.

Temporary user services:

- `thoughtos-visual-tailnet.service`: bound only to `100.76.207.86:4321`.
- `thoughtos-visual-prototype.service`: loopback preview on `127.0.0.1:4321`.

These are transient units, not enabled boot services. They can be inspected, restarted or stopped with `systemctl --user`. Logs: `journalctl --user -u thoughtos-visual-tailnet -n 30`.

HTTPS configuration required sudo and was not changed. Existing OpenClaw HTTPS routing remains untouched. Tailscale encrypts transport to the private IP. Do not publish/Funnel private note data.

Mac fallback while the loopback preview runs:

```sh
ssh -N -L 4321:127.0.0.1:4321 hardik@100.76.207.86
# Open http://127.0.0.1:4321 on the Mac.
```

## Run manually

Node 20+; no runtime dependencies, build step, model or API key:

```sh
cd ~/Projects/ThoughtOS/prototypes/visual-garden
npm start
# Or bind only to this home server's private Tailscale address:
HOST=100.76.207.86 npm start
```

Stop the matching existing service before starting another listener on the same address/port. `PORT` defaults to 4321. Serve only `public/`, never the repository root.

## Main interactions

1. **Open:** click a card's title/body to read it in the side pane.
2. **Edit / Tags:** visible actions in the reader and on cards. Tags have add/remove chips and reusable suggestions. Press Enter or comma to add; save the note to commit. Tags group/filter; they are not explicit links.
3. **Connect:** click Connect on any card. The chooser names the source card, searches all notes, excludes self/existing links, and previews matches. Select a match to create one undirected connection, visible on both cards. “Write a new thought and connect it” creates both in one undoable edit.
4. **Explore chain:** focus a thought between all its explicit connections. Click any neighbour to take another branch. A persistent breadcrumb trail has Back/Forward; taking a new branch discards forward navigation. Dotted breadcrumb separators mean a jump, not a link.
5. **Another angle:** suggestions based only on shared tags. Clearly marked NOT LINKED; viewing them does not create connections. Connect is a separate explicit action.
6. **Find:** searches across all collections, independently of desk filters. Arrow keys and Enter select a result. Opening a result enters chain exploration.
7. **Filter:** collection, word cloud and text filters combine on the desk. Chain exploration is global; it retains those filters for your return to All cards.
8. **Undo / Reset:** undo the last 30 data changes during this visit, or reset the demo with confirmation.

List is retained as a simple accessible alternative. Notebook and constellation are no longer in the active view switcher.

## Keyboard

| Keys | Action |
|---|---|
| Cmd/Ctrl+F, Cmd/Ctrl+K, or `/` | Find globally |
| N | New thought |
| Cmd/Ctrl+N | New thought only when the browser delivers this event to the page |
| E / T / C / X | Edit / Tags / Connect / Explore selected thought |
| Arrow keys + Enter | Move between cards, then open |
| Alt+Left / Alt+Right | Back / Forward in the thought trail |
| Cmd/Ctrl+S | Save the open editor |
| Escape | Close a dialog without saving |
| ? | Instructions and shortcut reference |

**Browser limitation:** Cmd/Ctrl+N is reserved by many browsers for a new window. A web page cannot reliably override browser/OS shortcuts. N outside an input and the visible New thought button remain reliable. Supporting native Cmd+N everywhere would require a desktop-app shell or another platform integration. Automated key events are not proof of OS-level interception.

Plain-letter shortcuts never trigger in text inputs or editable fields. Native text-editor undo is not overridden.

## Data / privacy boundary

Notes and links use browser `localStorage`, key `thoughtos.visual-garden.v1`. Version 02 preserves the version-01 data shape and existing saved edits. Each browser/origin has its own copy: the tailnet and SSH-tunnel URLs do not share edits. No backend writes or cross-device sync occur.

Malformed saved data is preserved and reported, not overwritten. Save failures leave edits in memory with a warning. Reset clears only the prototype storage key. View, filters, trail and undo history are session-local.

The server allowlists seven public assets, rejects writes, and cannot serve `.env`, SQLite or repository files. No external fonts, analytics or runtime libraries are loaded. Network access follows tailnet policy; this is not a production-authenticated personal vault. The Sources dialog describes possible adapters, not functioning integrations.

## Tests

```sh
npm test
```

Six unit tests cover data validation, filters, reciprocal links, tag counts, suggestion separation and invalid storage.

Browser tests use an existing Playwright installation (not a runtime dependency):

```sh
PLAYWRIGHT_MODULE=/home/hardik/Projects/wardrub/frontend/node_modules/playwright/index.mjs \
CHROME_PATH=/usr/bin/google-chrome \
PROTOTYPE_URL=http://100.76.207.86:4321 \
node tests/browser.mjs
```

Paths can be replaced by another installed Playwright/Chrome; without `PLAYWRIGHT_MODULE`, the test imports `playwright`. Tests verify desktop/mobile layout, a connection from an unselected card, searchable/keyboard chooser, reciprocal links, new connected notes, branch/back/forward, tags, global Cmd/Ctrl search, editor save shortcuts, ordinary typing, persistence, sanitization, undo, reset, corrupt storage and server isolation. Screenshots go to `/tmp/thoughtos-{desk,chain,connect,mobile-chain}-v2.png`.

## Source inventory and next step

See [`DESK_DIRECTION.md`](DESK_DIRECTION.md) for the user's platform direction and the read-only source inventory. Enough real notes exist to start, but entity relationships are not equivalent to explicit note links. Next integration should be a scoped, read-only ThoughtOS preview with provenance, then an explicitly selected Obsidian vault/export. Do not silently import all chat histories or convert task records into scheduled reminders.

Not implemented: live source adapters, sync, reminder scheduling, drag/stack layouts, handwriting, attachments, AI inference or production authentication.
