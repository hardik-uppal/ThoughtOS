import json
import os

DATA_DIR = "data"

def _ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def save_json(filename, data):
    _ensure_data_dir()
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def load_json(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None

def save_plaid_token(token):
    save_json("plaid_token.json", {"access_token": token})

def load_plaid_token():
    data = load_json("plaid_token.json")
    return data.get("access_token") if data else None
