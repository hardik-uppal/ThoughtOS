import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

class GraphManager:
    def __init__(self):
        self.driver = None
        if NEO4J_URI and NEO4J_USERNAME and NEO4J_PASSWORD:
            try:
                self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
            except Exception as e:
                print(f"Failed to create Neo4j driver: {e}")

    def close(self):
        if self.driver:
            self.driver.close()

    def query(self, query, parameters=None):
        if not self.driver:
            return None
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters)
                return [record.data() for record in result]
        except Exception as e:
            print(f"Query failed: {e}")
            return None

    def run_cypher(self, query, parameters=None):
        """
        Generic wrapper for executing read-only queries.
        Returns a list of dictionaries.
        """
        if not self.driver:
            return []
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [dict(record) for record in result]

    def get_spending_by_category(self):
        """
        Aggregates spending by category.
        """
        query = """
        MATCH (t:Transaction)
        WHERE t.amount > 0
        RETURN t.category as category, sum(t.amount) as total
        ORDER BY total DESC
        """
        return self.run_cypher(query)

    def get_top_merchants(self):
        """
        Returns top merchants by transaction count and total spend.
        """
        query = """
        MATCH (t:Transaction)-[:PAID_TO]->(m:Merchant)
        RETURN m.name as merchant, count(t) as count, sum(t.amount) as total
        ORDER BY total DESC
        LIMIT 5
        """
        return self.run_cypher(query)

    def verify_connection(self):
        if not self.driver:
            return False
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    def create_vector_index(self):
        """
        Creates a vector index on Thought, Event, and ChatThread nodes.
        """
        if not self.driver: return
        
        # Create index for Thoughts
        query_thought = """
        CREATE VECTOR INDEX thought_embeddings IF NOT EXISTS
        FOR (n:Thought)
        ON (n.embedding)
        OPTIONS {indexConfig: {
         `vector.dimensions`: 768,
         `vector.similarity_function`: 'cosine'
        }}
        """
        self.run_cypher(query_thought)
        
        # Create index for Events
        query_event = """
        CREATE VECTOR INDEX event_embeddings IF NOT EXISTS
        FOR (n:Event)
        ON (n.embedding)
        OPTIONS {indexConfig: {
         `vector.dimensions`: 768,
         `vector.similarity_function`: 'cosine'
        }}
        """
        self.run_cypher(query_event)
        
        # Create index for ChatThreads
        query_chat = """
        CREATE VECTOR INDEX chat_embeddings IF NOT EXISTS
        FOR (n:ChatThread)
        ON (n.embedding)
        OPTIONS {indexConfig: {
         `vector.dimensions`: 768,
         `vector.similarity_function`: 'cosine'
        }}
        """
        self.run_cypher(query_chat)
        
        print("Vector indexes created.")

    def update_embeddings(self):
        """
        Finds nodes without embeddings, generates them via Gemini, and updates the graph.
        """
        from logic.llm_engine import get_embedding
        
        # 1. Thoughts
        thoughts = self.run_cypher("MATCH (n:Thought) WHERE n.embedding IS NULL RETURN n.id as id, n.content as text")
        for t in thoughts:
            emb = get_embedding(t['text'])
            if emb:
                self.query("MATCH (n:Thought {id: $id}) SET n.embedding = $emb", {"id": t['id'], "emb": emb})
                
        # 2. Events
        events = self.run_cypher("MATCH (n:Event) WHERE n.embedding IS NULL RETURN n.id as id, n.summary as text")
        for e in events:
            emb = get_embedding(e['text'])
            if emb:
                self.query("MATCH (n:Event {id: $id}) SET n.embedding = $emb", {"id": e['id'], "emb": emb})
                
        print(f"Updated embeddings for {len(thoughts)} Thoughts and {len(events)} Events.")
