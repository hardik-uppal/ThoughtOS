"""MCP (Model Context Protocol) server for Claude Code.

Exposes ThoughtOS as native tools in Claude Code:
  - capture_note: Save a note and extract entities/tasks
  - list_tasks: Show open/done tasks
  - update_task: Toggle task status
  - search_entities: Search the knowledge graph
  - get_entity_web: Get an entity and its neighborhood
  - find_path: Find connections between entities
  - list_rules: Show extraction rules
  - improve_extraction: Re-extract a note with a different LLM

Usage:
  thoughtos mcp          # start MCP server (stdio transport)
  thoughtos mcp --port   # start with SSE transport
  
Or add to Claude Code config (~/.claude.json):
  "mcpServers": {
    "thoughtos": {
      "command": "thoughtos",
      "args": ["mcp"]
    }
  }
"""

from __future__ import annotations

import json
import sys
import os
import sqlite3
from typing import Any, Dict, Optional

from .config import load_config, ExtractionConfig
from .graph_store import GraphStore
from .note_intake import intake_note, rerun_extraction_for_note, rerun_all_extractions


config = load_config()
graph = GraphStore(config.db_path)
graph.init()


# --- Tool handlers ---


def handle_capture_note(params: Dict) -> Dict:
    """Capture a note, extract entities and tasks."""
    text = params.get("text", "")
    note_type = params.get("noteType", "auto")
    source = params.get("source", "claude-code")

    if not text.strip():
        return {"content": [{"type": "text", "text": "Error: text is required"}]}

    result = intake_note(
        user_id="local@thoughtos",
        text=text,
        source=source,
        note_type=note_type,
        extract_entities=True,
        config=config.extraction,
        db_path=config.db_path,
    )

    note = result.get("note", {})
    tasks = result.get("tasks", [])
    extraction = result.get("extraction", {})

    lines = [f"🧠 Captured: {note.get('title', 'Untitled')}"]
    if note.get("summary"):
        lines.append(f"Summary: {note['summary']}")

    if tasks:
        lines.append("\nTasks:")
        for t in tasks:
            due = f" · due {t['due_date']}" if t.get("due_date") else ""
            prio = f" {t.get('priority', '')}" if t.get("priority") else ""
            lines.append(f"- [ ] {t['title']}{prio}{due}")
    else:
        lines.append("\nNo tasks extracted.")

    if extraction.get("entities"):
        entities = extraction["entities"]
        lines.append(f"\n🔗 Entities extracted: {len(entities)}")
        for e in entities[:10]:
            lines.append(f"  - {e['name']} ({e.get('type', '?')})")

    if extraction.get("rules_proposed"):
        lines.append(f"\n📏 Rules proposed: {len(extraction['rules_proposed'])}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": result,
    }


def handle_list_tasks(params: Dict) -> Dict:
    """List tasks."""
    status = params.get("status", "open")
    limit = params.get("limit", 20)

    try:
        from logic.sql_engine import list_tasks
    except ImportError:
        return {"content": [{"type": "text", "text": "Error: logic.sql_engine not found. Run from ThoughtOS directory."}]}
    tasks = list_tasks("local@thoughtos", status=status, limit=limit)

    if not tasks:
        return {"content": [{"type": "text", "text": "No tasks found."}]}

    checkbox = "x" if status == "done" else " "
    lines = [f"🧠 ThoughtOS tasks ({status}):\n"]
    for t in tasks:
        due = f" · due {t['due_date']}" if t.get("due_date") else ""
        lines.append(f"- [{checkbox}] {t['title']}{due}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"tasks": tasks},
    }


def handle_update_task(params: Dict) -> Dict:
    """Update task status."""
    task_id = params.get("taskId", "")
    status = params.get("status", "done")

    try:
        from logic.sql_engine import update_task_status
    except ImportError:
        return {"content": [{"type": "text", "text": "Error: logic.sql_engine not found."}]}
    task = update_task_status("local@thoughtos", task_id, status)

    if not task:
        return {"content": [{"type": "text", "text": f"Task {task_id} not found."}]}

    return {
        "content": [{"type": "text", "text": f"Task '{task.get('title', task_id)}' marked {status}."}],
        "details": {"task": task},
    }


def handle_search_entities(params: Dict) -> Dict:
    """Search the knowledge graph for entities."""
    query = params.get("query", "")
    entity_type = params.get("entityType")
    limit = params.get("limit", 20)

    entities = graph.find_entities(
        user_id="local@thoughtos",
        query=query if query else None,
        entity_type=entity_type,
        limit=limit,
    )

    if not entities:
        return {"content": [{"type": "text", "text": "No entities found."}]}

    lines = [f"🔗 Entities ({len(entities)}):\n"]
    for e in entities:
        aliases = ""
        if e.get("aliases"):
            alias_list = e["aliases"] if isinstance(e["aliases"], list) else json.loads(str(e["aliases"]))
            if alias_list:
                aliases = f" (aka {', '.join(alias_list[:3])})"
        lines.append(f"  - {e['name']} [{e.get('type', '?')}]{aliases}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"entities": entities},
    }


def handle_get_entity_web(params: Dict) -> Dict:
    """Get an entity and its graph neighborhood."""
    entity_id = params.get("entityId", "")
    max_hops = params.get("maxHops", 2)

    web = graph.get_entity_web(entity_id, max_hops)

    if not web["entity"]:
        return {"content": [{"type": "text", "text": "Entity not found."}]}

    entity = web["entity"]
    lines = [
        f"🔗 {entity['name']} [{entity.get('type', '?')}]\n",
        f"Connected to {len(web['neighbors'])} entities via {len(web['relationships'])} relationships:\n",
    ]

    for rel in web["relationships"]:
        src = rel["source_entity_id"]
        tgt = rel["target_entity_id"]
        src_name = next((n["name"] for n in web["neighbors"] if n["entity_id"] == src), src[:8])
        tgt_name = next((n["name"] for n in web["neighbors"] if n["entity_id"] == tgt), tgt[:8])
        if src == entity_id:
            lines.append(f"  → {rel['relation_type']} → {tgt_name}")
        else:
            lines.append(f"  {src_name} → {rel['relation_type']} →")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": web,
    }


def handle_find_path(params: Dict) -> Dict:
    """Find path between two entities."""
    source_id = params.get("sourceId", "")
    target_id = params.get("targetId", "")
    max_hops = params.get("maxHops", 4)

    path = graph.find_path(source_id, target_id, max_hops)

    if not path:
        return {"content": [{"type": "text", "text": "No path found between these entities."}]}

    lines = [f"🔗 Path found ({len(path)} hops):\n"]
    for i, step in enumerate(path):
        src_name = graph.get_entity(step["source_entity_id"])
        tgt_name = graph.get_entity(step["target_entity_id"])
        src = src_name["name"] if src_name else step["source_entity_id"][:8]
        tgt = tgt_name["name"] if tgt_name else step["target_entity_id"][:8]
        lines.append(f"  {i+1}. {src} → {step['relation_type']} → {tgt}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"path": path},
    }


def handle_list_rules(params: Dict) -> Dict:
    """List extraction rules."""
    rule_type = params.get("ruleType")
    include_pending = params.get("includePending", False)

    rules = graph.list_rules(
        enabled_only=True,
        accepted_only=not include_pending,
        rule_type=rule_type,
    )

    if not rules:
        return {"content": [{"type": "text", "text": "No extraction rules found."}]}

    pending = [r for r in rules if not r.get("accepted")]
    active = [r for r in rules if r.get("accepted")]

    lines = [f"📏 Extraction rules: {len(active)} active"]

    if active:
        lines.append("")
        for r in active:
            lines.append(f"  - `{r['pattern']}` → {r.get('entity_type') or r.get('relation_type', '?')} "
                         f"(used {r.get('usage_count', 0)}x)")

    if pending:
        lines.append(f"\n📝 Pending review ({len(pending)}):")
        for r in pending:
            by = f" by {r.get('source_llm', '?')}" if r.get("source_llm") else ""
            lines.append(f"  - `{r['pattern']}` → {r.get('entity_type', '?')}{by}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"rules": rules},
    }


def handle_improve_extraction(params: Dict) -> Dict:
    """Re-extract a note with a different LLM."""
    note_id = params.get("noteId", "")
    llm_provider = params.get("llmProvider")
    llm_model = params.get("llmModel")

    if not note_id:
        return {"content": [{"type": "text", "text": "Error: noteId is required"}]}

    # Get note text
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT note_id, raw_text, title FROM notes WHERE note_id = ?",
        (note_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {"content": [{"type": "text", "text": f"Note {note_id} not found."}]}

    result = rerun_extraction_for_note(
        note_id=row["note_id"],
        note_text=row["raw_text"],
        user_id="local@thoughtos",
        config=config.extraction,
        db_path=config.db_path,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )

    lines = [
        f"🔍 Re-extracted: {row['title']}",
        f"LLM: {result.get('improved_with', 'default')}",
        f"Previous: {result.get('previous_extraction', 'none')}",
        f"New: {len(result.get('entities', []))} entities, {len(result.get('relationships', []))} relationships",
    ]

    if result.get("rules_proposed"):
        lines.append(f"Rules proposed: {len(result['rules_proposed'])}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": result,
    }


def handle_graph_stats(params: Dict) -> Dict:
    """Get knowledge graph statistics."""
    stats = graph.get_stats()
    lines = [
        "🧠 Knowledge Graph Stats:",
        f"  Entities: {stats['entity_count']}",
        f"  Relationships: {stats['relationship_count']}",
        f"  Rules: {stats['rule_count']}",
        f"  Notes extracted: {stats.get('notes_extracted', '?')}",
        f"  Notes stale: {stats.get('notes_stale', '?')}",
        "",
        "Entity types:",
    ]
    for etype, count in stats.get("entity_types", {}).items():
        lines.append(f"  {etype}: {count}")

    lines.append("")
    lines.append("Relationship types:")
    for rtype, count in stats.get("relation_types", {}).items():
        lines.append(f"  {rtype}: {count}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": stats,
    }


def handle_get_working_context(params: Dict) -> Dict:
    """Pull everything relevant to a task/topic."""
    query = params.get("query", "")
    max_entities = params.get("maxEntities", 10)
    max_notes = params.get("maxNotes", 5)
    include_timeline = params.get("includeTimeline", True)

    if not query.strip():
        return {"content": [{"type": "text", "text": "Error: query is required"}]}

    # Step 1: Find matching entities
    entities = graph.find_entities(
        user_id="local@thoughtos",
        query=query,
        limit=max_entities,
    )

    if not entities:
        return {
            "content": [{
                "type": "text",
                "text": f"No entities found for '{query}'. Try capturing notes about this topic first."
            }],
        }

    lines = [f"🧠 Working context for: {query}\n"]
    lines.append(f"Found {len(entities)} related entities:\n")

    # Step 2: For each entity, get its web
    all_related = {}
    all_note_ids = set()

    for e in entities[:5]:  # top 5 entities
        web = graph.get_entity_web(e["entity_id"], max_hops=1)
        for n in web.get("neighbors", []):
            all_related[n["entity_id"]] = n
        # Collect note IDs
        note_id = e.get("source_note_id")
        if note_id:
            all_note_ids.add(note_id)
        for r in web.get("relationships", []):
            nid = r.get("source_note_id")
            if nid:
                all_note_ids.add(nid)

    # Step 3: Build entity summary
    for e in entities:
        aliases_str = ""
        if e.get("aliases"):
            alias_list = e["aliases"] if isinstance(e["aliases"], list) else []
            if alias_list:
                aliases_str = f" (aka {', '.join(alias_list[:3])})"

        # Get direct relationships
        rels = graph.find_relationships(entity_id=e["entity_id"], limit=10)
        rel_summary = ""
        if rels:
            rel_parts = []
            for r in rels[:5]:
                other_id = r["target_entity_id"] if r["source_entity_id"] == e["entity_id"] else r["source_entity_id"]
                other = all_related.get(other_id) or graph.get_entity(other_id)
                other_name = other["name"] if other else other_id[:8]
                direction = "→" if r["source_entity_id"] == e["entity_id"] else "←"
                rel_parts.append(f"{direction} {r['relation_type']} {direction} {other_name}")
            rel_summary = " | ".join(rel_parts)

        lines.append(f"  ▸ {e['name']} [{e.get('type', '?')}]{aliases_str}")
        if rel_summary:
            lines.append(f"    {rel_summary}")

    # Step 4: Pull related notes
    if all_note_ids:
        import sqlite3
        conn = sqlite3.connect(config.db_path)
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" for _ in all_note_ids)
        rows = conn.execute(
            f"SELECT note_id, title, summary, created_at FROM notes WHERE note_id IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",
            list(all_note_ids) + [max_notes],
        ).fetchall()
        conn.close()

        if rows:
            lines.append(f"\n📝 Related notes ({min(len(rows), max_notes)}):")
            for row in rows:
                ts = row["created_at"][:10] if row["created_at"] else "?"
                lines.append(f"  - [{ts}] {row['title']}")
                summary = row["summary"]
                if summary:
                    lines.append(f"    {summary[:120]}")

    # Step 5: Suggest next actions
    lines.append("\n💡 Suggestions:")
    if entities:
        lines.append(f"  - Use `query_notes` with '{entities[0]['name']}' to find all related notes")
    if len(entities) > 1:
        lines.append(f"  - Use `find_path` between '{entities[0]['name']}' and '{entities[1]['name']}' to see connections")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"entities": entities, "related": list(all_related.values())[:20]},
    }


def handle_find_related_notes(params: Dict) -> Dict:
    """Find notes connected through shared entities."""
    entity_ids = params.get("entityIds", [])
    limit = params.get("limit", 10)

    if not entity_ids:
        return {"content": [{"type": "text", "text": "Error: entityIds is required"}]}

    # Get entity names for display
    entity_names = []
    for eid in entity_ids:
        e = graph.get_entity(eid)
        if e:
            entity_names.append(e["name"])

    # Find notes that reference these entities
    import sqlite3
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row

    # Get source_note_ids from all these entities
    all_note_ids = set()
    for eid in entity_ids:
        rows = conn.execute(
            "SELECT DISTINCT source_note_id FROM entities WHERE entity_id = ?",
            (eid,),
        ).fetchall()
        for r in rows:
            if r["source_note_id"]:
                all_note_ids.add(r["source_note_id"])

    # Also find notes connected through relationships
    for eid in entity_ids:
        rows = conn.execute(
            "SELECT DISTINCT source_note_id FROM relationships WHERE source_entity_id = ? OR target_entity_id = ?",
            (eid, eid),
        ).fetchall()
        for r in rows:
            if r["source_note_id"]:
                all_note_ids.add(r["source_note_id"])

    if not all_note_ids:
        return {
            "content": [{
                "type": "text",
                "text": f"No notes found connecting {', '.join(entity_names)}."
            }],
        }

    # Fetch notes
    placeholders = ",".join("?" for _ in all_note_ids)
    rows = conn.execute(
        f"SELECT note_id, title, summary, note_type, created_at FROM notes WHERE note_id IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",
        list(all_note_ids) + [limit],
    ).fetchall()
    conn.close()

    lines = [f"📝 Notes connecting {', '.join(entity_names)} ({len(rows)}):\n"]
    for row in rows:
        ts = row["created_at"][:10] if row["created_at"] else "?"
        ntype = f" [{row['note_type']}]" if row["note_type"] else ""
        lines.append(f"  - [{ts}]{ntype} {row['title']}")
        if row["summary"]:
            lines.append(f"    {row['summary'][:150]}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"notes": [dict(r) for r in rows]},
    }


def handle_entity_timeline(params: Dict) -> Dict:
    """Get temporal history of an entity."""
    entity_id = params.get("entityId", "")
    limit = params.get("limit", 20)

    if not entity_id:
        return {"content": [{"type": "text", "text": "Error: entityId is required"}]}

    entity = graph.get_entity(entity_id)
    if not entity:
        return {"content": [{"type": "text", "text": f"Entity {entity_id} not found."}]}

    # Get all relationships involving this entity, sorted by time
    rels = graph.find_relationships(entity_id=entity_id, limit=limit)

    # Get extraction logs for notes mentioning this entity
    import sqlite3
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row

    # Find notes where this entity appears
    note_rows = conn.execute(
        """SELECT DISTINCT n.note_id, n.title, n.created_at, n.summary
           FROM notes n
           INNER JOIN entities e ON n.note_id = e.source_note_id
           WHERE e.entity_id = ?
           ORDER BY n.created_at DESC
           LIMIT ?""",
        (entity_id, limit),
    ).fetchall()
    conn.close()

    lines = [f"⏳ Timeline for: {entity['name']} [{entity.get('type', '?')}]\n"]

    if not note_rows and not rels:
        lines.append("  No timeline entries yet.")
    else:
        if note_rows:
            lines.append("📝 Mentioned in notes:")
            for row in note_rows:
                ts = row["created_at"][:10] if row["created_at"] else "?"
                lines.append(f"  - [{ts}] {row['title']}")

        if rels:
            lines.append(f"\n🔗 Relationships ({len(rels)}):")
            for r in rels[:15]:
                other_id = r["target_entity_id"] if r["source_entity_id"] == entity_id else r["source_entity_id"]
                other = graph.get_entity(other_id)
                other_name = other["name"] if other else other_id[:8]
                ts = r.get("created_at", "?")[:10] if r.get("created_at") else "?"
                direction = "→" if r["source_entity_id"] == entity_id else "←"
                lines.append(f"  - [{ts}] {direction} {r['relation_type']} {direction} {other_name}")

    # First/last seen
    if entity.get("created_at"):
        lines.append(f"\n  First seen: {entity['created_at'][:10]}")
    if entity.get("last_seen_at"):
        lines.append(f"  Last seen: {entity['last_seen_at'][:10]}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"entity": entity, "notes": [dict(r) for r in note_rows], "relationships": rels},
    }


def handle_query_notes(params: Dict) -> Dict:
    """Search notes by entity reference."""
    entity_name = params.get("entityName", "")
    entity_type = params.get("entityType")
    limit = params.get("limit", 10)

    if not entity_name.strip():
        return {"content": [{"type": "text", "text": "Error: entityName is required"}]}

    # First find the entity (by name or alias)
    entities = graph.find_entities(
        user_id="local@thoughtos",
        query=entity_name,
        entity_type=entity_type,
        limit=5,
    )

    if not entities:
        # Try full-text search in notes directly
        import sqlite3
        conn = sqlite3.connect(config.db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT note_id, title, summary, note_type, created_at
               FROM notes WHERE user_id = ? AND (raw_text LIKE ? OR title LIKE ?)
               ORDER BY created_at DESC LIMIT ?""",
            ('local@thoughtos', f"%{entity_name}%", f"%{entity_name}%", limit),
        ).fetchall()
        conn.close()

        if not rows:
            return {
                "content": [{
                    "type": "text",
                    "text": f"No notes or entities found for '{entity_name}'."
                }],
            }

        lines = [f"📝 Notes mentioning '{entity_name}' ({len(rows)}):\n"]
        for row in rows:
            ts = row["created_at"][:10] if row["created_at"] else "?"
            lines.append(f"  - [{ts}] {row['title']}")
            if row["summary"]:
                lines.append(f"    {row['summary'][:150]}")

        return {
            "content": [{"type": "text", "text": "\n".join(lines)}],
            "details": {"notes": [dict(r) for r in rows]},
        }

    # Entity found — get all notes connected
    import sqlite3
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row

    all_note_ids = set()
    for e in entities:
        # Direct source notes
        if e.get("source_note_id"):
            all_note_ids.add(e["source_note_id"])
        # Notes from relationships
        rel_rows = conn.execute(
            "SELECT DISTINCT source_note_id FROM relationships WHERE source_entity_id = ? OR target_entity_id = ?",
            (e["entity_id"], e["entity_id"]),
        ).fetchall()
        for r in rel_rows:
            if r["source_note_id"]:
                all_note_ids.add(r["source_note_id"])

    # Keep unreviewed/unextracted notes discoverable beside existing entities.
    # Lexical retrieval does not create or approve graph links.
    text_rows = conn.execute(
        "SELECT note_id FROM notes WHERE user_id = ? AND (raw_text LIKE ? OR title LIKE ?) ORDER BY created_at DESC LIMIT ?",
        ('local@thoughtos', f"%{entity_name}%", f"%{entity_name}%", limit),
    ).fetchall()
    all_note_ids.update(r['note_id'] for r in text_rows)

    if not all_note_ids:
        conn.close()
        return {
            "content": [{
                "type": "text",
                "text": f"Entity '{entity_name}' found but no notes connected yet."
            }],
        }

    placeholders = ",".join("?" for _ in all_note_ids)
    rows = conn.execute(
        f"SELECT note_id, title, summary, note_type, created_at FROM notes WHERE user_id = ? AND note_id IN ({placeholders}) ORDER BY created_at DESC LIMIT ?",
        ['local@thoughtos'] + list(all_note_ids) + [limit],
    ).fetchall()
    conn.close()

    lines = [f"📝 Notes for '{entities[0]['name']}' [{entities[0].get('type', '?')}] ({len(rows)}):\n"]
    for row in rows:
        ts = row["created_at"][:10] if row["created_at"] else "?"
        ntype = f" [{row['note_type']}]" if row["note_type"] else ""
        lines.append(f"  - [{ts}]{ntype} {row['title']}")
        if row["summary"]:
            lines.append(f"    {row['summary'][:150]}")

    return {
        "content": [{"type": "text", "text": "\n".join(lines)}],
        "details": {"entities": entities, "notes": [dict(r) for r in rows]},
    }


# --- MCP Protocol ---

TOOLS = [
    {
        "name": "capture_note",
        "description": "Capture a note into ThoughtOS. Extracts entities into the knowledge graph and creates tasks automatically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Raw note text to capture"},
                "noteType": {"type": "string", "description": "auto, meeting_note, quick_note, task_dump"},
                "source": {"type": "string", "description": "Source label (default: claude-code)"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "list_tasks",
        "description": "List ThoughtOS tasks.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "open, done, all"},
                "limit": {"type": "number", "description": "Maximum tasks to return"},
            },
        },
    },
    {
        "name": "update_task",
        "description": "Update task status (toggle done/open).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "taskId": {"type": "string", "description": "Task ID to update"},
                "status": {"type": "string", "description": "done or open"},
            },
            "required": ["taskId"],
        },
    },
    {
        "name": "search_entities",
        "description": "Search the knowledge graph for entities (people, projects, tools, concepts, etc.).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "entityType": {"type": "string", "description": "Filter by type: person, project, tool, concept, etc."},
                "limit": {"type": "number", "description": "Max results"},
            },
        },
    },
    {
        "name": "get_entity_web",
        "description": "Get an entity and everything connected to it in the knowledge graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entityId": {"type": "string", "description": "Entity ID"},
                "maxHops": {"type": "number", "description": "How many hops to traverse (default: 2)"},
            },
            "required": ["entityId"],
        },
    },
    {
        "name": "find_path",
        "description": "Find the shortest connection path between two entities in the graph.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sourceId": {"type": "string", "description": "Source entity ID"},
                "targetId": {"type": "string", "description": "Target entity ID"},
                "maxHops": {"type": "number", "description": "Maximum hops to search (default: 4)"},
            },
            "required": ["sourceId", "targetId"],
        },
    },
    {
        "name": "list_rules",
        "description": "List extraction rules. Shows active rules and pending proposals.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ruleType": {"type": "string", "description": "entity or relationship"},
                "includePending": {"type": "boolean", "description": "Include rules pending review"},
            },
        },
    },
    {
        "name": "improve_extraction",
        "description": "Re-extract entities from a note using a different LLM to improve results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "noteId": {"type": "string", "description": "Note ID to re-extract"},
                "llmProvider": {"type": "string", "description": "LLM provider: ollama, gemini, openai"},
                "llmModel": {"type": "string", "description": "LLM model name (e.g., llama3.2:3b, gpt-4o)"},
            },
            "required": ["noteId"],
        },
    },
    {
        "name": "graph_stats",
        "description": "Get knowledge graph statistics.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_working_context",
        "description": "Get everything relevant to a task/topic: connected entities, recent notes, related projects. Use this when starting work on something to pull in context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What you're working on — entity name, project, topic, or free-text search"},
                "maxEntities": {"type": "number", "description": "Max entities to return (default: 10)"},
                "maxNotes": {"type": "number", "description": "Max related notes (default: 5)"},
                "includeTimeline": {"type": "boolean", "description": "Include temporal history (default: true)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "find_related_notes",
        "description": "Find notes connected through shared entities. 'What notes mention both Rohan and the culling pipeline?'",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entityIds": {"type": "array", "items": {"type": "string"}, "description": "Entity IDs to cross-reference"},
                "limit": {"type": "number", "description": "Max notes to return"},
            },
            "required": ["entityIds"],
        },
    },
    {
        "name": "entity_timeline",
        "description": "Get temporal history of an entity — when it was mentioned, in which notes, with whom.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entityId": {"type": "string", "description": "Entity ID"},
                "limit": {"type": "number", "description": "Max timeline entries"},
            },
            "required": ["entityId"],
        },
    },
    {
        "name": "query_notes",
        "description": "Search notes by entity reference. Find all notes that mention an entity (by name or alias).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entityName": {"type": "string", "description": "Entity name to search for in notes"},
                "entityType": {"type": "string", "description": "Optional: filter by entity type"},
                "limit": {"type": "number", "description": "Max notes"},
            },
            "required": ["entityName"],
        },
    },
]

HANDLERS = {
    "capture_note": handle_capture_note,
    "list_tasks": handle_list_tasks,
    "update_task": handle_update_task,
    "search_entities": handle_search_entities,
    "get_entity_web": handle_get_entity_web,
    "find_path": handle_find_path,
    "list_rules": handle_list_rules,
    "improve_extraction": handle_improve_extraction,
    "graph_stats": handle_graph_stats,
    "get_working_context": handle_get_working_context,
    "find_related_notes": handle_find_related_notes,
    "entity_timeline": handle_entity_timeline,
    "query_notes": handle_query_notes,
}


def run_mcp_stdio():
    """Run MCP server over stdin/stdout (for Claude Code)."""
    # Ensure graph is initialized
    graph.init()

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            request = json.loads(line)
            method = request.get("method", "")
            req_id = request.get("id")

            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                        },
                        "serverInfo": {
                            "name": "thoughtos",
                            "version": "0.1.0",
                        },
                    },
                }
            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"tools": TOOLS},
                }
            elif method == "tools/call":
                tool_name = request.get("params", {}).get("name", "")
                tool_args = request.get("params", {}).get("arguments", {})
                handler = HANDLERS.get(tool_name)
                if handler:
                    try:
                        result = handler(tool_args)
                        response = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": result,
                        }
                    except Exception as e:
                        response = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32000, "message": str(e)},
                        }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                    }
            elif method == "notifications/initialized":
                continue  # no response for notifications
            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown method: {method}"},
                }

            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

        except json.JSONDecodeError:
            continue
        except BrokenPipeError:
            break
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": str(e)},
            }
            try:
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
            except BrokenPipeError:
                break


def run_mcp_sse(port: int = 8001):
    """Run MCP server with SSE transport (for web clients)."""
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse
    import asyncio
    import uvicorn

    mcp_app = FastAPI(title="ThoughtOS MCP Server")

    @mcp_app.post("/mcp")
    async def mcp_endpoint(request: Request):
        body = await request.json()
        method = body.get("method", "")
        req_id = body.get("id")

        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "thoughtos", "version": "0.1.0"},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            tool_name = body.get("params", {}).get("name", "")
            tool_args = body.get("params", {}).get("arguments", {})
            handler = HANDLERS.get(tool_name)
            if handler:
                result = handler(tool_args)
            else:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}
        else:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    uvicorn.run(mcp_app, host="0.0.0.0", port=port, log_level="info")
