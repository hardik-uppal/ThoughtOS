import json
from logic.llm_engine import ask_gemini, ask_gemini_json, get_embedding
from logic.graph_db import GraphManager
from logic.sql_engine import get_thread_messages, update_thread_summary, log_event

class ChatEngine:
    def __init__(self):
        self.gm = GraphManager()

    def summarize_and_store_thread(self, thread_id):
        """
        1. Fetches messages for the thread.
        2. Generates a summary and extracts entities using LLM.
        3. Stores the summary in SQLite.
        4. Creates a ChatThread node in Neo4j and links it to entities.
        """
        messages = get_thread_messages(thread_id)
        if not messages:
            return {"status": "skipped", "reason": "No messages"}

        # Format transcript
        transcript = ""
        for msg in messages:
            role = "User" if msg['role'] == 'user' else "Assistant"
            transcript += f"{role}: {msg['content']}\n"

        # Generate Summary & Entities
        analysis = self._analyze_thread(transcript)
        
        if not analysis:
            return {"status": "error", "reason": "LLM analysis failed"}

        summary = analysis.get("summary", "")
        entities = analysis.get("entities", [])
        topic = analysis.get("topic", "General Chat")

        # Update SQLite
        update_thread_summary(thread_id, summary)

        # Store in Graph
        if self.gm.verify_connection():
            self._store_in_graph(thread_id, summary, topic, entities)
            return {"status": "success", "summary": summary, "entities": entities}
        else:
            return {"status": "partial_success", "reason": "Graph DB unavailable", "summary": summary}

    def _analyze_thread(self, transcript):
        """
        Uses LLM to summarize and extract entities.
        """
        prompt = f"""
        Analyze the following chat transcript.
        
        Transcript:
        {transcript}
        
        Tasks:
        1. Summarize the conversation in 1-2 sentences. Focus on decisions made or information retrieved.
        2. Identify the main Topic (short phrase).
        3. Extract key Entities mentioned (Merchants, People, Projects, Places).
        
        Return JSON:
        {{
            "summary": "...",
            "topic": "...",
            "entities": [
                {{ "name": "Uber", "type": "Merchant" }},
                {{ "name": "Project Alpha", "type": "Project" }}
            ]
        }}
        """
        try:
            response = ask_gemini_json(prompt)
            return json.loads(response)
        except Exception as e:
            log_event("ChatEngine", f"Analysis failed: {e}", level="ERROR")
            return None

    def _store_in_graph(self, thread_id, summary, topic, entities):
        """
        Creates nodes and relationships in Neo4j.
        """
        # 1. Create ChatThread Node
        embedding = get_embedding(summary)
        
        query_thread = """
        MERGE (c:ChatThread {id: $id})
        SET c.summary = $summary,
            c.topic = $topic,
            c.created_at = datetime(),
            c.embedding = $embedding
        """
        self.gm.query(query_thread, {
            "id": thread_id,
            "summary": summary,
            "topic": topic,
            "embedding": embedding
        })

        # 2. Link to Entities
        for entity in entities:
            name = entity['name']
            label = entity['type']
            
            # Sanitize label to avoid injection (allowlist)
            if label not in ["Merchant", "Person", "Project", "Place", "Event", "Topic"]:
                label = "Topic"

            query_link = f"""
            MATCH (c:ChatThread {{id: $id}})
            MERGE (e:{label} {{name: $name}})
            MERGE (c)-[:DISCUSSED]->(e)
            """
            self.gm.query(query_link, {"id": thread_id, "name": name})

        log_event("ChatEngine", f"Stored thread {thread_id} in graph with {len(entities)} links.", level="SUCCESS")
