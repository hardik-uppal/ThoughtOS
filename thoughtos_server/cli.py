"""ThoughtOS CLI — quick access to notes, tasks, and graph from the terminal.

Usage:
  thoughtos start                Start the HTTP API server on :8000
  thoughtos mcp                  Start MCP server for Claude Code (stdio)
  thoughtos mcp --port 8001      Start MCP server with SSE transport
  thoughtos note "text"          Quick note capture
  thoughtos tasks                List open tasks
  thoughtos todo "task text"     Create a task
  thoughtos entities [query]     Search entities
  thoughtos stats                Graph statistics
  thoughtos check                Check LLM providers
  thoughtos rules                List extraction rules
  thoughtos rerun                 Smart rerun: only stale notes
  thoughtos rerun --force         Re-extract ALL notes  
  thoughtos rerun --background    Dry-run: show what would run
  thoughtos rerun --rules-only    Rules-only (no LLM cost)
  thoughtos rerun <note_id>       Re-extract a specific note
  thoughtos impact <rule_id>      Check rule impact before accepting
"""

import sys
import os
import json
import argparse


def cmd_start(args):
    """Start the ThoughtOS HTTP API server."""
    from thoughtos_server.main import start
    print("🚀 Starting ThoughtOS server on http://0.0.0.0:8000")
    start()


def cmd_mcp(args):
    """Start MCP server for Claude Code."""
    from thoughtos_server.mcp_server import run_mcp_stdio, run_mcp_sse

    if hasattr(args, "port") and args.port:
        print(f"🔌 Starting ThoughtOS MCP server (SSE) on port {args.port}")
        run_mcp_sse(port=args.port)
    else:
        # stdio mode for Claude Code
        run_mcp_stdio()


def cmd_note(args):
    """Quick note capture via CLI."""
    from thoughtos_server.config import load_config
    from thoughtos_server.note_intake import intake_note

    config = load_config()
    text = args.text
    source = getattr(args, "source", "cli")

    result = intake_note(
        user_id="local@thoughtos",
        text=text,
        source=source,
        note_type=getattr(args, "type", "auto"),
        extract_entities=True,
        config=config.extraction,
        db_path=config.db_path,
    )

    note = result.get("note", {})
    tasks = result.get("tasks", [])
    extraction = result.get("extraction", {})

    print(f"🧠 Captured: {note.get('title', 'Untitled')}")
    if note.get("summary"):
        print(f"   {note['summary']}")

    if tasks:
        print(f"\n📋 Tasks ({len(tasks)}):")
        for t in tasks:
            due = f" · due {t['due_date']}" if t.get('due_date') else ""
            print(f"   - [ ] {t['title']}{due}")

    if extraction.get("entities"):
        entities = extraction["entities"]
        print(f"\n🔗 Entities extracted: {len(entities)}")
        for e in entities[:10]:
            print(f"   - {e['name']} ({e.get('type', '?')})")


def cmd_tasks(args):
    """List tasks."""
    try:
        from logic.sql_engine import list_tasks
    except ImportError:
        print("Error: logic.sql_engine not found. Run from ThoughtOS directory.")
        return

    tasks = list_tasks("local@thoughtos", status="open", limit=20)
    if not tasks:
        print("No open tasks.")
        return

    print(f"📋 Tasks ({len(tasks)}):")
    for t in tasks:
        due = f" · due {t['due_date']}" if t.get('due_date') else ""
        print(f"   - [ ] {t['title']}{due}")


def cmd_todo(args):
    """Create a task."""
    from thoughtos_server.config import load_config
    from thoughtos_server.note_intake import intake_note

    config = load_config()
    result = intake_note(
        user_id="local@thoughtos",
        text=f"TODO: {args.text}",
        source="cli",
        note_type="task_dump",
        extract_entities=False,
        config=config.extraction,
        db_path=config.db_path,
    )

    tasks = result.get("tasks", [])
    if tasks:
        print(f"✅ Created task: {tasks[0]['title']}")
    else:
        print("⚠️  No task extracted from input.")


def cmd_entities(args):
    """Search entities."""
    from thoughtos_server.config import load_config
    from thoughtos_server.graph_store import GraphStore

    config = load_config()
    graph = GraphStore(config.db_path)
    graph.init()

    entities = graph.find_entities(
        user_id="local@thoughtos",
        query=args.query if hasattr(args, "query") and args.query else None,
        entity_type=getattr(args, "type", None),
        limit=getattr(args, "limit", 50),
    )

    if not entities:
        print("No entities found.")
        return

    print(f"🔗 Entities ({len(entities)}):")
    for e in entities:
        aliases = ""
        if e.get("aliases"):
            alias_list = e["aliases"] if isinstance(e["aliases"], list) else []
            if alias_list:
                aliases = f" (aka {', '.join(alias_list[:3])})"
        print(f"   - {e['name']} [{e.get('type', '?')}]{aliases}")


def cmd_stats(args):
    """Show graph stats."""
    from thoughtos_server.config import load_config
    from thoughtos_server.graph_store import GraphStore

    config = load_config()
    graph = GraphStore(config.db_path)
    graph.init()

    stats = graph.get_stats()
    print("🧠 Knowledge Graph Stats:")
    print(f"   Entities: {stats['entity_count']}")
    print(f"   Relationships: {stats['relationship_count']}")
    print(f"   Rules: {stats['rule_count']}")
    print("\n   Entity types:")
    for etype, count in stats.get("entity_types", {}).items():
        print(f"     {etype}: {count}")
    print("\n   Relationship types:")
    for rtype, count in stats.get("relation_types", {}).items():
        print(f"     {rtype}: {count}")


def cmd_check(args):
    """Check LLM providers."""
    from thoughtos_server.config import load_config
    from thoughtos_server.llm import check_provider

    config = load_config()
    providers = {
        "extraction": config.extraction.extraction_llm,
        "rule_gen": config.extraction.rule_gen_llm,
    }

    for name, cfg in providers.items():
        result = check_provider(cfg)
        status = "✅" if result.get("status") == "ok" else "❌"
        print(f"{status} {name}: {cfg.provider}/{cfg.model}")
        if result.get("status") == "error":
            print(f"     Error: {result.get('reason')}")
        elif result.get("model_available") is False:
            print(f"     ⚠️  Model '{cfg.model}' not found. Available: {', '.join(result.get('models', [])[:10])}")
        else:
            print(f"     Models available: {len(result.get('models', []))}")


def cmd_rules(args):
    """List extraction rules."""
    from thoughtos_server.config import load_config
    from thoughtos_server.graph_store import GraphStore

    config = load_config()
    graph = GraphStore(config.db_path)
    graph.init()

    include_pending = getattr(args, "all", False)
    rules = graph.list_rules(
        enabled_only=True,
        accepted_only=not include_pending,
    )

    if not rules:
        print("No rules found.")
        return

    active = [r for r in rules if r.get("accepted")]
    pending = [r for r in rules if not r.get("accepted")]

    print(f"📏 Active rules ({len(active)}):")
    for r in active:
        print(f"   - `{r['pattern']}` → {r.get('entity_type') or r.get('relation_type', '?')} "
              f"(used {r.get('usage_count', 0)}x, conf={r.get('confidence', 0)})")

    if pending:
        print(f"\n📝 Pending review ({len(pending)}):")
        for r in pending:
            by = f" by {r.get('source_llm', '?')}" if r.get('source_llm') else ""
            print(f"   - `{r['pattern']}` → {r.get('entity_type', '?')}{by}")


def cmd_rerun(args):
    """Re-run extraction."""
    from thoughtos_server.config import load_config
    from thoughtos_server.extractor import ExtractionPipeline
    from thoughtos_server.graph_store import GraphStore

    config = load_config()
    graph = GraphStore(config.db_path)
    graph.init()  # ensure tables exist
    pipeline = ExtractionPipeline(graph=graph, config=config.extraction)

    force = getattr(args, "force", False)
    background = getattr(args, "background", False)
    rules_only = getattr(args, "rules_only", False)

    if hasattr(args, "note_id") and args.note_id:
        # Single note
        import sqlite3
        conn = sqlite3.connect(config.db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT note_id, raw_text, title FROM notes WHERE note_id = ?",
            (args.note_id,),
        ).fetchone()
        conn.close()

        if not row:
            print(f"Note {args.note_id} not found.")
            return

        print(f"🔍 Re-extracting: {row['title']}")
        from thoughtos_server.note_intake import rerun_extraction_for_note
        result = rerun_extraction_for_note(
            note_id=row["note_id"],
            note_text=row["raw_text"],
            user_id="local@thoughtos",
            config=config.extraction,
            db_path=config.db_path,
        )
        print(f"   Entities: {len(result.get('entities', []))}")
        print(f"   Relationships: {len(result.get('relationships', []))}")
        print(f"   Rules proposed: {len(result.get('rules_proposed', []))}")
    else:
        # Smart rerun
        llm_enabled = False if rules_only else None  # None = use config

        if background:
            result = pipeline.smart_rerun(
                user_id="local@thoughtos",
                force_all=force,
                background=True,
            )
            print(f"📊 Extraction state:")
            print(f"   Rule hash: {result.get('rule_hash', '?')}")
            print(f"   Would process: {result.get('would_process', 0)} notes")
            print(f"   Total stale: {result.get('total_stale', 0)}")
            print(f"   Strategy: {result.get('strategy', '?')}")
            return

        if force:
            print("🔍 Force re-extracting ALL notes...")
        else:
            print("🔍 Smart rerun: only stale notes...")

        result = pipeline.smart_rerun(
            user_id="local@thoughtos",
            force_all=force,
            max_notes=getattr(args, "max_notes", 50),
            llm_enabled=llm_enabled,
        )

        if result.get("strategy") == "up_to_date":
            print("✅ All notes up-to-date with current rules.")
        else:
            print(f"   Strategy: {result.get('strategy', '?')}")
            print(f"   Processed: {result.get('processed', 0)}")
            print(f"   Skipped: {result.get('skipped', 0)}")
            print(f"   New entities: {result.get('total_entities', 0)}")
            print(f"   New relationships: {result.get('total_relationships', 0)}")
            print(f"   Rules proposed: {result.get('rules_proposed', 0)}")

def cmd_impact(args):
    """Check impact of a rule before accepting."""
    from thoughtos_server.config import load_config
    from thoughtos_server.extractor import ExtractionPipeline
    from thoughtos_server.graph_store import GraphStore

    config = load_config()
    graph = GraphStore(config.db_path)
    graph.init()
    pipeline = ExtractionPipeline(graph=graph, config=config.extraction)
    result = pipeline.assess_rule_impact(args.rule_id, "local@thoughtos")

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    rule = result.get("rule", {})
    print(f"📏 Rule: `{rule.get('pattern', '?')}`")
    print(f"   Type: {rule.get('entity_type') or rule.get('relation_type', '?')}")
    print(f"   Affected notes: {result['affected_notes']}")
    print(f"   Est. new entities: {result['estimated_new_entities']}")
    print(f"   Impact: {result.get('recommendation', '?')}")
    if result.get("sample_affected"):
        print(f"   Sample: {result['sample_affected'][:5]}")


def main():
    parser = argparse.ArgumentParser(
        description="ThoughtOS — personal knowledge graph & task manager",
        prog="thoughtos",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # start
    subparsers.add_parser("start", help="Start HTTP API server")

    # mcp
    mcp_parser = subparsers.add_parser("mcp", help="Start MCP server for Claude Code")
    mcp_parser.add_argument("--port", type=int, help="Port for SSE transport (default: stdio)")

    # note
    note_parser = subparsers.add_parser("note", help="Capture a note")
    note_parser.add_argument("text", help="Note text")
    note_parser.add_argument("--source", default="cli", help="Source label")
    note_parser.add_argument("--type", default="auto", help="Note type")

    # tasks
    subparsers.add_parser("tasks", help="List open tasks")

    # todo
    todo_parser = subparsers.add_parser("todo", help="Create a task")
    todo_parser.add_argument("text", help="Task description")

    # entities
    ent_parser = subparsers.add_parser("entities", help="Search entities")
    ent_parser.add_argument("query", nargs="?", help="Search query")
    ent_parser.add_argument("--type", help="Entity type filter")
    ent_parser.add_argument("--limit", type=int, default=50, help="Max results")

    # stats
    subparsers.add_parser("stats", help="Graph statistics")

    # check
    subparsers.add_parser("check", help="Check LLM providers")

    # rules
    rules_parser = subparsers.add_parser("rules", help="List extraction rules")
    rules_parser.add_argument("--all", action="store_true", help="Include pending rules")

    # rerun
    rerun_parser = subparsers.add_parser("rerun", help="Re-run extraction (smart: only stale notes)")
    rerun_parser.add_argument("note_id", nargs="?", help="Note ID (omit for smart rerun)")
    rerun_parser.add_argument("--force", action="store_true", help="Force re-extract ALL notes")
    rerun_parser.add_argument("--background", action="store_true", help="Dry-run: show what would process")
    rerun_parser.add_argument("--rules-only", action="store_true", help="Only apply rules, no LLM")
    rerun_parser.add_argument("--max-notes", type=int, default=50, help="Batch size")

    # impact
    impact_parser = subparsers.add_parser("impact", help="Check rule impact before accepting")
    impact_parser.add_argument("rule_id", help="Rule ID to check")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "start": cmd_start,
        "mcp": cmd_mcp,
        "note": cmd_note,
        "tasks": cmd_tasks,
        "todo": cmd_todo,
        "entities": cmd_entities,
        "stats": cmd_stats,
        "check": cmd_check,
        "rules": cmd_rules,
        "rerun": cmd_rerun,
        "impact": cmd_impact,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
