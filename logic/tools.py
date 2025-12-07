import sqlite3
import json
from logic.sql_engine import get_connection
from logic.graph_db import GraphManager
from logic.llm_engine import get_embedding

def query_metrics_sql(query):
    """
    Executes a read-only SQL query against the SQLite database.
    Used for aggregations (SUM, COUNT, AVG) on master_transactions.
    """
    # Safety: Basic keyword check to prevent modification
    if any(x in query.upper() for x in ["UPDATE", "DELETE", "DROP", "INSERT", "ALTER"]):
        return "Error: Read-only access allowed."
        
    conn = get_connection()
    try:
        print(f"[DEBUG] Executing SQL: {query}")
        cursor = conn.execute(query)
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return json.dumps(results)
    except Exception as e:
        return f"SQL Error: {e}"
    finally:
        conn.close()

def explore_context_graph(entity_query, depth=1):
    """
    Performs a Hybrid Search (Vector + Traversal) in Neo4j.
    1. Finds the closest node to 'entity_query' via Vector Search.
    2. Traverses 'depth' hops to find related context.
    """
    gm = GraphManager()
    if not gm.driver:
        return "Error: Graph DB not connected."
        
    # 1. Vector Search
    embedding = get_embedding(entity_query)
    if not embedding:
        return "Error: Could not generate embedding."
        
    # Find closest Event, Thought, or ChatThread
    vector_query = """
    CALL db.index.vector.queryNodes('thought_embeddings', 1, $emb)
    YIELD node AS n, score
    RETURN n, score, labels(n) as labels
    UNION
    CALL db.index.vector.queryNodes('event_embeddings', 1, $emb)
    YIELD node AS n, score
    RETURN n, score, labels(n) as labels
    UNION
    CALL db.index.vector.queryNodes('chat_embeddings', 1, $emb)
    YIELD node AS n, score
    RETURN n, score, labels(n) as labels
    ORDER BY score DESC
    LIMIT 3
    """
    
    # Note: We need to ensure chat_embeddings index exists. 
    # If not, this query might fail or return partial results.
    # For robustness, we'll wrap in try/except or assume index creation.
    
    try:
        start_nodes = gm.run_cypher(vector_query, {"emb": embedding})
    except Exception as e:
        return f"Graph Search Error: {e}"
    
    if not start_nodes:
        return "No relevant context found in Graph."
        
    context_results = []
    
    for item in start_nodes:
        start_node = item['n']
        start_id = start_node.get('id')
        start_label = item['labels'][0]
        score = item['score']
        
        # 2. Traversal (Get neighbors)
        traversal_query = f"""
        MATCH (start:{start_label} {{id: $id}})-[r]-(neighbor)
        RETURN type(r) as relation, labels(neighbor) as target_type, neighbor
        LIMIT 5
        """
        
        neighbors = gm.run_cypher(traversal_query, {"id": start_id})
        
        node_data = dict(start_node)
        # Remove embedding from output to save tokens
        if 'embedding' in node_data:
            del node_data['embedding']
            
        context_results.append({
            "Type": start_label,
            "Score": score,
            "Content": node_data,
            "Related": [
                {
                    "Relation": n['relation'],
                    "Type": n['target_type'][0],
                    "Properties": {k:v for k,v in dict(n['neighbor']).items() if k != 'embedding'}
                }
                for n in neighbors
            ]
        })
    
    return json.dumps(context_results, default=str)
