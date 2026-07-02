"""FastAPI server for ThoughtOS — notes, tasks, and knowledge graph API.

Extends the existing backend with graph entity/relationship/rules endpoints.
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

try:
    from backend.auth import verify_google_token
except ImportError:
    import sys, os
    _parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    from backend.auth import verify_google_token

from .config import load_config
from .graph_store import GraphStore
from .note_intake import (
    intake_note,
    rerun_extraction_for_note,
    rerun_all_extractions,
)
from .extractor import ExtractionPipeline

app = FastAPI(title="ThoughtOS API", version="4.0")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load config
config = load_config()
graph = GraphStore(config.db_path)

# Initialize DB and graph on startup
@app.on_event("startup")
async def startup():
    # Import existing DB init
    from logic.sql_engine import init_db
    init_db()
    graph.init()

# --- Auth (same as existing) ---

optional_security = HTTPBearer(auto_error=False)

async def get_current_user_or_local(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
):
    if credentials:
        user_info = verify_google_token(credentials.credentials)
        return {
            "user_id": user_info["email"],
            "email": user_info["email"],
            "name": user_info.get("name", "Unknown"),
        }
    client_host = request.client.host if request.client else ""
    if client_host in {"127.0.0.1", "::1", "localhost"}:
        return {
            "user_id": request.headers.get("X-ThoughtOS-User", "local@thoughtos"),
            "email": request.headers.get("X-ThoughtOS-User", "local@thoughtos"),
            "name": "Local Terminal",
        }
    raise HTTPException(status_code=401, detail="Authentication required")


# --- Request models ---

class NoteIntakeRequest(BaseModel):
    text: str
    source: str = "api"
    note_type: Optional[str] = "auto"
    context: Optional[Dict[str, Any]] = None
    extract_entities: bool = True

class TaskStatusRequest(BaseModel):
    status: str

class RerunRequest(BaseModel):
    note_id: Optional[str] = None  # if None, smart rerun all stale
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    force: bool = False            # force re-extract ALL (ignore hashes)
    max_notes: int = 50            # batch size
    llm_enabled: Optional[bool] = None  # None = use config
    background: bool = False        # dry-run: just report what would run

class RuleToggleRequest(BaseModel):
    enabled: bool

class RuleAcceptRequest(BaseModel):
    pass  # no body needed


# --- Note / Task Endpoints (same as existing backend) ---

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "system": "ThoughtOS v4.0",
        "graph": graph.get_stats() if graph else {},
    }

@app.post("/api/notes/intake")
def note_intake_endpoint(
    request: NoteIntakeRequest,
    current_user: dict = Depends(get_current_user_or_local),
):
    """Capture notes, extract entities, create tasks."""
    try:
        result = intake_note(
            user_id=current_user["user_id"],
            text=request.text,
            source=request.source,
            note_type=request.note_type,
            context=request.context,
            extract_entities=request.extract_entities,
            config=config.extraction,
            db_path=config.db_path,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/notes")
def notes_list_endpoint(
    limit: int = 50,
    query: Optional[str] = None,
    note_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user_or_local),
):
    from logic.sql_engine import list_notes
    return {"notes": list_notes(current_user["user_id"], limit=limit, query=query, note_type=note_type)}

@app.get("/api/tasks")
def tasks_list_endpoint(
    status: str = "open",
    limit: int = 50,
    query: Optional[str] = None,
    current_user: dict = Depends(get_current_user_or_local),
):
    from logic.sql_engine import list_tasks
    return {"tasks": list_tasks(current_user["user_id"], status=status, limit=limit, query=query)}

@app.patch("/api/tasks/{task_id}")
def task_status_endpoint(
    task_id: str,
    request: TaskStatusRequest,
    current_user: dict = Depends(get_current_user_or_local),
):
    from logic.sql_engine import update_task_status
    task = update_task_status(current_user["user_id"], task_id, request.status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task}


# --- Graph Endpoints ---

@app.get("/api/graph/stats")
def graph_stats_endpoint():
    """Get knowledge graph statistics."""
    return graph.get_stats()

@app.get("/api/graph/entities")
def entities_list_endpoint(
    entity_type: Optional[str] = None,
    query: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user_or_local),
):
    """Search entities."""
    entities = graph.find_entities(
        user_id=current_user["user_id"],
        entity_type=entity_type,
        query=query,
        limit=limit,
    )
    return {"entities": entities}

@app.get("/api/graph/entities/{entity_id}")
def entity_detail_endpoint(entity_id: str):
    """Get a single entity."""
    entity = graph.get_entity(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity

@app.get("/api/graph/entities/{entity_id}/web")
def entity_web_endpoint(entity_id: str, max_hops: int = 2):
    """Get an entity and its neighborhood graph."""
    result = graph.get_entity_web(entity_id, max_hops=max_hops)
    if not result["entity"]:
        raise HTTPException(status_code=404, detail="Entity not found")
    return result

@app.get("/api/graph/path")
def graph_path_endpoint(
    source_id: str,
    target_id: str,
    max_hops: int = 4,
):
    """Find shortest path between two entities."""
    path = graph.find_path(source_id, target_id, max_hops)
    if not path:
        return {"path": None, "found": False}
    return {"path": path, "found": True, "hops": len(path)}

@app.get("/api/graph/relationships")
def relationships_list_endpoint(
    entity_id: Optional[str] = None,
    relation_type: Optional[str] = None,
    limit: int = 50,
):
    """List relationships."""
    rels = graph.find_relationships(
        entity_id=entity_id,
        relation_type=relation_type,
        limit=limit,
    )
    return {"relationships": rels}

@app.delete("/api/graph/entities/{entity_id}")
def entity_delete_endpoint(entity_id: str):
    """Delete an entity and its relationships."""
    graph.delete_entity(entity_id)
    return {"status": "deleted"}

# --- Extraction Endpoints ---

@app.post("/api/extraction/rerun")
def extraction_rerun_endpoint(
    request: RerunRequest,
    current_user: dict = Depends(get_current_user_or_local),
):
    """Re-run extraction with optional smart/stale-only mode.

    - note_id: re-extract a specific note
    - note_id omitted + force=true: re-extract ALL notes
    - note_id omitted (default): smart rerun — only stale notes
    - background=true: dry-run, return what WOULD be processed
    """
    try:
        force = getattr(request, 'force', False)

        if request.note_id:
            # Single note re-extraction
            import sqlite3
            conn = sqlite3.connect(config.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT note_id, raw_text FROM notes WHERE note_id = ?",
                (request.note_id,),
            ).fetchone()
            conn.close()

            if not row:
                raise HTTPException(status_code=404, detail="Note not found")

            result = rerun_extraction_for_note(
                note_id=row["note_id"],
                note_text=row["raw_text"],
                user_id=current_user["user_id"],
                config=config.extraction,
                db_path=config.db_path,
                llm_provider=request.llm_provider,
                llm_model=request.llm_model,
            )
        else:
            # Smart rerun
            pipeline = ExtractionPipeline(graph, config.extraction)
            result = pipeline.smart_rerun(
                user_id=current_user["user_id"],
                force_all=force,
                max_notes=getattr(request, 'max_notes', 50),
                llm_enabled=getattr(request, 'llm_enabled', None),
                background=getattr(request, 'background', False),
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/extraction/logs")
def extraction_logs_endpoint(
    note_id: Optional[str] = None,
    limit: int = 50,
):
    """Get extraction logs."""
    logs = graph.get_extraction_log(note_id=note_id, limit=limit)
    return {"logs": logs}

@app.get("/api/extraction/rules")
def extraction_rules_endpoint(
    enabled_only: bool = True,
    accepted_only: bool = True,
    rule_type: Optional[str] = None,
):
    """List extraction rules."""
    rules = graph.list_rules(
        enabled_only=enabled_only,
        accepted_only=accepted_only,
        rule_type=rule_type,
    )
    return {"rules": rules}

@app.post("/api/extraction/rules/{rule_id}/toggle")
def rule_toggle_endpoint(rule_id: str, request: RuleToggleRequest):
    """Enable or disable an extraction rule."""
    graph.toggle_rule(rule_id, request.enabled)
    return {"status": "ok"}

@app.post("/api/extraction/rules/{rule_id}/accept")
def rule_accept_endpoint(rule_id: str):
    """Accept a proposed rule."""
    graph.accept_rule(rule_id)
    return {"status": "accepted"}

@app.get("/api/extraction/rules/{rule_id}/impact")
def rule_impact_endpoint(
    rule_id: str,
    current_user: dict = Depends(get_current_user_or_local),
):
    """Check how many notes a rule would affect before accepting it.

    Runs the rule's regex against all notes (SQL LIKE pre-filter → regex).
    Use this before accepting to estimate extraction cost.
    """
    pipeline = ExtractionPipeline(graph, config.extraction)
    result = pipeline.assess_rule_impact(rule_id, current_user["user_id"])
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@app.get("/api/extraction/state")
def extraction_state_endpoint(
    note_id: Optional[str] = None,
):
    """Get extraction state for a note or overall stats."""
    if note_id:
        state = graph.get_extraction_state(note_id)
        return {"state": state}

    current_hash = graph.get_rule_hash()
    stale = graph.get_stale_notes(current_hash, limit=10000)
    return {
        "current_rule_hash": current_hash,
        "stale_count": len(stale),
        "stale_notes": stale[:20],  # first 20
    }


# --- LLM Provider Check ---

@app.get("/api/llm/check")
def llm_check_endpoint(provider: Optional[str] = None):
    """Check if LLM providers are available."""
    from .llm import check_provider
    results = {}

    if provider:
        cfg = config.extraction.extraction_llm
        if provider == "extraction":
            cfg = config.extraction.extraction_llm
        elif provider == "rule_gen":
            cfg = config.extraction.rule_gen_llm
        else:
            from .config import LLMConfig
            cfg = LLMConfig(provider=provider)
        results[provider] = check_provider(cfg)
    else:
        results["extraction"] = check_provider(config.extraction.extraction_llm)
        results["rule_gen"] = check_provider(config.extraction.rule_gen_llm)

    return {"providers": results}


# --- Run server ---

def start():
    """Entry point for 'thoughtos start'."""
    import uvicorn
    uvicorn.run(
        "thoughtos_server.main:app",
        host=config.host,
        port=config.port,
        reload=False,
        log_level="info",
    )
