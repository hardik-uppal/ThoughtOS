from logic.graph_db import GraphManager
from logic.enrichment import EnrichmentManager

def sync_calendar_to_graph(graph_manager, events):
    if not graph_manager.driver:
        return 0
    
    count = 0
    query = """
    MERGE (e:Event {id: $id})
    SET e.summary = $summary,
        e.start = $start,
        e.end = $end,
        e.recurringEventId = $recurringEventId,
        e.user_id = $user_id
    RETURN e
    """
    
    for event in events:
        params = {
            "id": event.get("event_id") or event.get("id"),
            "summary": event.get("summary"),
            "start": event.get("start_iso") or event.get("start"),
            "end": event.get("end_iso") or event.get("end"),
            "recurringEventId": event.get("series_id") or event.get("recurringEventId"),
            "user_id": event.get("user_id")
        }
        graph_manager.query(query, params)
        count += 1
    return count

def sync_transactions_to_graph(graph_manager, transactions):
    if not graph_manager.driver:
        return 0
    
    count = 0
    query = """
    MERGE (t:Transaction {id: $id})
    SET t.amount = $amount,
        t.date = $date,
        t.category = $category,
        t.user_id = $user_id
    
    MERGE (m:Merchant {name: $merchant})
    MERGE (t)-[:PAID_TO]->(m)
    RETURN t
    """
    
    for txn in transactions:
        params = {
            "id": txn.get("txn_id") or txn.get("id"),
            "amount": txn.get("amount"),
            "date": txn.get("date_posted") or txn.get("date"),
            "category": txn.get("category"),
            "merchant": txn.get("merchant_name") or txn.get("merchant"),
            "user_id": txn.get("user_id")
        }
        graph_manager.query(query, params)
        count += 1
    return count

def run_enrichment(graph_manager):
    """
    Runs the enrichment engine to link nodes.
    """
    em = EnrichmentManager(graph_manager)
    links = em.link_temporal_context()
    return links

def fetch_google_calendar(user_id):
    """
    Fetches events from Google Calendar and persists them to SQLite.
    Returns the list of events.
    """
    from integrations.calendar_api import fetch_events
    from logic.sql_engine import upsert_event
    from backend.auth import get_user_credentials
    
    # 1. Get credentials
    creds = get_user_credentials(user_id)
    if not creds:
        print(f"No credentials found for user {user_id}")
        return {"error": "No credentials found"}

    # 2. Fetch events using credentials
    events = fetch_events(creds=creds)
    
    if events and not isinstance(events, dict):
        for e in events:
            upsert_event(user_id, e)
            
    if isinstance(events, dict) and "error" in events:
        print(f"Calendar Error: {events['error']}")
        return []
        
    return events

def sync_plaid_transactions(user_id):
    """
    Fetches transactions from Plaid and persists them to SQLite.
    """
    from integrations.plaid_api import fetch_transactions
    from logic.sql_engine import upsert_transaction
    from logic.data_store import load_plaid_token
    
    # TODO: Load token for specific user
    token = load_plaid_token()
    if token:
        txns = fetch_transactions(token)
        for t in txns:
            upsert_transaction(user_id, t)
        return txns
    return []

def backfill_transactions(user_id, days=365):
    """
    Backfills transactions for the specified number of days.
    """
    from integrations.plaid_api import fetch_transactions
    from logic.sql_engine import upsert_transaction, log_event
    from logic.data_store import load_plaid_token
    
    # TODO: Load token for specific user
    token = load_plaid_token()
    if token:
        log_event("Backfill", f"Starting backfill for {days} days...", level="INFO")
        try:
            txns = fetch_transactions(token, days=days)
            log_event("Backfill", f"Fetched {len(txns)} transactions. Upserting...", level="INFO")
            for t in txns:
                upsert_transaction(user_id, t)
            log_event("Backfill", "Backfill complete.", level="SUCCESS")
            return len(txns)
        except Exception as e:
            log_event("Backfill", f"Backfill failed: {e}", level="ERROR")
            return 0
    return 0
