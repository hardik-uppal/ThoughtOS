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

    def get_spending_by_category(self, user_id):
        """
        Aggregates spending by category for a specific user.
        """
        query = """
        MATCH (t:Transaction)
        WHERE t.user_id = $user_id AND t.amount > 0
        RETURN t.category as category, sum(t.amount) as total
        ORDER BY total DESC
        """
        return self.run_cypher(query, {"user_id": user_id})

    def get_top_merchants(self, user_id):
        """
        Returns top merchants by transaction count and total spend for a specific user.
        """
        query = """
        MATCH (t:Transaction)-[:PAID_TO]->(m:Merchant)
        WHERE t.user_id = $user_id
        RETURN m.name as merchant, count(t) as count, sum(t.amount) as total
        ORDER BY total DESC
        LIMIT 5
        """
        return self.run_cypher(query, {"user_id": user_id})

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

    def create_thought(self, content, links=None):
        """
        Creates a Thought node and links it to existing nodes.
        """
        if not self.driver: return False
        
        # 1. Create Thought Node
        query_create = """
        CREATE (t:Thought {
            id: randomUUID(),
            content: $content,
            created_at: datetime(),
            type: 'thought'
        })
        RETURN t.id as id
        """
        result = self.query(query_create, {"content": content})
        if not result: return False
        
        thought_id = result[0]['id']
        
        # 2. Create Links
        if links:
            query_link = """
            MATCH (t:Thought {id: $thought_id})
            MATCH (n) WHERE n.id IN $links
            MERGE (t)-[:RELATED_TO]->(n)
            """
            self.query(query_link, {"thought_id": thought_id, "links": links})
            
        # 3. Generate Embedding (Async ideally, but sync for now)
        try:
            from logic.llm_engine import get_embedding
            emb = get_embedding(content)
            if emb:
                self.query("MATCH (n:Thought {id: $id}) SET n.embedding = $emb", {"id": thought_id, "emb": emb})
        except Exception as e:
            print(f"Failed to generate embedding for thought: {e}")
            
        return True

    def create_archive(self, content):
        """
        Creates an Archive node (disconnected from graph context, but searchable).
        """
        if not self.driver: return False
        
        query_create = """
        CREATE (a:Archive {
            id: randomUUID(),
            content: $content,
            created_at: datetime(),
            type: 'archive'
        })
        RETURN a.id as id
        """
        result = self.query(query_create, {"content": content})
        return bool(result)

    def find_similar_nodes(self, text, limit=5):
        """
        Vector search for similar nodes (Thoughts, Events, ChatThreads).
        """
        if not self.driver: return []
        
        try:
            from logic.llm_engine import get_embedding
            emb = get_embedding(text)
            if not emb: return []
            
            # Search over multiple indices or just one generic if unified. 
            # For now, let's search Thoughts and Events.
            
            # Simple approach: Union of searches (Neo4j < 5.x might not support multi-index vector search easily without UNION)
            query = """
            CALL db.index.vector.queryNodes('thought_embeddings', $limit, $emb)
            YIELD node, score
            RETURN node.id as id, node.content as name, 'Thought' as type, score as similarity
            UNION
            CALL db.index.vector.queryNodes('event_embeddings', $limit, $emb)
            YIELD node, score
            RETURN node.id as id, node.summary as name, 'Event' as type, score as similarity
            ORDER BY similarity DESC
            LIMIT $limit
            """
            return self.run_cypher(query, {"emb": emb, "limit": limit})
        except Exception as e:
            print(f"Vector search failed: {e}")
            return []
