# ThoughtOS Server

Personal knowledge graph + note & task manager with MCP server for Claude Code.

**`pip install -e .` → `thoughtos start` → graph-aware coding agent**

## Features

- 📝 **Note intake** — captures rough notes, standardizes them, extracts tasks
- 🔗 **Knowledge graph** — extracts entities (people, projects, tools, concepts) and relationships
- 📏 **Learnable rules** — regex rules learned from LLM extractions, applied for free on future notes
- 🤖 **Multi-LLM** — Ollama (local), Gemini, or OpenAI for extraction, rule generation, and improvement
- 🛠️ **MCP server** — native Claude Code tools: `capture_note`, `search_entities`, `find_path`, etc.
- 🖥️ **CLI** — `thoughtos note "idea"`, `thoughtos tasks`, `thoughtos entities`, `thoughtos stats`

## Quick Start

```bash
# Install
cd ~/Projects/ThoughtOS
pip install -e .

# Start the API server
thoughtos start

# Or just use CLI directly (no server needed)
thoughtos note "Discussed LFM vs SigLIP with Rohan"
thoughtos tasks
thoughtos entities LFM
thoughtos stats
```

## Claude Code Integration

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "thoughtos": {
      "command": "thoughtos",
      "args": ["mcp"]
    }
  }
}
```

Then in Claude Code you get these tools:

| Tool | Description |
|------|-------------|
| `capture_note` | Save a note → extracts entities + tasks |
| `list_tasks` | Show open/done tasks |
| `update_task` | Toggle task status |
| `search_entities` | Search knowledge graph |
| `get_entity_web` | See everything connected to an entity |
| `find_path` | Find connections between entities |
| `list_rules` | Show extraction rules (active + pending) |
| `improve_extraction` | Re-extract with a different LLM |
| `graph_stats` | Knowledge graph statistics |

## Configuration

All via environment variables:

```bash
# LLM provider for extraction (default: ollama)
export THOUGHTOS_LLM_PROVIDER=ollama
export THOUGHTOS_LLM_MODEL=llama3.2:3b
export THOUGHTOS_LLM_BASE_URL=http://127.0.0.1:11434

# Different LLM for rule generation (optional, defaults to same as extraction)
export THOUGHTOS_RULE_LLM_PROVIDER=gemini
export THOUGHTOS_RULE_LLM_MODEL=gemini-2.0-flash
export THOUGHTOS_RULE_LLM_API_KEY=...

# Enable rule generation (LLM proposes regex rules from patterns)
export THOUGHTOS_RULE_GEN_ENABLED=1

# Disable LLM extraction (rule-engine + builtins only)
export THOUGHTOS_LLM_ENABLED=0

# Server
export THOUGHTOS_PORT=8000
export THOUGHTOS_DB_PATH="$HOME/ThoughtOS/context_os.db"
```

Use one absolute database path for every harness. Notes/tasks and the graph now
share that path, independent of the project working directory. Restart existing
MCP clients after upgrading. Code pushes do **not** sync private notes.

See [multi-machine storage and backup plan](MULTI_MACHINE.md) for a canonical
private server, SSH MCP access, and safe SQLite backup/migration. Remote hosting,
a daemon and synchronization are not installed yet.

## Extraction Pipeline

```
Raw Note
  │
  ├─→ Stage 1: Rule Engine (regex, free, deterministic)
  │     Uses stored rules + built-in heuristics
  │
  ├─→ Stage 2: LLM Extraction (optional, configurable provider)
  │     Ollama / Gemini / OpenAI → finds nuanced entities
  │
  ├─→ Stage 3: Deduplication (fuzzy matching → merged with graph)
  │
  └─→ Stage 4: Rule Generation (optional, different LLM can propose rules)
        Observes patterns → proposes regex rules → reviewed → Stage 1
        ┌─────────────────────────────────────────────────┐
        │  Rules feed back into Stage 1 for future notes  │
        │  thoughtos rerun → re-extract all notes         │
        └─────────────────────────────────────────────────┘
```

### Improving extraction over time

```bash
# Use a smarter model to review a specific note's extraction
thoughtos rerun <note_id> --llm gemini --model gemini-2.5-pro

# Accept proposed rules from LLM observations
thoughtos rules --all    # see pending proposals
# Accept via API: POST /api/extraction/rules/{rule_id}/accept

# Re-extract everything with current rules + LLM
thoughtos rerun
```

## API Endpoints

```
POST   /api/notes/intake          Capture note, extract entities + tasks
GET    /api/notes                  List/search notes
GET    /api/tasks                  List tasks (status=open/done)
PATCH  /api/tasks/:id             Update task status

GET    /api/graph/stats            Knowledge graph statistics
GET    /api/graph/entities         Search entities
GET    /api/graph/entities/:id     Get entity details
GET    /api/graph/entities/:id/web Entity neighborhood graph
GET    /api/graph/path             Shortest path between entities
GET    /api/graph/relationships    List relationships

GET    /api/extraction/rules       List extraction rules
POST   /api/extraction/rules/:id/toggle   Enable/disable rule
POST   /api/extraction/rules/:id/accept   Accept proposed rule
POST   /api/extraction/rerun      Re-run extraction
GET    /api/extraction/logs       Extraction logs

GET    /api/llm/check              Check LLM provider status
```

## Rules Table Schema

```sql
extraction_rules:
  rule_id          -- UUID
  pattern          -- regex pattern
  entity_type      -- person/project/tool/concept/document/event/org
  relation_type    -- discussed/uses/depends_on/part_of/etc.
  confidence       -- 0.0-1.0
  enabled          -- boolean
  accepted         -- reviewed and accepted
  source_llm       -- which LLM proposed it
  usage_count      -- how many times triggered
```

## Architecture

```
thoughtos_server/
├── config.py          Environment-based configuration
├── llm.py             Multi-provider LLM abstraction
├── graph_store.py     SQLite graph storage + traversal
├── extractor.py       Extraction pipeline (rules → LLM → dedup → rule gen)
├── note_intake.py     Note capture + standardization + extraction
├── main.py            FastAPI server
├── mcp_server.py      MCP server for Claude Code
└── cli.py             CLI tool
```
