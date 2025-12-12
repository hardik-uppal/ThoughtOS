import json
from langgraph.graph import StateGraph, END
from logic.schemas import EnrichmentState, TransactionModel, EnrichmentStatus
from logic.sql_engine import (
    get_pending_enrichment,
    update_enrichment_status,
    log_event,
    get_rules
)
from logic.embedding_engine import find_similar_transactions, store_embedding
from logic.llm_engine import ask_gemini_json

class EnrichmentAgent:
    def __init__(self):
        self.workflow = self._build_graph()
        self.app = self.workflow.compile()

    def _build_graph(self):
        workflow = StateGraph(EnrichmentState)
        
        # Nodes
        workflow.add_node("enrich", self._node_enrich)
        workflow.add_node("evaluate", self._node_evaluate)
        workflow.add_node("commit", self._node_commit)
        workflow.add_node("flag_user", self._node_flag_user)
        
        # Edges
        workflow.set_entry_point("enrich")
        workflow.add_edge("enrich", "evaluate")
        
        workflow.add_conditional_edges(
            "evaluate",
            self._route_result,
            {
                "COMPLETE": "commit",
                "NEEDS_USER": "flag_user"
            }
        )
        
        workflow.add_edge("commit", END)
        workflow.add_edge("flag_user", END)
        
        return workflow

    def process_pending_items(self):
        """
        Main entry point to batch process pending transactions.
        """
        txns, events = get_pending_enrichment()
        log_event("EnrichmentAgent", f"Starting batch for {len(txns)} items.")
        
        auto_count = 0
        review_count = 0
        
        for txn_data in txns:
            # Create typed TransactionModel
            txn_model = TransactionModel(
                txn_id=txn_data['txn_id'],
                merchant_name=txn_data['merchant_name'],
                amount=txn_data['amount'],
                date=txn_data.get('date_posted', '')
            )
            
            initial_state = EnrichmentState(transaction=txn_model)
            
            # Invoke Graph
            final_state = self.app.invoke(initial_state)
            
            if final_state['status'] == EnrichmentStatus.COMPLETE:
                auto_count += 1
            else:
                review_count += 1
                
        return auto_count, review_count

    # --- Nodes ---

    def _node_enrich(self, state: EnrichmentState):
        txn = state.transaction
        
        # 1. Embeddings
        store_embedding(txn.txn_id, txn.merchant_name)
        similar = find_similar_transactions(txn.merchant_name)
        state.similar_transactions = similar
        
        # 2. Rules
        rules = get_rules()
        for rule in rules:
            if rule['pattern'].lower() in txn.merchant_name.lower():
                state.suggested_category = rule['category']
                state.confidence = 1.0
                state.status = EnrichmentStatus.COMPLETE
                return state

        # 3. LLM
        prompt = f"""
        Categorize transaction:
        Merchant: {txn.merchant_name}
        Amount: {txn.amount}
        
        Similar: {json.dumps(similar[:3])}
        
        Return JSON using this schema:
        {{
            "category": "...",
            "confidence": 0.0-1.0 (float),
            "is_ambiguous": boolean,
            "clarification_question": "..." (optional),
            "suggested_options": ["A", "B"] (optional)
        }}
        """
        try:
            result = json.loads(ask_gemini_json(prompt))
            state.suggested_category = result.get('category')
            state.confidence = result.get('confidence', 0.0)
            
            if result.get('is_ambiguous', False) or state.confidence < 0.7:
                state.status = EnrichmentStatus.NEEDS_USER
                state.clarification_question = result.get('clarification_question')
                state.suggested_options = result.get('suggested_options', [])
            else:
                state.status = EnrichmentStatus.COMPLETE
                
        except Exception as e:
            # Fallback
            state.status = EnrichmentStatus.NEEDS_USER
            state.clarification_question = f"Error processing: {e}"
            
        return state

    def _node_evaluate(self, state: EnrichmentState):
        # Already decided in enrich node, but could add extra verification logic here
        return state

    def _node_commit(self, state: EnrichmentState):
        update_enrichment_status(
            "master_transactions", 
            "txn_id", 
            state.transaction.txn_id, 
            "COMPLETE", 
            updates={"category": state.suggested_category}
        )
        return state

    def _node_flag_user(self, state: EnrichmentState):
        update_enrichment_status(
            "master_transactions", 
            "txn_id", 
            state.transaction.txn_id, 
            "NEEDS_USER", 
            updates={
                "clarification_question": state.clarification_question,
                "suggested_tags": json.dumps(state.suggested_options)
            }
        )
        return state

    def _route_result(self, state: EnrichmentState):
        return state.status.value

    def apply_user_feedback(self, txn_id, feedback_tag):
        # Direct SQL update, no graph needed for this simple action
        update_enrichment_status(
            "master_transactions", 
            "txn_id", 
            txn_id, 
            "COMPLETE", 
            updates={"category": feedback_tag}
        )
