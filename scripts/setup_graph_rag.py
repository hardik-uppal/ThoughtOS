import sys
import os

# Add parent directory to path so we can import logic
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logic.graph_db import GraphManager

def main():
    print("🚀 Initializing Graph-RAG Setup...")
    
    gm = GraphManager()
    if not gm.verify_connection():
        print("❌ Error: Could not connect to Neo4j. Check .env")
        return

    print("\n1️⃣  Creating Vector Indexes...")
    gm.create_vector_index()
    
    print("\n2️⃣  Generating Embeddings (this may take a moment)...")
    gm.update_embeddings()
    
    print("\n✅ Setup Complete! The Graph is now semantic.")
    gm.close()

if __name__ == "__main__":
    main()
