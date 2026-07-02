"""SQLite graph storage for entities, relationships, and extraction rules.

Design principles:
- Zero new dependencies (SQLite is built-in)
- Recursive CTEs for graph traversal
- Fuzzy matching via trigram similarity (built-in)
- Versioned extraction rules that can be proposed/reviewed/accepted
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .config import Config

# --- Schema ---

GRAPH_SCHEMA = """
-- Entities extracted from notes
CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,           -- person, project, tool, concept, document, event, org
    aliases TEXT DEFAULT '[]',    -- JSON array of alternative names
    source_note_id TEXT,
    confidence REAL DEFAULT 1.0,
    metadata JSON DEFAULT '{}',
    created_at TEXT,
    last_seen_at TEXT,
    user_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_entities_user ON entities(user_id);

-- Relationships between entities
CREATE TABLE IF NOT EXISTS relationships (
    rel_id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,   -- discussed, uses, depends_on, part_of, compared_with, etc.
    source_note_id TEXT,
    confidence REAL DEFAULT 1.0,
    metadata JSON DEFAULT '{}',
    created_at TEXT,
    user_id TEXT,
    FOREIGN KEY(source_entity_id) REFERENCES entities(entity_id),
    FOREIGN KEY(target_entity_id) REFERENCES entities(entity_id)
);

CREATE INDEX IF NOT EXISTS idx_rels_source ON relationships(source_entity_id);
CREATE INDEX IF NOT EXISTS idx_rels_target ON relationships(target_entity_id);
CREATE INDEX IF NOT EXISTS idx_rels_type ON relationships(relation_type);

-- Extraction rules (regex patterns for Stage 1)
CREATE TABLE IF NOT EXISTS extraction_rules (
    rule_id TEXT PRIMARY KEY,
    pattern TEXT NOT NULL,           -- regex pattern
    entity_type TEXT,                -- what entity type this extracts
    relation_type TEXT,              -- if this is a relationship pattern
    source_entity_type TEXT,         -- for relationship rules
    target_entity_type TEXT,         -- for relationship rules
    priority INTEGER DEFAULT 0,      -- higher = applied first
    confidence REAL DEFAULT 0.8,
    enabled BOOLEAN DEFAULT 1,
    source_llm TEXT,                 -- which LLM proposed this rule
    source_note_id TEXT,            -- which note led to this rule
    accepted BOOLEAN DEFAULT 1,     -- reviewed and accepted
    usage_count INTEGER DEFAULT 0,  -- how many times triggered
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_rules_enabled ON extraction_rules(enabled, priority DESC);

-- Extraction history (for debugging/review/improvement)
CREATE TABLE IF NOT EXISTS extraction_log (
    log_id TEXT PRIMARY KEY,
    note_id TEXT,
    stage TEXT,                     -- rule_engine, llm, dedup, rule_gen
    input_summary TEXT,             -- brief description of input
    output_summary TEXT,            -- what was extracted
    llm_provider TEXT,
    llm_model TEXT,
    duration_ms REAL,
    success BOOLEAN,
    details JSON DEFAULT '{}',
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_extlog_note ON extraction_log(note_id);

-- Extraction state per note (for smart reruns)
CREATE TABLE IF NOT EXISTS note_extraction_state (
    note_id TEXT PRIMARY KEY,
    rule_hash TEXT,               -- hash of all enabled rule patterns applied
    llm_fingerprint TEXT,         -- provider:model used
    entity_count INTEGER DEFAULT 0,
    relationship_count INTEGER DEFAULT 0,
    last_extracted_at TEXT,
    extraction_version INTEGER DEFAULT 1,
    FOREIGN KEY(note_id) REFERENCES notes(note_id)
);

CREATE INDEX IF NOT EXISTS idx_ext_state_hash ON note_extraction_state(rule_hash);
"""


# --- DB Connection ---


class GraphStore:
    """SQLite-backed graph store for entities, relationships, and extraction rules."""

    def __init__(self, db_path: str = "context_os.db"):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def init(self):
        """Initialize graph tables."""
        conn = self._conn()
        try:
            conn.executescript(GRAPH_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def _now(self) -> str:
        return datetime.utcnow().isoformat(timespec="seconds") + "Z"

    # --- Entity CRUD ---

    def upsert_entity(
        self,
        name: str,
        entity_type: str,
        user_id: str,
        source_note_id: Optional[str] = None,
        aliases: Optional[List[str]] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict] = None,
        entity_id: Optional[str] = None,
    ) -> Dict:
        """Create or update an entity."""
        conn = self._conn()
        try:
            eid = entity_id or str(uuid.uuid4())
            now = self._now()
            aliases_json = json.dumps(aliases or [])
            meta_json = json.dumps(metadata or {})

            conn.execute(
                """INSERT INTO entities
                   (entity_id, name, type, aliases, source_note_id, confidence,
                    metadata, created_at, last_seen_at, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(entity_id) DO UPDATE SET
                     name=excluded.name, type=excluded.type,
                     aliases=excluded.aliases, confidence=excluded.confidence,
                     metadata=excluded.metadata, last_seen_at=excluded.last_seen_at""",
                (eid, name, entity_type, aliases_json, source_note_id,
                 confidence, meta_json, now, now, user_id),
            )
            conn.commit()
            return self.get_entity(eid) or {}
        finally:
            conn.close()

    def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get a single entity by ID."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM entities WHERE entity_id = ?", (entity_id,)
            ).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            conn.close()

    def find_entities(
        self,
        user_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Search entities with optional filters."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM entities WHERE 1=1"
            params: List[Any] = []

            if user_id:
                sql += " AND user_id = ?"
                params.append(user_id)
            if entity_type:
                sql += " AND type = ?"
                params.append(entity_type)
            if query:
                sql += " AND (name LIKE ? OR aliases LIKE ?)"
                pattern = f"%{query}%"
                params.extend([pattern, pattern])

            sql += " ORDER BY last_seen_at DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def delete_entity(self, entity_id: str) -> bool:
        """Delete an entity and its relationships."""
        conn = self._conn()
        try:
            conn.execute("DELETE FROM relationships WHERE source_entity_id = ? OR target_entity_id = ?",
                         (entity_id, entity_id))
            conn.execute("DELETE FROM entities WHERE entity_id = ?", (entity_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    # --- Relationship CRUD ---

    def create_relationship(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: str,
        user_id: str,
        source_note_id: Optional[str] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        """Create a relationship between two entities."""
        conn = self._conn()
        try:
            rel_id = str(uuid.uuid4())
            now = self._now()
            meta_json = json.dumps(metadata or {})

            conn.execute(
                """INSERT OR REPLACE INTO relationships
                   (rel_id, source_entity_id, target_entity_id, relation_type,
                    source_note_id, confidence, metadata, created_at, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (rel_id, source_entity_id, target_entity_id, relation_type,
                 source_note_id, confidence, meta_json, now, user_id),
            )
            conn.commit()
            return self.get_relationship(rel_id) or {}
        finally:
            conn.close()

    def get_relationship(self, rel_id: str) -> Optional[Dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM relationships WHERE rel_id = ?", (rel_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def find_relationships(
        self,
        entity_id: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Find relationships involving an entity."""
        conn = self._conn()
        try:
            if entity_id:
                rows = conn.execute(
                    """SELECT * FROM relationships
                       WHERE source_entity_id = ? OR target_entity_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (entity_id, entity_id, limit),
                ).fetchall()
            elif relation_type:
                rows = conn.execute(
                    "SELECT * FROM relationships WHERE relation_type = ? LIMIT ?",
                    (relation_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM relationships ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    # --- Graph traversal ---

    def get_entity_web(
        self, entity_id: str, max_hops: int = 2
    ) -> Dict:
        """Get an entity and its neighborhood up to max_hops away.

        Returns a dict with 'entity', 'relationships', and 'neighbors'.
        """
        conn = self._conn()
        try:
            entity = self.get_entity(entity_id)
            if not entity:
                return {"entity": None, "relationships": [], "neighbors": []}

            # Use recursive CTE for graph traversal
            rows = conn.execute(
                """WITH RECURSIVE graph_walk AS (
                    -- Base: direct relationships
                    SELECT
                        r.rel_id, r.source_entity_id, r.target_entity_id,
                        r.relation_type, r.confidence, r.created_at,
                        1 AS hop
                    FROM relationships r
                    WHERE r.source_entity_id = ? OR r.target_entity_id = ?

                    UNION ALL

                    -- Recursive: follow neighbors
                    SELECT
                        r2.rel_id, r2.source_entity_id, r2.target_entity_id,
                        r2.relation_type, r2.confidence, r2.created_at,
                        gw.hop + 1
                    FROM relationships r2
                    JOIN graph_walk gw ON (
                        r2.source_entity_id = gw.target_entity_id
                        OR r2.source_entity_id = gw.source_entity_id
                        OR r2.target_entity_id = gw.source_entity_id
                        OR r2.target_entity_id = gw.target_entity_id
                    )
                    WHERE gw.hop < ? AND r2.rel_id != gw.rel_id
                )
                SELECT DISTINCT * FROM graph_walk ORDER BY hop, confidence DESC
                """,
                (entity_id, entity_id, max_hops),
            ).fetchall()

            relationships = [dict(r) for r in rows]
            neighbor_ids = set()
            for r in relationships:
                if r["source_entity_id"] != entity_id:
                    neighbor_ids.add(r["source_entity_id"])
                if r["target_entity_id"] != entity_id:
                    neighbor_ids.add(r["target_entity_id"])

            neighbors = []
            for nid in neighbor_ids:
                n = self.get_entity(nid)
                if n:
                    neighbors.append(n)

            return {
                "entity": entity,
                "relationships": relationships,
                "neighbors": neighbors,
            }
        finally:
            conn.close()

    def find_path(
        self, source_id: str, target_id: str, max_hops: int = 4
    ) -> Optional[List[Dict]]:
        """Find the shortest path between two entities (BFS-style with CTE)."""
        conn = self._conn()
        try:
            rows = conn.execute(
                """WITH RECURSIVE path_search AS (
                    SELECT
                        r.rel_id, r.source_entity_id, r.target_entity_id,
                        r.relation_type, r.confidence,
                        1 AS hop,
                        json_array(r.rel_id) AS path_ids
                    FROM relationships r
                    WHERE r.source_entity_id = ?

                    UNION ALL

                    SELECT
                        r2.rel_id, r2.source_entity_id, r2.target_entity_id,
                        r2.relation_type, r2.confidence,
                        ps.hop + 1,
                        json_insert(ps.path_ids, '$[#]', r2.rel_id)
                    FROM relationships r2
                    JOIN path_search ps ON r2.source_entity_id = ps.target_entity_id
                    WHERE ps.hop < ?
                      AND r2.rel_id NOT IN (SELECT value FROM json_each(ps.path_ids))
                )
                SELECT * FROM path_search
                WHERE target_entity_id = ?
                ORDER BY hop ASC, confidence DESC
                LIMIT 1
                """,
                (source_id, max_hops, target_id),
            ).fetchall()

            if not rows:
                # Try reverse direction
                rows = conn.execute(
                    """WITH RECURSIVE path_search AS (
                        SELECT
                            r.rel_id, r.target_entity_id AS source_entity_id,
                            r.source_entity_id AS target_entity_id,
                            r.relation_type || ' (reverse)' AS relation_type,
                            r.confidence,
                            1 AS hop,
                            json_array(r.rel_id) AS path_ids
                        FROM relationships r
                        WHERE r.target_entity_id = ?

                        UNION ALL

                        SELECT
                            r2.rel_id, r2.target_entity_id,
                            r2.source_entity_id,
                            r2.relation_type || ' (reverse)',
                            r2.confidence,
                            ps.hop + 1,
                            json_insert(ps.path_ids, '$[#]', r2.rel_id)
                        FROM relationships r2
                        JOIN path_search ps ON r2.target_entity_id = ps.target_entity_id
                        WHERE ps.hop < ?
                          AND r2.rel_id NOT IN (SELECT value FROM json_each(ps.path_ids))
                    )
                    SELECT * FROM path_search
                    WHERE target_entity_id = ?
                    ORDER BY hop ASC, confidence DESC
                    LIMIT 1
                    """,
                    (source_id, max_hops, target_id),
                ).fetchall()

            return [dict(r) for r in rows] if rows else None
        finally:
            conn.close()

    # --- Extraction Rules ---

    def upsert_rule(
        self,
        pattern: str,
        entity_type: Optional[str] = None,
        relation_type: Optional[str] = None,
        source_entity_type: Optional[str] = None,
        target_entity_type: Optional[str] = None,
        priority: int = 0,
        confidence: float = 0.8,
        source_llm: Optional[str] = None,
        source_note_id: Optional[str] = None,
        accepted: bool = True,
        rule_id: Optional[str] = None,
    ) -> Dict:
        """Create or update an extraction rule."""
        conn = self._conn()
        try:
            rid = rule_id or str(uuid.uuid4())
            now = self._now()

            conn.execute(
                """INSERT OR REPLACE INTO extraction_rules
                   (rule_id, pattern, entity_type, relation_type,
                    source_entity_type, target_entity_type,
                    priority, confidence, enabled, source_llm, source_note_id,
                    accepted, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)""",
                (rid, pattern, entity_type, relation_type,
                 source_entity_type, target_entity_type,
                 priority, confidence, source_llm, source_note_id,
                 accepted, now, now),
            )
            conn.commit()
            return self.get_rule(rid) or {}
        finally:
            conn.close()

    def get_rule(self, rule_id: str) -> Optional[Dict]:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM extraction_rules WHERE rule_id = ?", (rule_id,)
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    def list_rules(
        self,
        enabled_only: bool = True,
        accepted_only: bool = True,
        rule_type: Optional[str] = None,  # "entity", "relationship", or None for all
    ) -> List[Dict]:
        """List extraction rules."""
        conn = self._conn()
        try:
            sql = "SELECT * FROM extraction_rules WHERE 1=1"
            params: List[Any] = []

            if enabled_only:
                sql += " AND enabled = 1"
            if accepted_only:
                sql += " AND accepted = 1"
            if rule_type == "entity":
                sql += " AND entity_type IS NOT NULL AND relation_type IS NULL"
            elif rule_type == "relationship":
                sql += " AND relation_type IS NOT NULL"

            sql += " ORDER BY priority DESC, usage_count DESC"

            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def toggle_rule(self, rule_id: str, enabled: bool) -> bool:
        """Enable or disable a rule."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE extraction_rules SET enabled = ?, updated_at = ? WHERE rule_id = ?",
                (int(enabled), self._now(), rule_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def accept_rule(self, rule_id: str) -> bool:
        """Mark a proposed rule as accepted."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE extraction_rules SET accepted = 1, enabled = 1, updated_at = ? WHERE rule_id = ?",
                (self._now(), rule_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    def increment_rule_usage(self, rule_id: str):
        """Increment the usage counter for a rule."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE extraction_rules SET usage_count = usage_count + 1 WHERE rule_id = ?",
                (rule_id,),
            )
            conn.commit()
        finally:
            conn.close()

    # --- Extraction Log ---

    def log_extraction(
        self,
        note_id: str,
        stage: str,
        input_summary: str,
        output_summary: str,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
        duration_ms: float = 0,
        success: bool = True,
        details: Optional[Dict] = None,
    ):
        """Log an extraction step for debugging and improvement."""
        conn = self._conn()
        try:
            log_id = str(uuid.uuid4())
            now = self._now()
            conn.execute(
                """INSERT INTO extraction_log
                   (log_id, note_id, stage, input_summary, output_summary,
                    llm_provider, llm_model, duration_ms, success, details, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (log_id, note_id, stage, input_summary, output_summary,
                 llm_provider, llm_model, duration_ms, int(success),
                 json.dumps(details or {}), now),
            )
            conn.commit()
        finally:
            conn.close()

    def get_extraction_log(
        self, note_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict]:
        """Get extraction logs."""
        conn = self._conn()
        try:
            if note_id:
                rows = conn.execute(
                    "SELECT * FROM extraction_log WHERE note_id = ? ORDER BY created_at DESC LIMIT ?",
                    (note_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM extraction_log ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    # --- Stats ---

    def get_stats(self) -> Dict:
        """Get graph statistics."""
        conn = self._conn()
        try:
            return {
                "entity_count": conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0],
                "relationship_count": conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0],
                "rule_count": conn.execute("SELECT COUNT(*) FROM extraction_rules WHERE enabled=1").fetchone()[0],
                "notes_extracted": conn.execute("SELECT COUNT(*) FROM note_extraction_state").fetchone()[0],
                "notes_stale": conn.execute(
                    "SELECT COUNT(*) FROM note_extraction_state WHERE rule_hash != (SELECT group_concat(pattern,'') FROM extraction_rules WHERE enabled=1 AND accepted=1)"
                ).fetchone()[0] if conn.execute("SELECT COUNT(*) FROM note_extraction_state").fetchone()[0] > 0 else 0,
                "entity_types": {
                    row[0]: row[1]
                    for row in conn.execute(
                        "SELECT type, COUNT(*) FROM entities GROUP BY type"
                    ).fetchall()
                },
                "relation_types": {
                    row[0]: row[1]
                    for row in conn.execute(
                        "SELECT relation_type, COUNT(*) FROM relationships GROUP BY relation_type"
                    ).fetchall()
                },
            }
        finally:
            conn.close()

    # --- Extraction State (for smart reruns) ---

    def get_rule_hash(self) -> str:
        """Compute hash of all enabled, accepted extraction rules.

        This is used to detect when rules have changed and notes need re-extraction.
        """
        import hashlib
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT pattern FROM extraction_rules WHERE enabled=1 AND accepted=1 ORDER BY pattern"
            ).fetchall()
            combined = "|".join(r[0] for r in rows)
            return hashlib.sha256(combined.encode()).hexdigest()[:16]
        finally:
            conn.close()

    def upsert_extraction_state(
        self,
        note_id: str,
        rule_hash: str,
        llm_fingerprint: str,
        entity_count: int = 0,
        relationship_count: int = 0,
    ):
        """Record extraction state for a note."""
        conn = self._conn()
        try:
            now = self._now()
            # Get current version and increment
            existing = conn.execute(
                "SELECT extraction_version FROM note_extraction_state WHERE note_id = ?",
                (note_id,),
            ).fetchone()
            version = (existing[0] + 1) if existing else 1

            conn.execute(
                """INSERT OR REPLACE INTO note_extraction_state
                   (note_id, rule_hash, llm_fingerprint, entity_count,
                    relationship_count, last_extracted_at, extraction_version)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (note_id, rule_hash, llm_fingerprint, entity_count,
                 relationship_count, now, version),
            )
            conn.commit()
        finally:
            conn.close()

    def get_stale_notes(
        self, current_rule_hash: str, limit: int = 100
    ) -> List[str]:
        """Find notes whose extraction is stale (rule hash mismatch).

        Also includes notes that have never been extracted.
        """
        conn = self._conn()
        try:
            # Notes with stored state but wrong hash
            rows = conn.execute(
                """SELECT nes.note_id FROM note_extraction_state nes
                   WHERE nes.rule_hash != ?
                   ORDER BY nes.last_extracted_at ASC
                   LIMIT ?""",
                (current_rule_hash, limit),
            ).fetchall()
            stale = [r[0] for r in rows]

            # Notes never extracted
            remaining = limit - len(stale)
            if remaining > 0:
                rows2 = conn.execute(
                    """SELECT n.note_id FROM notes n
                       LEFT JOIN note_extraction_state nes ON n.note_id = nes.note_id
                       WHERE nes.note_id IS NULL
                       ORDER BY n.created_at ASC
                       LIMIT ?""",
                    (remaining,),
                ).fetchall()
                stale.extend(r[0] for r in rows2)

            return stale
        finally:
            conn.close()

    def get_notes_matching_rule(
        self, rule_pattern: str, limit: int = 500
    ) -> List[str]:
        """Find notes whose text matches a regex pattern.

        Uses SQLite LIKE for prefix/suffix matching, falls back to
        fetching and regex-testing in Python for complex patterns.
        """
        conn = self._conn()
        try:
            # Try simple LIKE pre-filter first (instant)
            # Extract a simple substring from the pattern for SQL LIKE
            import re
            simple = re.sub(r'[\\(\\)\[\]\{\}\^\$\.\*\+\?\|]', '', rule_pattern)
            simple = simple.strip()

            if simple and len(simple) >= 3:
                rows = conn.execute(
                    "SELECT note_id, raw_text FROM notes WHERE raw_text LIKE ? LIMIT ?",
                    (f"%{simple}%", limit),
                ).fetchall()
            else:
                # Complex pattern, fetch all notes
                rows = conn.execute(
                    "SELECT note_id, raw_text FROM notes LIMIT ?",
                    (limit,),
                ).fetchall()

            # Regex filter in Python
            try:
                compiled = re.compile(rule_pattern, re.IGNORECASE)
                return [r[0] for r in rows if compiled.search(r[1] or "")]
            except re.error:
                return []
        finally:
            conn.close()

    def get_extraction_state(self, note_id: str) -> Optional[Dict]:
        """Get extraction state for a note."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM note_extraction_state WHERE note_id = ?",
                (note_id,),
            ).fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            conn.close()

    # --- Helpers ---

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict:
        d = dict(row)
        # Parse JSON fields
        for field in ("aliases", "metadata", "payload", "structured_payload", "details", "raw_payload"):
            if field in d and isinstance(d[field], str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
