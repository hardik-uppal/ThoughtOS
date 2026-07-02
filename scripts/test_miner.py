import sqlite3
import json
import urllib.request
import urllib.parse
import os

DB_PATH = "/home/hardik/Projects/ThoughtOS/context_os.db"
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent?key={GOOGLE_API_KEY}"

SYSTEM_PROMPT = """You are a precise data mining agent. Your job is to extract semantic meaning from notes.
Do NOT hallucinate. Do NOT extract common words (e.g., "Good idea", "Tomorrow", "Meeting").
Only extract proper nouns, specific technologies, projects, or clear actionable TODOs.

Return ONLY a valid JSON object in the following format:
{
  "entities": [
    {"name": "Entity Name", "type": "Project|Person|Concept", "confidence": 0.95}
  ],
  "todos": [
    {"action": "Specific task", "context": "Context from note"}
  ],
  "ambiguities": [
    "Any questions you need to ask the user to clarify this note"
  ]
}
"""

def query_llm(text):
    prompt = f"{SYSTEM_PROMPT}\n\nNOTE CONTENT:\n{text}\n\nJSON:"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    req = urllib.request.Request(GEMINI_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        response = urllib.request.urlopen(req)
        result = json.loads(response.read().decode('utf-8'))
        return json.loads(result['candidates'][0]['content']['parts'][0]['text'])
    except Exception as e:
        return {"error": str(e)}

IGNORE_LIST = {"idea", "thought", "today", "tomorrow", "stuff", "things", "meeting", "week"}
HUB_NODES = {"blog", "app", "project", "website"}
ROOT_NODES = {"hardik", "i", "me", "my wife", "vanika"}

def post_process_entities(data):
    if "entities" not in data:
        return data
        
    filtered_entities = []
    for e in data["entities"]:
        name_lower = e["name"].lower().strip()
        
        # 1. Filter out ignored words
        if name_lower in IGNORE_LIST:
            continue
            
        # 2. Map to Root Nodes
        if name_lower in ROOT_NODES:
            e["type"] = "Root/Self"
            
        # 3. Map to Hub Nodes
        elif name_lower in HUB_NODES:
            e["type"] = "Hub/Medium"
            
        filtered_entities.append(e)
        
    data["entities"] = filtered_entities
    return data

def test_miner():
    print(f"Connecting to DB: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("Database not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Let's grab the last 5 notes
    cursor.execute("SELECT note_id, raw_text, created_at FROM notes ORDER BY created_at DESC LIMIT 5;")
    notes = cursor.fetchall()
    
    if not notes:
        print("No notes found in the 'notes' table. Trying 'master_entries'...")
        cursor.execute("SELECT entry_id, content_text, created_at FROM master_entries WHERE entry_type='THOUGHT' ORDER BY created_at DESC LIMIT 5;")
        notes = cursor.fetchall()
        
    for note in notes:
        note_id = note[0]
        text = note[1]
        
        if not text or len(text.strip()) < 10:
            continue
            
        print("-" * 50)
        print(f"MINING NOTE [{note_id}]: {text[:100]}...")
        
        extracted_data = query_llm(text)
        if "error" not in extracted_data:
            extracted_data = post_process_entities(extracted_data)
        print(json.dumps(extracted_data, indent=2))
        
    conn.close()

if __name__ == "__main__":
    test_miner()
