import json
from logic.llm_engine import ask_gemini, ask_gemini_json
from logic.tools import query_metrics_sql, explore_context_graph

from logic.sql_engine import log_event

class ReasoningEngine:
    def __init__(self):
        pass
        
    def process_query(self, user_query, history=None):
        """
        Main entry point.
        1. Classify Intent
        2. Execute Tool
        3. Synthesize Answer
        """
        # 1. Classify
        plan = self._classify_intent(user_query, history)
        
        tool_name = plan.get("tool")
        tool_arg = plan.get("argument")
        
        log_event("ReasoningEngine", f"Classified query: {tool_name}", level="INFO", metadata=plan)
        
        context = ""
        
        # 2. Execute
        if tool_name == "SQL":
            context = query_metrics_sql(tool_arg)
        elif tool_name == "GRAPH":
            context = explore_context_graph(tool_arg)
        elif tool_name == "CHAT":
            # Pass history to chat
            history_str = self._format_history(history)
            response_text = ask_gemini(f"{history_str}\nUser says: {user_query}")
            return {"text": response_text, "widget": {"type": "none"}}
            
        # 3. Synthesize
        return self._synthesize_answer(user_query, context, tool_name, history)

    def _format_history(self, history):
        if not history:
            return ""
        # Take last 5 turns
        relevant = history[-5:]
        formatted = "Conversation History:\n"
        for msg in relevant:
            role = "User" if msg['role'] == 'user' else "Assistant"
            formatted += f"{role}: {msg['content']}\n"
        return formatted

    def _classify_intent(self, query, history=None):
        """
        Decides which tool to use.
        """
        history_str = self._format_history(history)
        
        prompt = f"""
        You are the Brain of ContextOS.
        {history_str}
        User Query: "{query}"
        
        Available Tools:
        1. SQL: For quantitative questions about Money/Transactions (How much, Total, Sum, Count).
           - Argument: A READ-ONLY SQL query for table 'master_transactions'. 
           - Columns: amount, category, merchant_name, date_posted (YYYY-MM-DD).
           - Rules:
             * Use SQLite syntax.
             * Use SQLite syntax.
             * For dates: Use date('now', '-90 days') for recent history unless specified otherwise.
             * For strings: Use LIKE or LOWER() for case-insensitive matching.
           - Example: "SELECT sum(amount) FROM master_transactions WHERE category LIKE 'Food%' AND date_posted >= date('now', '-90 days')"
           
        2. GRAPH: For qualitative questions about Context, Why, Relationships, Projects, People, OR Past Conversations.
           - Argument: The key entity string to search for.
           - Example: "Project Alpha", "Meeting with Bob", "Renovations discussion"
           
        3. CHAT: For general greetings, philosophy, or if no data is needed.
           - Argument: null
           
        Return JSON:
        {{
            "tool": "SQL" | "GRAPH" | "CHAT",
            "argument": "The SQL query OR The Entity String OR null"
        }}
        """
        try:
            response = ask_gemini_json(prompt)
            return json.loads(response)
        except:
            return {"tool": "CHAT", "argument": None}

    def _synthesize_answer(self, query, context, tool_used, history=None):
        """
        Generates the final response based on tool output.
        """
        history_str = self._format_history(history)
        
        prompt = f"""
        {history_str}
        User Query: "{query}"
        Tool Used: {tool_used}
        Context Retrieved:
        {context}
        
        Task: Answer the user's question using the context AND recommend a UI widget to visualize it.
        
        Available Widgets:
        1. "bar_chart": For comparing categories or time periods.
           - data: {{ "title": "...", "labels": ["A", "B"], "values": [10, 20], "series_name": "Spend" }}
        2. "line_chart": For trends over time.
           - data: {{ "title": "...", "labels": ["Jan", "Feb"], "values": [10, 20], "series_name": "Balance" }}
        3. "transaction_list": For showing a list of transactions.
           - data: {{ "transactions": [ {{ "date": "...", "merchant": "...", "amount": 10.0 }} ] }}
        4. "stat_card": For a single important number.
           - data: {{ "label": "Total Spend", "value": "$500", "trend": "+10%" }}
        5. "none": Text only.
        
        Return JSON:
        {{
            "text": "The natural language answer...",
            "widget": {{
                "type": "bar_chart" | "line_chart" | "transaction_list" | "stat_card" | "none",
                "data": {{ ... }}
            }}
        }}
        """
        try:
            response = ask_gemini_json(prompt)
            return json.loads(response)
        except Exception as e:
            # Fallback to text if JSON parsing fails
            return {
                "text": f"I found some data but couldn't visualize it perfectly. Context: {str(context)[:200]}...",
                "widget": {"type": "none"}
            }
