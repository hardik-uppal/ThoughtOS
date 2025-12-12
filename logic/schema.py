from logic.graph_db import GraphManager

def create_constraints(graph_manager):
    """
    Sets up uniqueness constraints to prevent duplicate data.
    """
    if not graph_manager.driver:
        return "Graph DB not connected."

    queries = [
        "CREATE CONSTRAINT event_id_unique IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
        "CREATE CONSTRAINT transaction_id_unique IF NOT EXISTS FOR (t:Transaction) REQUIRE t.id IS UNIQUE",
        "CREATE CONSTRAINT merchant_name_unique IF NOT EXISTS FOR (m:Merchant) REQUIRE m.name IS UNIQUE",
        "CREATE INDEX transaction_user_id IF NOT EXISTS FOR (t:Transaction) ON (t.user_id)",
        "CREATE INDEX event_user_id IF NOT EXISTS FOR (e:Event) ON (e.user_id)"
    ]

    results = []
    for q in queries:
        try:
            graph_manager.query(q)
            results.append(f"Executed: {q}")
        except Exception as e:
            results.append(f"Failed: {q} ({e})")
    
    return results
