from logic.graph_db import GraphManager
from logic.sql_engine import log_event
import datetime

def analyze_stress_spending():
    """
    Analyzes the Knowledge Graph to find correlations between 'High Stress' events
    and subsequent spending.
    
    Definition of High Stress (MVP):
    - Events containing: "Deadline", "Meeting", "Pitch", "Review", "Urgent"
    
    Definition of Correlation:
    - Transaction occurs within 4 hours AFTER the event end time.
    """
    gm = GraphManager()
    if not gm.verify_connection():
        log_event("Causal Engine", "Skipping analysis: Neo4j not connected", "WARNING")
        return "Neo4j Disconnected"

    # Cypher Query: Find Stress Events and subsequent Transactions
    query = """
    MATCH (e:Event)
    WHERE toLower(e.summary) CONTAINS 'deadline' 
       OR toLower(e.summary) CONTAINS 'meeting' 
       OR toLower(e.summary) CONTAINS 'pitch'
       OR toLower(e.summary) CONTAINS 'urgent'
    
    // Find transactions within 4 hours (14400 seconds) after event
    MATCH (t:Transaction)
    WHERE datetime(t.date) >= datetime(e.end) 
      AND datetime(t.date) <= datetime(e.end) + duration('PT4H')
      
    RETURN e.summary as Event, t.merchant as Merchant, t.amount as Amount, t.category as Category
    """
    
    try:
        results = gm.query(query)
        
        if not results:
            log_event("Causal Engine", "Analysis complete. No correlations found.", "INFO")
            return "No correlations found."
            
        # Aggregate findings
        total_spent = 0
        categories = {}
        
        for r in results:
            amount = float(r['Amount'])
            total_spent += amount
            cat = r['Category']
            categories[cat] = categories.get(cat, 0) + amount
            
        # Log Summary
        top_cat = max(categories, key=categories.get) if categories else "None"
        msg = f"Found correlation! Spent ${total_spent:.2f} after {len(results)} stressful events. Top Category: {top_cat}"
        
        log_event("Causal Engine", msg, "INFO", metadata={"details": results})
        return msg
        
    except Exception as e:
        log_event("Causal Engine", f"Analysis failed: {e}", "ERROR")
        return f"Error: {e}"

if __name__ == "__main__":
    analyze_stress_spending()
