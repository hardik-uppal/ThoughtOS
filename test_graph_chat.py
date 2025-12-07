import requests
import time
import sqlite3
from logic.sql_engine import create_thread, save_message, get_connection
from logic.tools import explore_context_graph

def test_graph_chat():
    print("1. Creating Thread...")
    thread_id = create_thread()
    print(f"Thread ID: {thread_id}")

    print("2. Adding Messages...")
    save_message(thread_id, "user", "I'm thinking of renovating my kitchen.")
    save_message(thread_id, "assistant", "That sounds exciting! What's your budget?")
    save_message(thread_id, "user", "I want to spend around $15,000. I need a new stove and cabinets.")
    save_message(thread_id, "assistant", "Got it. $15k for stove and cabinets. Do you have a contractor?")
    save_message(thread_id, "user", "Not yet, I'm looking for one.")

    print("3. Closing Thread (Triggering Summarization)...")
    response = requests.post("http://localhost:8000/api/chat/thread/close", json={"thread_id": thread_id})
    print(f"Close Response: {response.json()}")

    print("4. Waiting for Background Task (5s)...")
    time.sleep(5)

    print("5. Checking SQLite Summary...")
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT summary FROM chat_threads WHERE thread_id = ?", (thread_id,)).fetchone()
    conn.close()
    print(f"Summary in DB: {row[0] if row else 'None'}")

    print("6. Testing Graph Retrieval...")
    # We search for "kitchen renovation" which should match the summary
    result = explore_context_graph("kitchen renovation")
    print(f"Graph Result: {result}")

if __name__ == "__main__":
    test_graph_chat()
