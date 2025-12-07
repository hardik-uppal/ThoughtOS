from logic.graph_db import GraphManager
import os

def check_graph():
    print(f"URI: {os.getenv('NEO4J_URI')}")
    # Don't print password
    print(f"User: {os.getenv('NEO4J_USERNAME')}")
    
    gm = GraphManager()
    if gm.verify_connection():
        print("Connection Successful!")
    else:
        print("Connection Failed!")

if __name__ == "__main__":
    check_graph()
