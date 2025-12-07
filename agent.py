import re
import random

class Agent:
    def __init__(self):
        self.name = "ContextOS Agent"

    def process_input(self, user_input, image=None, context=None, history=None):
        """
        Intelligent Router:
        1. Check for enrichment queue (if no context and not a command)
        2. Check for context-based template requests
        3. Check for Critical Commands (Backfill)
        4. Try Reasoning Engine (Graph-RAG)
        5. Fallback (if Gemini fails)
        """
        user_input_lower = user_input.lower()

        # 1. Check enrichment queue (conversational tagging)
        if not context and not self._is_command(user_input_lower):
            enrichment_question = self._check_enrichment_queue()
            if enrichment_question:
                return enrichment_question

        # 2. Context-based template (if context is set and user wants to log)
        if context and any(word in user_input_lower for word in ['log', 'record', 'add', 'save', 'note']):
            return self._generate_template_widget(context)

        # 3. Critical Commands (Hardcoded for reliability)
        if self._is_command(user_input_lower):
            return self._handle_backfill_request(user_input_lower)

        # 4. Try Reasoning Engine (Graph-RAG)
        try:
            from logic.reasoning_engine import ReasoningEngine
            engine = ReasoningEngine()
            
            # Include context in the query if present
            if context:
                enriched_query = f"[Context: {context.get('summary') or context.get('content_text')}] {user_input}"
                result = engine.process_query(enriched_query, history=history)
            else:
                result = engine.process_query(user_input, history=history)
            
            # Result is now a dict { "text": "...", "widget": { ... } }
            response_payload = {
                "type": "chat",
                "content": result.get("text", "I'm not sure.")
            }
            
            # Attach widget if present and not 'none'
            widget = result.get("widget")
            if widget and widget.get("type") != "none":
                response_payload["widget"] = {
                    "type": widget["type"],
                    "data": widget["data"]
                }
                
            return response_payload
                
        except Exception as e:
            print(f"Gemini Unavailable ({e}).")
            return {
                "type": "chat",
                "content": f"⚠️ **Gemini Unavailable**\n\nI couldn't connect to the AI brain (Error: {e}).\n\nPlease check your API key or try again later."
            }

    def _is_command(self, text):
        """Check if input is a command."""
        # Only trigger if "backfill" or "fetch" is explicitly mentioned
        if "backfill" in text or "fetch" in text:
            return True
        # Only trigger "history" if combined with "load" or "get"
        if "history" in text and ("load" in text or "get" in text):
            return True
        return False

    def _check_enrichment_queue(self):
        """Check for pending enrichment items and return a question."""
        from logic.sql_engine import get_needs_user_review
        import json
        
        items = get_needs_user_review()
        
        if not items:
            return None
        
        # Take first item
        item = items[0]
        options = json.loads(item.get('suggested_tags', '[]'))
        
        if not options:
            options = ["Shopping", "Food", "Transport", "Entertainment"]
            
        if "Other" not in options:
            options.append("Other")
        
        return {
            "type": "tag_selector",
            "content": f"🏷️ **Quick Question**\n\nI see you spent **${abs(item['amount']):.2f}** at **{item['merchant_name']}** on {item['date_posted']}.\n\n{item['clarification_question'] or 'How should I categorize this?'}",
            "data": {
                "txn_id": item['txn_id'],
                "merchant": item['merchant_name'],
                "amount": item['amount'],
                "options": options
            }
        }

    def _generate_template_widget(self, context):
        """
        Generates a form widget based on context type.
        """
        from logic.templates import detect_template_type, generate_template_widget
        
        template_type = detect_template_type(context)
        widget = generate_template_widget(template_type, context)
        
        return {
            "type": "form",
            "content": f"Here's a form to capture details:",
            "data": widget,
            "context_id": context.get('id'),
            "context_type": context.get('type')
        }

    def _handle_backfill_request(self, text):
        days = 30
        if "year" in text or "365" in text:
            days = 365
        elif "90" in text:
            days = 90
            
        return {
            "type": "action_backfill",
            "days": days,
            "content": f"Starting backfill for the last {days} days. Please wait..."
        }

