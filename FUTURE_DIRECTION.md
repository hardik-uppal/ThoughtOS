# ThoughtOS — Future Direction

Status: recorded product direction, not implemented ingestion or permission to bulk-import private sources.

## User's vision

ThoughtOS should ingest many kinds of the user's own information and make them navigable in one place. Initial sources include Claude conversations, Codex conversations and Obsidian notes; other user-owned information can follow.

A simple organising engine should work over that personal corpus, using **user cues** to guide how things are sorted. The aim is not to force every capture through a complex form, or to substitute generic external knowledge for the user's actual material.

Original user thought:

> we should be able to ingest all sort of information to get organize here now i am thinking. with user quese to sort it. we sort thourgh user data alone. so claude codex chats. and obsidian notes etc. some where we need to run simaple organise engine, we would be building. record this thoguht as well and also this goes to fuure direction of thoughtos

## Related feedback already recorded

- The desk should be quieter and show more thoughts at a glance.
- Capture can be freeform or structured, selected through a setting.
- Suggest titles and tags from content, but allow correction.
- Search should understand tags and eventually meaning, not just literal titles.
- Semantically similar notes can sit nearby without implying a real connection.
- Save design experiments and restorable snapshots as useful evaluation data.
- Desktop Zettel desk is the current focus; notebook/tablet and constellation/AR are later device-specific experiences.

## Proposed organising-engine shape (assistant interpretation, to validate)

```text
Explicitly selected personal sources
  -> source adapters / import preview
  -> preserved originals with stable source references
  -> normalised items and thought-sized excerpts
  -> deduplication + search/embedding index
  -> proposed titles, tags, groupings and connections
  -> user cues, corrections and review
  -> desk / search / thought-chain exploration
```

### 1. User-owned sources, chosen explicitly

Start with approved Obsidian folders and selected Claude/Codex exports or supported local conversation stores. Later consider documents, bookmarks, images, voice notes, tasks and reminders where useful and authorised. “All sorts of information” is the intended scope of the product, not an instruction to read every private file now.

### 2. Preserve the original and its provenance

Keep raw source material separate from generated summaries or extracted thoughts. Store source type, stable source ID/path, timestamps, import revision and excerpt location so the user can open the original. Chat turns retain authorship: assistant suggestions are not automatically the user's beliefs, decisions or commitments.

### 3. Start with a small, inspectable engine

Use deterministic normalisation, explicit tags/wikilinks, duplicate checks and a local embedding index before adding complicated agents. Propose metadata and groupings rather than rewriting originals. Extraction models can later supply optional titles/summaries/tags, with their provenance recorded.

### 4. Let the user steer organisation

Potential cues include “this belongs with Wardrub,” “keep this separate,” “these mean the same thing,” “this is a decision, not a task,” and acceptance/rejection of a suggested link. These are examples to validate, not final UI contracts. Apply corrections visibly and reversibly. Do not silently treat every click or accidental navigation as ground-truth training feedback.

### 5. Separate proximity from knowledge

- Explicit source links and deliberate user-created connections are real links.
- Shared tags/entities and embedding similarity support discovery and suggestions.
- Similarity alone must not assert causality, agreement, identity, ownership or a task dependency.
- Preserve relationship direction/type when a source supplies it; a symmetric similarity score is not a directional relationship.

### 6. Preserve the meaning of each connection

Additional user feedback:

> connection name? that means something, its getting lost too

The current prototype stores only unlabelled, undirected note links. That loses the reason for connecting two thoughts. A future connection should preserve a meaningful relationship name and, where relevant, direction: “experiment **tests** hypothesis,” “finding **contradicts** assumption,” “decision **depends on** task,” or “idea **inspired by** observation.”

Proposed interaction: “Why connect these?” with a short free-text relationship label and optional reusable types. Show that label on the connection and during chain traversal, not only in a hidden metadata panel. A longer explanation/evidence can be optional. Allow an unnamed link during quick capture without inventing a meaning; it can be clarified later.

Proposed schema: an edge record with its own ID, source and target IDs, relationship type/label, optional explanation/evidence, direction, provenance and review status. Keep metadata on the edge rather than duplicating divergent labels on both notes. Reverse traversal should display the inverse reading or preserve the original arrow clearly. Existing unlabelled links must migrate without guessing their meaning.

Suggested relationship labels need context/evidence or explicit user confirmation. An embedding score alone cannot identify whether one thought supports, challenges or depends on another. Multiple distinct relationships between the same pair may be legitimate.

### 7. Evaluate with the user's actual workflow

With opt-in recording, preserve named experiment snapshots and completed-action feedback. Evaluate finding a known thought, discovering useful related material, correcting organisation and retracing a chain. Prototype state must remain distinct from canonical personal notes until an explicit integration step is approved.

## Boundaries for future implementation

- Preview sources and scope before ingestion; no automatic whole-account imports.
- Prefer local processing; get explicit approval before sending private text to external models.
- Record source permissions, handle secrets and third-party sensitive content, and support source removal/re-indexing.
- Imports should be incremental/idempotent with stable IDs, conflict reporting and reversible changes.
- Do not equate Claude/Codex session tasks with scheduled reminders or invent due dates.
- Raw content, extracted assertions and approved user knowledge need distinct provenance.
- Authentication and owner scoping precede serving real corpus contents beyond loopback.

## Next decision

Choose one small, representative, explicitly approved source sample. Prove capture -> organise -> find -> correct -> revisit before expanding connectors or adding automatic agents.
