"""Note intake — captures raw notes, standardizes, extracts entities.

This is a lightweight wrapper around the existing logic/note_intake module,
adding graph entity extraction as a third step in the pipeline:

  raw text → standardize → extract entities+relationships → store in SQLite + graph
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from logic.note_intake import intake_note as _original_intake_note
except ImportError:
    # Fallback: when running without full install
    import sys, os
    _parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from logic.note_intake import intake_note as _original_intake_note

from .config import ExtractionConfig, load_config
from .graph_store import GraphStore
from .extractor import ExtractionPipeline
from .paths import database_path, using_database


def intake_note(
    user_id: str,
    text: str,
    source: str = "api",
    note_type: str = "auto",
    context: Optional[Dict[str, Any]] = None,
    extract_entities: bool = True,
    config: Optional[ExtractionConfig] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Capture a note, standardize it, extract entities, store everything.

    Args:
        user_id: The user making the request.
        text: Raw note text.
        source: Source label (e.g., 'pi', 'claude', 'api').
        note_type: 'auto', 'meeting_note', 'quick_note', 'task_dump', etc.
        context: Optional additional context.
        extract_entities: Whether to run graph entity extraction.
        config: Extraction configuration (uses env vars if None).
        db_path: Path to SQLite database.

    Returns:
        Dict with 'note', 'tasks', 'structured', and optionally 'extraction'.
    """
    # Explicit per-call overrides must apply to notes/tasks AND the graph.
    db_path = database_path(db_path)
    from logic.sql_engine import init_db
    with using_database(db_path):
        init_db()
        result = _original_intake_note(
            user_id=user_id,
            text=text,
            source=source,
            note_type=note_type,
            context=context,
        )

    # Step 2: Extract entities & relationships
    if extract_entities:
        try:
            ext_config = config or load_config().extraction
            graph = GraphStore(db_path)
            # Ensure graph tables exist
            graph.init()

            pipeline = ExtractionPipeline(graph, ext_config)
            extraction = pipeline.extract(
                text=text,
                note_id=result["note"].get("note_id", ""),
                user_id=user_id,
            )
            result["extraction"] = {
                "entities": extraction["entities"],
                "relationships": extraction["relationships"],
                "rules_proposed": extraction.get("rules_proposed", []),
                "total_duration_ms": extraction.get("total_duration_ms", 0),
            }
        except Exception as e:
            result["extraction"] = {"error": str(e)}

    return result


def rerun_extraction_for_note(
    note_id: str,
    note_text: str,
    user_id: str,
    config: Optional[ExtractionConfig] = None,
    db_path: Optional[str] = None,
    llm_provider: Optional[str] = None,
    llm_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-run extraction on a specific note with optional different LLM."""
    ext_config = config or load_config().extraction
    graph = GraphStore(db_path)
    graph.init()

    pipeline = ExtractionPipeline(graph, ext_config)

    if llm_provider or llm_model:
        return pipeline.improve_extraction(
            note_id=note_id,
            note_text=note_text,
            user_id=user_id,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
    else:
        return pipeline.extract(
            text=note_text,
            note_id=note_id,
            user_id=user_id,
        )


def rerun_all_extractions(
    user_id: str,
    config: Optional[ExtractionConfig] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-run extraction on all notes for a user."""
    import sqlite3

    ext_config = config or load_config().extraction
    graph = GraphStore(db_path)
    graph.init()

    # Get all notes with their text
    conn = sqlite3.connect(graph.db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT note_id, raw_text FROM notes WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        ).fetchall()
        note_texts = [(r["note_id"], r["raw_text"]) for r in rows]
    finally:
        conn.close()

    pipeline = ExtractionPipeline(graph, ext_config)
    return pipeline.rerun_all(user_id, note_texts)
