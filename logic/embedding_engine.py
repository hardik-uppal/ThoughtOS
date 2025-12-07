import google.generativeai as genai
import numpy as np
import sqlite3
import os

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def generate_embedding(text):
    """Generate embedding for text using Gemini."""
    try:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        return np.array(result['embedding'], dtype=np.float32)
    except Exception as e:
        print(f"Embedding error: {e}")
        return None

def find_similar_transactions(merchant_name, limit=5):
    """Find similar transactions using cosine similarity."""
    query_embedding = generate_embedding(merchant_name)
    
    if query_embedding is None:
        return []
    
    conn = sqlite3.connect("context_os.db")
    conn.row_factory = sqlite3.Row
    
    # Get all transactions with embeddings and categories
    rows = conn.execute("""
        SELECT merchant_name, category, embedding 
        FROM master_transactions 
        WHERE embedding IS NOT NULL 
        AND category IS NOT NULL 
        AND enrichment_status = 'COMPLETE'
    """).fetchall()
    
    conn.close()
    
    if not rows:
        return []
    
    similarities = []
    for row in rows:
        try:
            emb = np.frombuffer(row['embedding'], dtype=np.float32)
            similarity = np.dot(query_embedding, emb) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(emb)
            )
            similarities.append({
                "merchant_name": row['merchant_name'],
                "category": row['category'],
                "similarity": float(similarity)
            })
        except Exception as e:
            print(f"Similarity calculation error: {e}")
            continue
    
    # Sort by similarity
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    return similarities[:limit]

def store_embedding(txn_id, merchant_name):
    """Generate and store embedding for a transaction."""
    embedding = generate_embedding(merchant_name)
    
    if embedding is None:
        return False
    
    conn = sqlite3.connect("context_os.db")
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE master_transactions SET embedding = ? WHERE txn_id = ?",
            (embedding.tobytes(), txn_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Store embedding error: {e}")
        return False
    finally:
        conn.close()
