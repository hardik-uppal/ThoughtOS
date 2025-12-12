import json
from langgraph.graph import StateGraph, END
from logic.schemas import ReasoningState, ResponseModel, WidgetModel, WidgetType
from logic.llm_engine import ask_gemini, ask_gemini_json
from logic.tools import query_metrics_sql, explore_context_graph
from logic.sql_engine import log_event

class ReasoningEngine:
    def __init__(self):
        self.workflow = self._build_graph()
        self.app = self.workflow.compile()

    def _build_graph(self):
        workflow = StateGraph(ReasoningState)

        # Define Nodes
        workflow.add_node("classify", self._node_classify)
        workflow.add_node("tool_sql", self._node_tool_sql)
        workflow.add_node("tool_graph", self._node_tool_graph)
        workflow.add_node("respond", self._node_respond)

        # Define Edges
        workflow.set_entry_point("classify")
        
        workflow.add_conditional_edges(
            "classify",
            self._route_tool,
            {
                "SQL": "tool_sql",
                "GRAPH": "tool_graph",
                "CHAT": "respond",
                "VISION": "respond" # In future, can have dedicated vision node
            }
        )
        
        workflow.add_edge("tool_sql", "respond")
        workflow.add_edge("tool_graph", "respond")
        workflow.add_edge("respond", END)

        return workflow

    def process_query(self, user_query, history=None, image=None):
        """
        Main entry point.
        """
        initial_state = ReasoningState(
            user_query=user_query,
            messages=history if history else []
        )
        
        # Invoke the graph
        final_state = self.app.invoke(initial_state)
        
        # Convert Pydantic response to Dict for frontend
        if final_state.get('final_response'):
            return final_state['final_response'].dict()
        else:
            return {"text": "Error: No response generated.", "widget": {"type": "none"}}

    # --- Nodes ---

    def _node_classify(self, state: ReasoningState):
        query = state.user_query
        history = state.messages
        
        # Reuse existing logic but return into State
        # (This logic is adapted from original _classify_intent but streamlined)
        
        history_str = self._format_history(history)
        prompt = f"""
        You are the Brain of ContextOS.
        {history_str}
        User Query: "{query}"
        
        Available Tools:
        1. SQL: For quantitative questions about Money/Transactions. DATABASE IS SQLite.
           - Table: master_transactions (txn_id, merchant_name, amount, category, date_posted)
           - SQLite date functions: date('now'), date('now', '-7 days'), datetime('now')
           - Example: SELECT SUM(amount) FROM master_transactions WHERE date_posted >= date('now', '-7 days')
           - DO NOT use MySQL functions like DATE_SUB, NOW(), INTERVAL.
        2. GRAPH: For qualitative questions about Context, Projects, People, Events.
        3. CHAT: For general greetings or if no data is needed.
        
        If SQL tool is chosen, the argument MUST be a valid SQLite query.
        Return JSON: {{ "tool": "SQL" | "GRAPH" | "CHAT", "argument": "..." }}
        """
        
        try:
            plan = json.loads(ask_gemini_json(prompt))
            state.intent = plan.get("tool", "CHAT")
            state.tool_args = plan.get("argument")
        except:
            state.intent = "CHAT"
            
        return state

    def _node_tool_sql(self, state: ReasoningState):
        try:
            state.context_data = query_metrics_sql(state.tool_args)
        except Exception as e:
            state.context_data = f"SQL Error: {e}"
        return state

    def _node_tool_graph(self, state: ReasoningState):
        try:
            state.context_data = explore_context_graph(state.tool_args)
        except Exception as e:
            state.context_data = f"Graph Error: {e}"
        return state

    def _node_respond(self, state: ReasoningState):
        query = state.user_query
        context = state.context_data
        
        prompt = f"""
        User Query: "{query}"
        Context: {context}
        
        Task: Answer the user's question using the context AND determine the best UI widget.
        
        Return JSON validating against this schema:
        {{
            "text": "The answer...",
            "widget": {{
                "type": "bar_chart" | "line_chart" | "pie_chart" | "transaction_list" | "stat_card" | "none",
                "data": {{ ... }}
            }}
        }}
        """
        
        try:
            response_json = ask_gemini_json(prompt)
            # Validate with Pydantic
            response_data = json.loads(response_json)
            validated_response = ResponseModel(**response_data)
            
            state.final_response = validated_response
        except Exception as e:
            # Fallback
            state.final_response = ResponseModel(
                text=f"I found the data but couldn't format it perfectly. Context: {str(context)[:100]}...",
                widget=WidgetModel(type=WidgetType.NONE)
            )
            
        return state

    def _route_tool(self, state: ReasoningState):
        return state.intent

    def _format_history(self, history):
         if not history: return ""
         relevant = history[-5:]
         formatted = "History:\n"
         for msg in relevant:
             role = "User" if msg['role'] == 'user' else "Assistant"
             formatted += f"{role}: {msg['content']}\n"
         return formatted
