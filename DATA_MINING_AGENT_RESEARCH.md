# ThoughtOS Data Mining Agent (miner.py) - Research & Architecture

## Overview
ThoughtOS currently acts as a passive repository for notes, tasks, and system state (via `context_os.db`). To evolve ThoughtOS into an active **Graph Backend**, we need a background worker (`miner.py`) that continuously processes new unstructured data, extracts semantic meaning, identifies actionable TODOs, and proactively interacts with the user via OpenClaw.

## Goals
1. **Entity Extraction & Graph Linking:** Turn unstructured notes into a connected knowledge graph (Wiki-style links).
2. **TODO Mining:** Automatically detect implied or explicit tasks within notes.
3. **Proactive Clarification & Fulfillment:** Act as an ancillary system that reaches out to the user (via OpenClaw/Telegram) to ask clarifying questions or offer to execute the mined TODOs.

---

## Proposed Architecture

### Phase 1: The Miner (`miner.py`)
A continuous or cron-triggered background script running locally.
*   **Trigger:** Monitors `context_os.db` for new or updated notes that haven't been processed (`processed_flag = FALSE`).
*   **Engine:** Uses a local LLM via Ollama (e.g., `qwen` or `gemma`) or the primary OpenClaw API to ensure privacy and low cost.
*   **Output Structure:** For every note, the LLM is prompted to return a strict JSON schema:
    ```json
    {
      "entities": [
        {"name": "VTON", "type": "Project", "confidence": 0.95},
        {"name": "Himanshu", "type": "Person", "confidence": 0.99}
      ],
      "todos": [
        {"action": "Research index funds", "status": "pending", "context": "For upcoming blog post"}
      ],
      "questions_for_user": [
        "Did you mean Joffre Lakes when you wrote Jose lake?"
      ]
    }
    ```

### Phase 2: Graph Database Integration
Instead of migrating away from SQLite entirely, we can implement a lightweight relational graph within `context_os.db`:
*   `table_entities`: ID, Name, Type (Person, Project, Concept).
*   `table_edges`: Source_Note_ID, Target_Entity_ID, Relationship_Type.
*   `table_mined_tasks`: Mined TODOs linked to the Source_Note_ID.

When the ThoughtOS frontend renders a note, a middleware function highlights words that exist in `table_entities` and turns them into clickable wiki-links.

### Phase 3: The Proactive Ancillary Loop (OpenClaw Chat UI)
Since the primary interaction model is the **Chat UI (Telegram/Terminal via OpenClaw)**, there will be no dedicated web UI for this specific clarification flow. 
*   **The Bridge:** `miner.py` pushes the extracted `todos` and `questions_for_user` into OpenClaw's native Task Registry or Cron system.
*   **User Interaction (Chat UI):** OpenClaw handles reaching out to the user asynchronously in the chat thread.
*   **Fulfillment:** If the user agrees, OpenClaw executes the task and updates the ThoughtOS database via an API call or direct DB write.

### Phase 4: Rule Extraction & Learnable Cron (The Feedback Loop)
To prevent the agent from becoming a rigid, annoying bot, it must adapt to the user.
*   **Rule Extraction:** The LLM prompt will be expanded to extract `user_rules` (e.g., "Hardik prefers to book his own flights, just track the dates"). These rules are saved as structural nodes in the Graph, altering how the agent processes future notes.
*   **Learnable Cron:** The cron job that sends the daily digest or clarification questions must learn from the user's response patterns.
    *   *Pattern Logging:* OpenClaw tracks *when* the user responds (e.g., ignores at 9 AM, responds at 6 PM).
    *   *Graph Integration:* These behavioral patterns are saved into the Graph as metadata on the `Root/Self` node.
    *   *Adaptive Scheduling:* The cron dynamically shifts its execution window based on this historical behavioral graph to maximize response rates and minimize friction.

---

## Technical Implementation Steps

### 1. Database Schema Updates
Need to alter `context_os.db` to support:
- Processing status on notes.
- Tables for Entities, Edges (Links), and Mined Tasks.

### 2. Building `miner.py`
- Location: `/home/hardik/Projects/ThoughtOS/scripts/miner.py`
- Stack: Python, `sqlite3`, `langchain` or direct API calls to Ollama.
- Logic: Fetch unprocessed notes -> Send to LLM with JSON schema -> Parse response -> Insert into new DB tables -> Mark note as processed.

### 3. OpenClaw Handshake
- Build an integration where `miner.py` can inject payloads into `/home/hardik/.openclaw/cron/jobs.json` or directly into the OpenClaw delivery queue.
- Ensure OpenClaw knows how to route these "clarification questions" to the user's preferred channel (e.g., Telegram).

### 4. Frontend Updates
- Modify the ThoughtOS UI to parse notes through the Entity Dictionary before rendering, replacing known entity strings with `<a href="/entity/ID">Entity</a>`.

## Deep Critical Analysis (Devil's Advocate)

While the architecture sounds ideal, applying deep scrutiny reveals several critical failure points that must be addressed before building:

### 1. The SQLite Concurrency Trap (Database Locking)
*   **The Flaw:** `miner.py` running in the background while the ThoughtOS API is actively being used will cause SQLite `database is locked` errors. SQLite handles concurrent reads well, but concurrent writes (saving a new note vs. the miner updating entity tables) will crash the system.
*   **The Fix:** Enable `PRAGMA journal_mode=WAL;` (Write-Ahead Logging) in SQLite, and implement a robust retry/queue mechanism for `miner.py` so it never blocks the main app thread.

### 2. The Mutation Problem (State Drift)
*   **The Flaw:** The architecture assumes notes are written once. What happens when Hardik edits a note 3 hours later? The miner has already extracted "Jose Lake". The edit corrects it to "Joffre Lakes". Now the graph contains orphaned entities, ghost TODOs, and incorrect edges. 
*   **The Fix:** `miner.py` needs a complex reconciliation engine. If a note is updated, the miner must delete all previous edges/TODOs associated with that `note_id` and regenerate them, which risks deleting user-approved clarifications.

### 3. "Clippy Syndrome" (Notification Spam)
*   **The Flaw:** If the miner instantly pushes "Questions for user" to OpenClaw/Telegram for every ambiguous note, it will quickly become annoying. If every brain-dump generates 2 follow-up questions, the user will start ignoring the agent.
*   **The Fix:** Batching. OpenClaw should *never* interrupt immediately. Clarifications should be grouped into a single "Daily Review" payload sent via the existing OpenClaw cron (e.g., at 6:00 PM), allowing the user to approve/reject them in bulk.

### 4. Entity Explosion (The Tagging Trap)
*   **The Flaw:** LLMs are over-eager extractors. Without extreme guardrails, the LLM will extract useless concepts like "Friday", "My car", or "Good idea" as Entities. Within a month, `table_entities` will have 10,000 useless nodes, rendering the Graph meaningless.
*   **The Fix:** Strict Taxonomy Enforcement. The LLM prompt must inject the *existing* list of entities (or top 100 relevant ones via embeddings) and instruct the LLM: *"Map to these existing entities first. Only propose a NEW entity if it is a proper noun, project, or specific framework with >95% confidence."*

### 5. Context-Blind Execution
*   **The Flaw:** `miner.py` extracts: *"Research index funds."* OpenClaw offers to execute it. But OpenClaw executes it generically, completely unaware that in a *different* note, Hardik specified he only cares about "India vs. West" index funds.
*   **The Fix:** When OpenClaw prompts the user to fulfill a mined TODO, it must perform a RAG (Retrieval-Augmented Generation) pull across `context_os.db` using the linked `Entity_ID` to gain full context *before* executing the task.

---
## Revised Next Steps
1. **First Milestone:** Do not build the whole loop yet. Build a standalone script (`test_miner.py`) that just pulls the last 50 notes, runs the extraction prompt, and outputs to the terminal. We must tune the prompt to stop "Entity Explosion" before we let it touch a database.
