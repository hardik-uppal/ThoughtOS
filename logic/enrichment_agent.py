import json
from logic.sql_engine import (
    get_pending_enrichment,
    update_enrichment_status,
    get_needs_user_review,
    log_event
)
from logic.llm_engine import ask_gemini_json

class EnrichmentAgent:
    def __init__(self):
        pass

    def process_pending_items(self):
        """
        Fetches PENDING items and uses Gemini to tag them.
        Returns (auto_tagged_count, needs_review_count)
        """
        txns, events = get_pending_enrichment()

        log_event("EnrichmentAgent", f"Starting enrichment for {len(txns)} txns, {len(events)} events.")

        auto_count = 0
        review_count = 0

        # Process Transactions
        for txn in txns:
            result = self._analyze_transaction(txn)

            if result['status'] == 'COMPLETE':
                update_enrichment_status(
                    "master_transactions", 
                    "txn_id", 
                    txn['txn_id'], 
                    "COMPLETE", 
                    updates={"category": result['category']}
                )
                auto_count += 1
            else:
                update_enrichment_status(
                    "master_transactions", 
                    "txn_id", 
                    txn['txn_id'], 
                    "NEEDS_USER", 
                    updates={
                        "clarification_question": result['question'],
                        "suggested_tags": json.dumps(result['options'])
                    }
                )
                review_count += 1
                
        # Process Events (Simple auto-complete for now)
        for event in events:
            # Future: Analyze attendees
            update_enrichment_status("master_events", "event_id", event['event_id'], "COMPLETE")
            
        return auto_count, review_count

    def _analyze_transaction(self, txn):
        """
        Uses Gemini to classify the transaction with intelligent context.
        1. Check exact rule match
        2. Find similar transactions (embeddings)
        3. Ask LLM with context
        """
        from logic.llm_engine import ask_gemini_json
        from logic.sql_engine import get_rules
        from logic.embedding_engine import find_similar_transactions, store_embedding
        
        merchant = txn['merchant_name']
        amount = txn['amount']
        txn_id = txn['txn_id']
        
        # Store embedding for this transaction
        store_embedding(txn_id, merchant)
        
        # 1. Check exact rule match
        rules = get_rules()
        for rule in rules:
            if rule['pattern'].lower() in merchant.lower():
                return {"status": "COMPLETE", "category": rule['category']}
        
        # 2. Find similar transactions
        similar = find_similar_transactions(merchant, limit=5)
        
        # 3. Build context for LLM
        rules_context = "\n".join([
            f"- '{r['pattern']}' → {r['category']}" 
            for r in rules
        ]) if rules else "No rules yet."
        
        similar_context = "\n".join([
            f"- '{s['merchant_name']}' → {s['category']} (similarity: {s['similarity']:.2f})"
            for s in similar
        ]) if similar else "No similar transactions."
        
        prompt = f"""
        You are a financial data categorizer.
        Analyze this transaction:
        Merchant: "{merchant}"
        Amount: ${amount}
        
        User's Categorization Rules:
        {rules_context}
        
        Similar Transactions:
        {similar_context}
        
        Task:
        1. If you can confidently categorize based on rules or similar patterns, set status: COMPLETE
        2. If ambiguous, set status: NEEDS_USER with a clarifying question and 2-3 options
        
        Categories: Transport, Dining, Groceries, Shopping, Utilities, Rent, Salary, Transfer, Entertainment, Health, Other
        
        Output JSON only:
        {{
            "status": "COMPLETE" or "NEEDS_USER",
            "category": "The Category",
            "confidence": 0.0-1.0,
            "question": "Clarification question if ambiguous (else null)",
            "options": ["Option1", "Option2"] (if ambiguous, else [])
        }}
        
        Examples:
        - "Uber", $15 → status: COMPLETE, category: Transport, confidence: 0.95
        - "Amazon", $45 → status: NEEDS_USER, question: "What was this Amazon purchase?", options: ["Shopping", "Groceries", "Entertainment"]
        """
        
        try:
            response_json = ask_gemini_json(prompt)
            result = json.loads(response_json)
            
            # High confidence = COMPLETE, low = NEEDS_USER
            if result.get('confidence', 0) > 0.8 and result.get('status') != 'NEEDS_USER':
                result['status'] = 'COMPLETE'
            
            return result
        except Exception as e:
            print(f"LLM Error: {e}")
            # Fallback
            return {"status": "COMPLETE", "category": "Uncategorized"}

    def apply_user_feedback(self, txn_id, feedback_tag):
        """
        Called by UI when user clicks a button.
        """
        update_enrichment_status(
            "master_transactions", 
            "txn_id", 
            txn_id, 
            "COMPLETE", 
            updates={"category": feedback_tag}
        )
