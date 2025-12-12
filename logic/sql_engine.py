import sqlite3
import json
import os
from datetime import datetime

DB_NAME = "context_os.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    """
    Initializes the SQLite database with the required tables.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Table 5: user_tokens (OAuth Credentials)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_tokens (
        user_id TEXT PRIMARY KEY,
        provider TEXT,              -- "google"
        access_token TEXT,
        refresh_token TEXT,
        token_uri TEXT,
        client_id TEXT,
        client_secret TEXT,
        scopes TEXT,
        expiry TEXT
    );
    """)

    # Table 1: master_transactions (Finance)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS master_transactions (
        txn_id TEXT PRIMARY KEY,       -- Plaid's 'transaction_id'
        account_id TEXT,               -- Link to bank account
        merchant_name TEXT,            -- Cleaned name (e.g., "Uber")
        amount REAL,                   -- Signed float (-15.50)
        currency TEXT,                 -- "USD"
        category TEXT,                 -- Primary category ("Food")
        date_posted TEXT,              -- ISO8601 "YYYY-MM-DD"
        raw_payload JSON,              -- The full original API response
        is_synced_to_graph BOOLEAN DEFAULT 0
    );
    """)
    
    # Indexes for master_transactions
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON master_transactions(date_posted);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_txn_merchant ON master_transactions(merchant_name);")

    # Table 2: master_events (Time)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS master_events (
        event_id TEXT PRIMARY KEY,     -- Google's 'id'
        summary TEXT,                  -- "Client Meeting"
        start_iso TEXT,                -- "2025-11-21T14:00:00Z"
        end_iso TEXT,
        series_id TEXT,                -- "recurringEventId"
        description TEXT,              -- The body of the invite
        attendees JSON,                -- List of emails
        is_synced_to_graph BOOLEAN DEFAULT 0
    );
    """)
    
    # Index for master_events
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_start ON master_events(start_iso);")

    # Table 3: master_entries (The Flexible Journal)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS master_entries (
        entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_type TEXT,               -- "THOUGHT", "TASK", "LOG_FOOD", "LOG_WORKOUT"
        content_text TEXT,             -- Searchable summary
        created_at TEXT,               -- ISO8601 timestamp
        payload JSON,                  -- Specific data
        is_synced_to_graph BOOLEAN DEFAULT 0
    );
    """)
    
    # Index for master_entries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entry_type ON master_entries(entry_type);")

    # Table 4: master_logs        # Master Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS master_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            level TEXT,
            component TEXT,
            message TEXT,
            metadata TEXT
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_log_time ON master_logs(timestamp);")

    # User Rules Table (for Onboarding/Calibration)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT UNIQUE,
            category TEXT,
            threshold_limit REAL,
            created_at TEXT
        )
    ''')

    # User Preferences Table (Global Settings)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    ''')

    # --- MIGRATION: Add Enrichment Columns if they don't exist ---
    # master_transactions
    try:
        cursor.execute("ALTER TABLE master_transactions ADD COLUMN enrichment_status TEXT DEFAULT 'PENDING'")
    except sqlite3.OperationalError:
        pass # Column likely exists
    
    try:
        cursor.execute("ALTER TABLE master_transactions ADD COLUMN clarification_question TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE master_transactions ADD COLUMN suggested_tags JSON")
    except sqlite3.OperationalError:
        pass

    # master_events
    try:
        cursor.execute("ALTER TABLE master_events ADD COLUMN enrichment_status TEXT DEFAULT 'PENDING'")
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute("ALTER TABLE master_events ADD COLUMN people_involved JSON")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE master_events ADD COLUMN project_link TEXT")
    except sqlite3.OperationalError:
        pass

    # Add embedding column for intelligent auto-tagger
    try:
        cursor.execute("ALTER TABLE master_transactions ADD COLUMN embedding BLOB")
    except sqlite3.OperationalError:
        pass

    # Chat Threads Tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_threads (
            thread_id TEXT PRIMARY KEY,
            created_at TEXT,
            updated_at TEXT,
            summary TEXT,
            is_active BOOLEAN DEFAULT 1
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id TEXT PRIMARY KEY,
            thread_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT,
            FOREIGN KEY(thread_id) REFERENCES chat_threads(thread_id)
        )
    ''')

    # --- MIGRATION: Add user_id column ---
    tables_to_migrate = [
        'master_transactions', 
        'master_events', 
        'master_entries', 
        'user_rules', 
        'chat_threads'
    ]
    
    # --- MIGRATION: Add user_id column ---
    tables_to_migrate = [
        'master_transactions', 
        'master_events', 
        'master_entries', 
        'user_rules', 
        'chat_threads'
    ]
    
    for table in tables_to_migrate:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id TEXT")
        except sqlite3.OperationalError:
            pass # Column likely exists

    # --- MIGRATION: Add user_tokens table (if not exists) ---
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_tokens (
        user_id TEXT PRIMARY KEY,
        provider TEXT,
        access_token TEXT,
        refresh_token TEXT,
        token_uri TEXT,
        client_id TEXT,
        client_secret TEXT,
        scopes TEXT,
        expiry TEXT
    );
    """)

    conn.commit()
    conn.close()

def upsert_transaction(user_id, txn):
    """
    Idempotent insert for Plaid transactions.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Extract fields safely
        txn_id = txn.get('id') or txn.get('transaction_id')
        merchant = txn.get('merchant') or txn.get('merchant_name') or txn.get('name')
        amount = txn.get('amount')
        category = txn.get('category', ['Uncategorized'])
        date = txn.get('date') or txn.get('date_posted')
        
        # Check for User Rules
        rules = cursor.execute("SELECT pattern, category FROM user_rules WHERE user_id = ?", (user_id,)).fetchall()
        
        final_category = category
        if isinstance(final_category, list):
            final_category = final_category[0]
            
        for pattern, rule_category in rules:
            if pattern.lower() in merchant.lower():
                final_category = rule_category
                break
        
        cursor.execute("""
            INSERT INTO master_transactions 
            (txn_id, user_id, merchant_name, amount, category, date_posted, raw_payload, enrichment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING')
            ON CONFLICT(txn_id) DO UPDATE SET
                amount=excluded.amount,
                category=excluded.category,
                raw_payload=excluded.raw_payload;
        """, (
            txn_id, 
            user_id,
            merchant, 
            amount, 
            final_category, 
            date, 
            json.dumps(txn)
        ))
        conn.commit()
    except Exception as e:
        print(f"Error upserting transaction {txn.get('id')}: {e}")
    finally:
        conn.close()

def upsert_event(user_id, event):
    """
    Idempotent insert for Google Calendar events.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO master_events 
            (event_id, user_id, summary, start_iso, end_iso, series_id, description, attendees, enrichment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            ON CONFLICT(event_id) DO UPDATE SET
                summary=excluded.summary,
                start_iso=excluded.start_iso,
                end_iso=excluded.end_iso,
                description=excluded.description;
        """, (
            event.get('id'),
            user_id,
            event.get('summary'),
            event.get('start_iso'),
            event.get('end_iso'),
            event.get('recurringEventId'),
            event.get('description'),
            json.dumps(event.get('attendees', [])),
        ))
        conn.commit()
    except Exception as e:
        print(f"Error upserting event {event.get('id')}: {e}")
    finally:
        conn.close()

def get_unsynced_data():
    """
    Fetches data meant for the Knowledge Graph.
    Now syncs ALL data regardless of enrichment status.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row # Allow accessing columns by name
    
    # Get new Transactions (ALL unsynced)
    txns = conn.execute(
        "SELECT * FROM master_transactions WHERE is_synced_to_graph = 0"
    ).fetchall()
    
    # Get new Events (ALL unsynced)
    events = conn.execute(
        "SELECT * FROM master_events WHERE is_synced_to_graph = 0"
    ).fetchall()
    
    conn.close()
    
    # Convert Row objects to dicts
    return [dict(t) for t in txns], [dict(e) for e in events]

def mark_as_synced(table_name, id_column, ids):
    """
    Marks rows as synced after successful graph ingestion.
    """
    if not ids:
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    
    placeholders = ','.join(['?'] * len(ids))
    query = f"UPDATE {table_name} SET is_synced_to_graph = 1 WHERE {id_column} IN ({placeholders})"
    
    cursor.execute(query, ids)
    conn.commit()
    conn.close()

# --- Enrichment Helpers ---

def get_pending_enrichment():
    """
    Fetches rows that need LLM processing (PENDING).
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    txns = conn.execute("""
        SELECT txn_id, merchant_name, amount, category, date_posted,
               enrichment_status, clarification_question, suggested_tags,
               is_synced_to_graph, raw_payload
        FROM master_transactions 
        WHERE enrichment_status = 'PENDING'
    """).fetchall()
    
    events = conn.execute(
        "SELECT * FROM master_events WHERE enrichment_status = 'PENDING'"
    ).fetchall()
    
    conn.close()
    return [dict(t) for t in txns], [dict(e) for e in events]

def get_needs_user_review(user_id):
    """
    Fetches rows that need User Review (NEEDS_USER) for a specific user.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    txns = conn.execute("""
        SELECT txn_id, merchant_name, amount, category, date_posted,
               enrichment_status, clarification_question, suggested_tags,
               is_synced_to_graph, raw_payload
        FROM master_transactions 
        WHERE user_id = ? AND enrichment_status = 'NEEDS_USER'
    """, (user_id,)).fetchall()
    
    conn.close()
    return [dict(t) for t in txns]

def update_enrichment_status(table, id_col, item_id, status, updates=None):
    """
    Updates the enrichment status and other fields (e.g. category, question).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Base update
    query = f"UPDATE {table} SET enrichment_status = ? WHERE {id_col} = ?"
    params = [status, item_id]
    
    cursor.execute(query, params)
    
    # Optional extra updates (e.g. category, question)
    if updates:
        for col, val in updates.items():
            cursor.execute(f"UPDATE {table} SET {col} = ? WHERE {id_col} = ?", (val, item_id))
            
    conn.commit()
    conn.close()

def reset_enrichment_status():
    """
    Resets all transactions and events to 'PENDING' enrichment status.
    Used for retroactive enrichment (re-processing old data with new logic).
    Also resets is_synced_to_graph to 0 so they get updated in Neo4j.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Reset Transactions
    cursor.execute("UPDATE master_transactions SET enrichment_status = 'PENDING', is_synced_to_graph = 0")
    
    # Reset Events
    cursor.execute("UPDATE master_events SET enrichment_status = 'PENDING', is_synced_to_graph = 0")
    
    conn.commit()
    conn.close()

def log_event(component, message, level="INFO", metadata=None):
    """
    Logs a system event to the master_logs table.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO master_logs (timestamp, component, message, level, metadata)
            VALUES (datetime('now'), ?, ?, ?, ?)
        """, (component, message, level, json.dumps(metadata) if metadata else None))
        conn.commit()
    except Exception as e:
        print(f"Logging Error: {e}")
    finally:
        conn.close()
        
    # Also log to file for redundancy
    try:
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] [{component}] {message} | {metadata}\n"
        with open("system.log", "a") as f:
            f.write(log_entry)
    except Exception:
        pass

def get_logs(limit=50):
    """
    Fetches the most recent logs.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    logs = conn.execute(
        f"SELECT * FROM master_logs ORDER BY timestamp DESC LIMIT {limit}"
    ).fetchall()
    
    conn.close()
    return [dict(l) for l in logs]

def clear_logs():
    """Clears all logs from the database."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM master_logs")
    conn.commit()
    conn.close()

# --- Onboarding / Rules Helpers ---

def add_rule(user_id, pattern, category, threshold=None):
    """Adds a categorization rule."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Insert Rule
        cursor.execute('''
            INSERT OR REPLACE INTO user_rules (user_id, pattern, category, threshold_limit, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', (user_id, pattern, category, threshold))
        
        # 2. Apply Retroactively
        # Update all transactions where merchant_name contains pattern (case-insensitive)
        # AND category is different (to avoid redundant updates)
        cursor.execute('''
            UPDATE master_transactions
            SET category = ?, enrichment_status = 'COMPLETE'
            WHERE user_id = ? AND lower(merchant_name) LIKE ? AND category != ?
        ''', (category, user_id, f"%{pattern.lower()}%", category))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding rule: {e}")
        return False
    finally:
        conn.close()

def get_rules(user_id=None):
    """Fetches all user rules."""
    conn = get_connection()
    cursor = conn.cursor()
    
    if user_id:
        cursor.execute("SELECT pattern, category, threshold_limit FROM user_rules WHERE user_id = ?", (user_id,))
    else:
        cursor.execute("SELECT pattern, category, threshold_limit FROM user_rules")
        
    rules = [{"pattern": row[0], "category": row[1], "threshold": row[2]} for row in cursor.fetchall()]
    conn.close()
    return rules

def set_preference(key, value):
    """Sets a global preference."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO user_preferences (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
    ''', (key, str(value)))
    conn.commit()
    conn.close()

def get_preference(key, default=None):
    """Gets a global preference."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def get_thoughts(user_id):
    """
    Fetches all thoughts/tasks from master_entries.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM master_entries WHERE user_id = ? AND entry_type = 'thought' ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_transactions(user_id, limit=100):
    """Fetches recent transactions."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM master_transactions WHERE user_id = ? ORDER BY date_posted DESC LIMIT ?", (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_events(user_id, limit=100, start_date=None, end_date=None):
    """Fetches recent events, optionally filtering by date range."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT * FROM master_events WHERE user_id = ?"
    params = [user_id]
    
    if start_date:
        query += " AND start_iso >= ?"
        params.append(start_date)
        
    if end_date:
        query += " AND start_iso <= ?"
        params.append(end_date)
        
    query += " ORDER BY start_iso ASC LIMIT ?"
    params.append(limit)
    
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# --- Chat Thread Helpers ---

def create_thread(user_id):
    """Creates a new chat thread."""
    import uuid
    thread_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_threads (thread_id, user_id, created_at, updated_at, is_active)
        VALUES (?, ?, datetime('now'), datetime('now'), 1)
    ''', (thread_id, user_id))
    conn.commit()
    conn.close()
    return thread_id

def save_message(thread_id, role, content):
    """Saves a message to a thread."""
    import uuid
    message_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_messages (message_id, thread_id, role, content, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    ''', (message_id, thread_id, role, content))
    
    # Update thread timestamp
    cursor.execute('''
        UPDATE chat_threads SET updated_at = datetime('now') WHERE thread_id = ?
    ''', (thread_id,))
    
    conn.commit()
    conn.close()

def get_thread_messages(thread_id, limit=50):
    """Fetches messages from a thread."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    messages = conn.execute('''
        SELECT role, content, created_at 
        FROM chat_messages 
        WHERE thread_id = ? 
        ORDER BY created_at ASC 
        LIMIT ?
    ''', (thread_id, limit)).fetchall()
    conn.close()
    return [dict(m) for m in messages]

def update_thread_summary(thread_id, summary):
    """
    Updates the summary of a chat thread.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE chat_threads SET summary = ?, updated_at = CURRENT_TIMESTAMP WHERE thread_id = ?", (summary, thread_id))
    conn.commit()
    conn.close()

def get_active_thread(user_id):
    """Gets the most recent active thread for a user."""
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    thread = conn.execute('''
        SELECT thread_id FROM chat_threads 
        WHERE user_id = ? AND is_active = 1 
        ORDER BY updated_at DESC 
        LIMIT 1
    ''', (user_id,)).fetchone()
    conn.close()
    return dict(thread)['thread_id'] if thread else None

def store_user_token(user_id, creds_data):
    """
    Stores OAuth credentials for a user.
    creds_data should be a dictionary with token fields.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO user_tokens 
        (user_id, provider, access_token, refresh_token, token_uri, client_id, client_secret, scopes, expiry)
        VALUES (?, 'google', ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        creds_data.get('token'),
        creds_data.get('refresh_token'),
        creds_data.get('token_uri'),
        creds_data.get('client_id'),
        creds_data.get('client_secret'),
        json.dumps(creds_data.get('scopes', [])),
        creds_data.get('expiry') # ISO string or timestamp
    ))
    conn.commit()
    conn.close()

def get_user_token(user_id):
    """
    Retrieves OAuth credentials for a user.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM user_tokens WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        data = dict(row)
        if data['scopes']:
            try:
                data['scopes'] = json.loads(data['scopes'])
            except:
                data['scopes'] = []
        return data
    return None

def get_recent_activity(user_id, limit=10):
    """
    Fetches a mixed stream of recent activity (Transactions, Events, Thoughts).
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    
    # Transactions
    txns = conn.execute(f"SELECT 'transaction' as type, txn_id as id, merchant_name as title, amount as subtitle, date_posted as timestamp FROM master_transactions WHERE user_id = ? ORDER BY date_posted DESC LIMIT {limit}", (user_id,)).fetchall()
    
    # Events
    events = conn.execute(f"SELECT 'event' as type, event_id as id, summary as title, start_iso as subtitle, start_iso as timestamp FROM master_events WHERE user_id = ? ORDER BY start_iso DESC LIMIT {limit}", (user_id,)).fetchall()
    
    # Thoughts/Tasks
    thoughts = conn.execute(f"SELECT 'task' as type, entry_id as id, content_text as title, 'Task' as subtitle, created_at as timestamp FROM master_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT {limit}", (user_id,)).fetchall()
    
    conn.close()
    
    combined = [dict(row) for row in txns] + [dict(row) for row in events] + [dict(row) for row in thoughts]
    
    # Sort by timestamp desc
    combined.sort(key=lambda x: x['timestamp'] or "", reverse=True)
    
    return combined[:limit]

