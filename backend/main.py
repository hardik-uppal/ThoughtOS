from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sys
import os

# Add root directory to sys.path to import existing logic
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import Agent
from logic.ingestion import sync_plaid_transactions, fetch_google_calendar
from logic.task_engine import calculate_daily_energy, rank_tasks
from logic.sql_engine import get_thoughts

app = FastAPI(title="ContextOS API", version="3.0")

# Initialize Agent
agent = Agent()

# Initialize Database
from logic.sql_engine import init_db
init_db()

class ChatRequest(BaseModel):
    message: str
    image: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    thread_id:Optional[str] = None

class ChatResponse(BaseModel):
    type: str
    content: str
    data: Optional[Dict[str, Any]] = None
    thread_id: Optional[str] = None

@app.get("/health")
def health_check():
    return {"status": "ok", "system": "ContextOS v3.0"}

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        from logic.sql_engine import save_message, get_thread_messages, create_thread
        
        # 1. Get or create thread
        thread_id = request.thread_id
        if not thread_id:
            thread_id = create_thread()
        
        # 2. Load history from DB
        db_history = get_thread_messages(thread_id)
        history = [{"role": m['role'], "content": m['content']} for m in db_history]
        
        # Extract context if present
        context = request.context
        print(f"[DEBUG] Context received: {context}")
        print(f"[DEBUG] Message: {request.message}")
        print(f"[DEBUG] Thread ID: {thread_id}")
        
        # 3. Save user message
        save_message(thread_id, 'user', request.message)
        
        # 4. Process
        response = agent.process_input(request.message, request.image, context=context, history=history)
        
        # 5. Normalize response
        if isinstance(response, str):
            response = {"type": "chat", "content": response}
        
        # 6. Save assistant response
        save_message(thread_id, 'assistant', response.get('content', ''))
        
        # 7. Return with thread_id
        return {
            **response,
            "thread_id": thread_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CloseThreadRequest(BaseModel):
    thread_id: str

@app.post("/api/chat/thread/close")
def close_thread_endpoint(req: CloseThreadRequest, background_tasks: BackgroundTasks):
    from logic.chat_engine import ChatEngine
    
    def summarize_task(thread_id):
        engine = ChatEngine()
        engine.summarize_and_store_thread(thread_id)
        
    background_tasks.add_task(summarize_task, req.thread_id)
    return {"status": "closing", "message": "Thread summarization started."}

@app.post("/api/sync")
def sync_endpoint():
    try:
        # 1. Sync Plaid
        txns = sync_plaid_transactions()
        
        # 2. Sync Calendar
        events = fetch_google_calendar()
        
        # 3. Run auto-enrichment (NEW)
        auto_tagged = 0
        needs_review = 0
        try:
            auto_tagged, needs_review = curator_agent.process_pending_items()
        except Exception as e:
            print(f"Auto-enrichment error: {e}")
        
        # 4. Sync to Graph
        from logic.graph_db import GraphManager
        from logic.ingestion import sync_calendar_to_graph, sync_transactions_to_graph, run_enrichment
        
        gm = GraphManager()
        if gm.verify_connection():
            # Sync Events
            if isinstance(events, list):
                sync_calendar_to_graph(gm, events)
            
            # Sync Transactions
            if isinstance(txns, list):
                sync_transactions_to_graph(gm, txns)
                
            # Run Enrichment
            links_count = run_enrichment(gm)
            
            return {
                "status": "success", 
                "transactions_synced": len(txns) if isinstance(txns, list) else 0,
                "events_synced": len(events) if isinstance(events, list) else 0,
                "enrichment_links": links_count,
                "auto_tagged": auto_tagged,
                "needs_review": needs_review
            }
        else:
            return {
                "status": "warning",
                "message": "Data synced to SQL, but GraphDB unavailable.",
                "transactions_synced": len(txns) if isinstance(txns, list) else 0,
                "events_synced": len(events) if isinstance(events, list) else 0,
                "auto_tagged": auto_tagged,
                "needs_review": needs_review
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BackfillRequest(BaseModel):
    days: int = 365

@app.post("/api/action/backfill")
def backfill_endpoint(req: BackfillRequest, background_tasks: BackgroundTasks):
    from logic.ingestion import backfill_transactions
    
    background_tasks.add_task(backfill_transactions, days=req.days)
    return {"status": "started", "message": f"Backfill started for {req.days} days."}

@app.get("/api/context")
def get_context_rail():
    """
    Returns data for the Context Rail (Energy, Events, Tasks).
    """
    try:
        # 1. Events & Energy
        events = fetch_google_calendar()
        energy_level = calculate_daily_energy(events)
        
        # 2. Tasks
        all_tasks = get_thoughts()
        ranked_tasks = rank_tasks(all_tasks, energy_level)
        
        return {
            "energy_level": energy_level,
            "events": events[:5] if isinstance(events, list) else [],
            "tasks": ranked_tasks[:5] if ranked_tasks else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Admin Endpoints ---

from logic.sql_engine import get_logs, clear_logs
from scripts.causal_analysis import analyze_stress_spending

@app.get("/api/logs")
def logs_endpoint(limit: int = 50):
    try:
        return get_logs(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logs/clear")
def clear_logs_endpoint():
    try:
        clear_logs()
        return {"status": "success", "message": "Logs cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analysis/causal")
def causal_analysis_endpoint():
    try:
        result = analyze_stress_spending()
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Auth Endpoints ---

from integrations.plaid_api import create_link_token, exchange_public_token
from integrations.calendar_api import authenticate_google
from logic.data_store import save_plaid_token

@app.get("/api/auth/plaid/link-token")
def plaid_link_token_endpoint():
    try:
        result = create_link_token()
        if "error" in result:
             raise HTTPException(status_code=400, detail=result["error"])
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PlaidExchangeRequest(BaseModel):
    public_token: str

@app.post("/api/auth/plaid/exchange")
def plaid_exchange_endpoint(req: PlaidExchangeRequest):
    try:
        access_token = exchange_public_token(req.public_token)
        save_plaid_token(access_token)
        return {"status": "success", "message": "Plaid Connected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/google")
def google_auth_endpoint():
    try:
        creds = authenticate_google()
        if creds:
            return {"status": "success", "message": "Google Calendar Connected"}
        else:
             raise HTTPException(status_code=400, detail="Auth failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Context Notes Endpoint ---

from logic.sql_engine import get_connection

class ContextSaveRequest(BaseModel):
    type: str  # 'event' or 'task'
    id: str
    notes: str

@app.post("/api/context/save")
def save_context_endpoint(req: ContextSaveRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if req.type == 'event':
            cursor.execute(
                "UPDATE master_events SET context_notes = ? WHERE event_id = ?",
                (req.notes, req.id)
            )
        elif req.type == 'task':
            cursor.execute(
                "UPDATE master_entries SET context_notes = ? WHERE entry_id = ?",
                (req.notes, req.id)
            )
        
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Context Form Submission ---

class ContextSubmitRequest(BaseModel):
    contextId: str
    contextType: str
    formData: Dict[str, str]

@app.post("/api/context/submit")
def submit_context_endpoint(req: ContextSubmitRequest):
    try:
        from logic.context_notes import add_note_to_node
        from logic.graph_db import GraphManager
        
        graph = GraphManager()
        
        # Convert form data to a formatted note
        note_lines = []
        for key, value in req.formData.items():
            if value:
                note_lines.append(f"**{key.replace('_', ' ').title()}**: {value}")
        
        note_text = "\n".join(note_lines)
        
        # Determine Neo4j node type
        node_type = "Event" if req.contextType == "event" else "Entry"
        
        # Save to Neo4j
        result = add_note_to_node(graph, node_type, req.contextId, note_text)
        
        return {"status": "success", "message": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/auth/status")
def auth_status_endpoint():
    # Check if we have tokens (Mock logic for now, checking if DB has data is a good proxy)
    from logic.sql_engine import get_transactions, get_events
    
    has_plaid = len(get_transactions(limit=1)) > 0
    has_google = len(get_events(limit=1)) > 0
    
    return {
        "plaid": has_plaid,
        "google": has_google
    }

# --- Onboarding Endpoints ---

from logic.onboarding_agent import OnboardingAgent
onboarding_agent = OnboardingAgent()

@app.get("/api/onboarding/status")
def onboarding_status_endpoint():
    try:
        is_complete = onboarding_agent.check_status()
        return {"complete": is_complete}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/onboarding/calibrate/finance")
def calibrate_finance_endpoint():
    try:
        questions = onboarding_agent.generate_financial_questions()
        return {"questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RuleRequest(BaseModel):
    merchant: str
    category: str

@app.post("/api/onboarding/rules")
def save_rule_endpoint(req: RuleRequest):
    try:
        success = onboarding_agent.save_rule(req.merchant, req.category)
        return {"status": "success" if success else "error"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/onboarding/complete")
def complete_onboarding_endpoint():
    try:
        # Also set productivity defaults when completing
        onboarding_agent.set_productivity_defaults()
        onboarding_agent.complete_onboarding()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Curator Endpoints ---

from logic.enrichment_agent import EnrichmentAgent
from logic.sql_engine import get_needs_user_review, reset_enrichment_status

curator_agent = EnrichmentAgent()

@app.get("/api/curator/review")
def curator_review_endpoint():
    try:
        items = get_needs_user_review()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CuratorApplyRequest(BaseModel):
    txn_id: str
    tag: str

@app.post("/api/curator/apply")
def curator_apply_endpoint(req: CuratorApplyRequest):
    try:
        from logic.sql_engine import get_rules
        
        # 1. Apply tag
        curator_agent.apply_user_feedback(req.txn_id, req.tag)
        
        # 2. Check if similar pattern exists in rules
        rules = get_rules()
        existing_rule = any(r['pattern'].lower() in req.txn_id.lower() for r in rules)
        
        if not existing_rule:
            # 3. Suggest creating a rule
            return {
                "status": "success",
                "suggest_rule": True,
                "pattern": req.txn_id,
                "category": req.tag
            }
        
        return {"status": "success", "suggest_rule": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/curator/auto")
def curator_auto_endpoint():
    try:
        auto, manual = curator_agent.process_pending_items()
        return {"status": "success", "auto_tagged": auto, "needs_review": manual}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/curator/reset")
def curator_reset_endpoint():
    try:
        reset_enrichment_status()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
