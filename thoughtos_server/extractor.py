"""Entity & relationship extraction pipeline.

Pipeline stages:
  1. Rule Engine — regex patterns from DB, deterministic, free
  2. LLM Extraction — uses configured LLM to find nuanced entities
  3. Deduplication — fuzzy matching + LLM to merge with existing graph
  4. Rule Generation — optional: LLM observes patterns, proposes new regex rules

Any LLM provider can be used at any stage. Rules from Stage 4 feed back into Stage 1.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .config import ExtractionConfig
from .graph_store import GraphStore
from .llm import call_llm_json

# --- Constants ---

VALID_ENTITY_TYPES = {
    "person", "project", "tool", "concept", "document",
    "event", "org", "location", "metric", "other",
}

VALID_RELATION_TYPES = {
    "discussed", "uses", "depends_on", "part_of", "compared_with",
    "created", "met_with", "works_on", "reviewed", "owns",
    "references", "integrates_with", "alternative_to", "produces",
    "related_to",
}


# --- Stage 1: Rule Engine ---


def _compile_rules(rules: List[Dict]) -> List[Dict]:
    """Compile regex patterns from rule dicts."""
    compiled = []
    for rule in rules:
        try:
            compiled.append({
                **rule,
                "_regex": re.compile(rule["pattern"], re.IGNORECASE),
            })
        except re.error:
            continue
    return compiled


def _apply_entity_rules(
    text: str, compiled_rules: List[Dict], user_id: str
) -> List[Dict]:
    """Apply entity extraction rules to text."""
    entities = []
    seen_names = set()

    for rule in compiled_rules:
        if rule.get("relation_type"):
            continue  # entity rules only
        for match in rule["_regex"].finditer(text):
            name = match.group(1) if match.groups() else match.group(0)
            name = name.strip()
            if not name or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            entities.append({
                "name": name,
                "type": rule.get("entity_type") or "other",
                "confidence": rule.get("confidence", 0.8),
                "source": "rule",
                "rule_id": rule.get("rule_id"),
            })

    return entities


def _apply_relationship_rules(
    text: str, entity_names: Set[str], compiled_rules: List[Dict]
) -> List[Dict]:
    """Apply relationship extraction rules, matching against found entities."""
    relationships = []
    seen_pairs = set()

    for rule in compiled_rules:
        if not rule.get("relation_type"):
            continue  # relationship rules only

        # Look for mentions of entities within the pattern match context
        for match in rule["_regex"].finditer(text):
            matched_text = match.group(0) if not match.groups() else " ".join(
                g for g in match.groups() if g
            )

            # Find which known entities appear in this match
            entities_in_match = [
                name for name in entity_names
                if name.lower() in matched_text.lower()
            ]

            if len(entities_in_match) >= 2:
                source, target = entities_in_match[0], entities_in_match[1]
                pair = (source.lower(), target.lower())
                if pair not in seen_pairs:
                    seen_pairs.add(pair)
                    relationships.append({
                        "source_name": source,
                        "target_name": target,
                        "relation_type": rule["relation_type"],
                        "confidence": rule.get("confidence", 0.7),
                        "source": "rule",
                        "rule_id": rule.get("rule_id"),
                    })

    return relationships


# --- Stage 1: Heuristic fallback (no rules needed) ---


# Built-in patterns that catch obvious entities without needing stored rules
BUILTIN_ENTITY_PATTERNS = [
    # @project references (highest priority)
    (r"@(\w[\w.-]*)", "project"),
    # People: "with Name Surname" after discussion/meeting verbs
    (r"(?:called|met|spoke|talked|discussed|chat(?:ted)?|synced|paired|hopped)\s+(?:with|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", "person"),
    # People: "Name and I/we" patterns
    (r"([A-Z][a-z]+)\s+and\s+(?:I|we|the team)\s+(?:discussed|talked|met|worked|decided)", "person"),
    # People: "told Name", "asked Name"
    (r"(?:told|asked|pinged|messaged|emailed|texted)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", "person"),
    # File paths
    (r"([\w/.-]+\.(?:py|js|ts|rs|go|java|rb|sh|yaml|yml|json|toml|md))", "document"),
    # URLs / repos
    (r"(?:github\.com/[\w.-]+/[\w.-]+)", "project"),
    # Tools/libraries: "using X", "via X", "through X"
    (r"(?:using|via|through)\s+([A-Z][a-zA-Z0-9]{2,20}(?:\s+[A-Z][a-zA-Z0-9]{2,20})?)\b", "tool"),
    # Organizations: @CamelCase
    (r"@([A-Z][a-z]+(?:[A-Z][a-z]+)+)", "org"),
    # Capitalized concepts: "X pipeline", "X model", "X framework"
    (r"([A-Z][a-zA-Z0-9]{2,30})\s+(?:pipeline|model|framework|system|algorithm|method|approach)", "concept"),
]

BUILTIN_RELATION_PATTERNS = [
    (r"(\w+)\s+(?:vs|versus|compared\s+(?:to|with))\s+(\w+)", "compared_with"),
    (r"(\w+)\s+(?:using|via|through|with|powered by)\s+(\w+)", "uses"),
    (r"(\w+)\s+(?:depends on|requires|needs)\s+(\w+)", "depends_on"),
    (r"(\w+)\s+(?:is part of|belongs to|in)\s+(\w+)", "part_of"),
]


def _apply_builtins(text: str) -> Tuple[List[Dict], List[Dict]]:
    """Apply built-in heuristic patterns."""
    entities = []
    relationships = []
    seen_names = set()

    for pattern, etype in BUILTIN_ENTITY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            name = match.group(1).strip() if match.groups() else match.group(0).strip()
            if not name or len(name) < 2 or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            entities.append({
                "name": name,
                "type": etype,
                "confidence": 0.6,
                "source": "builtin",
            })

    entity_names = {e["name"] for e in entities}

    for pattern, rtype in BUILTIN_RELATION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            g1 = match.group(1).strip() if match.groups() else ""
            g2 = match.group(2).strip() if len(match.groups()) >= 2 else ""
            if g1.lower() in entity_names and g2.lower() in entity_names and g1 != g2:
                relationships.append({
                    "source_name": g1,
                    "target_name": g2,
                    "relation_type": rtype,
                    "confidence": 0.6,
                    "source": "builtin",
                })

    return entities, relationships


# --- Stage 2: LLM Extraction ---


EXTRACTION_PROMPT = """You are an entity extraction engine for a personal knowledge graph.
Extract entities and relationships from the following note.

Entity types: person, project, tool, concept, document, event, org, location, metric, other
Relationship types: discussed, uses, depends_on, part_of, compared_with, created, met_with,
  works_on, reviewed, owns, references, integrates_with, alternative_to, produces, related_to

Existing entities (avoid duplicates, use exact names):
{existing_entities}

Note:
{text}

Return exactly this JSON shape:
{{
  "entities": [
    {{
      "name": "Entity Name",
      "type": "one of the valid entity types",
      "aliases": ["alternative names"],
      "confidence": 0.9
    }}
  ],
  "relationships": [
    {{
      "source_name": "Entity A",
      "target_name": "Entity B",
      "relation_type": "one of the valid relationship types",
      "confidence": 0.85
    }}
  ]
}}

Rules:
- Only extract entities that are clearly mentioned in the text.
- Do NOT create entities for generic concepts like "the project" or "the team".
- For people, use their actual name (e.g., "Rohan" not "the developer").
- For tools/libraries, use the actual name (e.g., "PyTorch" not "the framework").
- Relationships should only connect entities found in this note.
- If existing entities have the same meaning, reuse their exact name.
- Set confidence lower (0.6-0.7) for inferred relationships, higher (0.8-1.0) for explicit ones."""


def _llm_extract(
    text: str,
    existing_entities: List[Dict],
    config: ExtractionConfig,
) -> Tuple[List[Dict], List[Dict]]:
    """Use LLM to extract entities and relationships."""
    existing_str = "\n".join(
        f"- {e['name']} ({e.get('type', 'unknown')})"
        for e in existing_entities[:30]  # limit context window
    ) or "(none)"

    prompt = EXTRACTION_PROMPT.format(
        existing_entities=existing_str,
        text=text[:4000],  # truncate long notes
    )

    result = call_llm_json(prompt, config.extraction_llm)
    if not result:
        return [], []

    entities = result.get("entities", [])
    relationships = result.get("relationships", [])

    # Validate and filter
    validated_entities = []
    for e in entities:
        name = (e.get("name") or "").strip()
        etype = e.get("type", "other")
        if not name or len(name) < 2:
            continue
        if etype not in VALID_ENTITY_TYPES:
            etype = "other"
        validated_entities.append({
            "name": name,
            "type": etype,
            "aliases": e.get("aliases", []),
            "confidence": float(e.get("confidence", 0.7)),
            "source": "llm",
        })

    validated_rels = []
    for r in relationships:
        src = (r.get("source_name") or "").strip()
        tgt = (r.get("target_name") or "").strip()
        rtype = r.get("relation_type", "related_to")
        if not src or not tgt or src == tgt:
            continue
        if rtype not in VALID_RELATION_TYPES:
            rtype = "related_to"
        validated_rels.append({
            "source_name": src,
            "target_name": tgt,
            "relation_type": rtype,
            "confidence": float(r.get("confidence", 0.7)),
            "source": "llm",
        })

    return validated_entities, validated_rels


# --- Stage 3: Deduplication ---


def _fuzzy_match(name: str, candidates: List[Dict], threshold: float = 0.85) -> Optional[Dict]:
    """Find the best fuzzy match for a name among candidates."""
    name_lower = name.lower().strip()

    # Exact match
    for c in candidates:
        if c["name"].lower() == name_lower:
            return c
        aliases = c.get("aliases") or []
        if isinstance(aliases, str):
            try:
                aliases = __import__("json").loads(aliases)
            except Exception:
                aliases = []
        for alias in aliases:
            if alias.lower() == name_lower:
                return c

    # Simple trigram similarity
    best_score = 0
    best_match = None
    for c in candidates:
        score = _trigram_similarity(name_lower, c["name"].lower())
        if score > best_score:
            best_score = score
            best_match = c

    if best_score >= threshold:
        return best_match
    return None


def _trigram_similarity(a: str, b: str) -> float:
    """Simple trigram-based string similarity."""
    if a == b:
        return 1.0

    def trigrams(s: str) -> Set[str]:
        s = "  " + s + " "
        return {s[i:i + 3] for i in range(len(s) - 2)}

    ta = trigrams(a)
    tb = trigrams(b)
    if not ta or not tb:
        return 0.0

    intersection = ta & tb
    return len(intersection) / max(len(ta), len(tb))


# --- Stage 4: Rule Generation ---


RULE_GEN_PROMPT = """You are analyzing entity extraction results to improve a rule engine.
Look at the note text and the extracted entities/relationships.
Propose regex rules that could automatically extract similar entities in the future.

Rules should:
- Be specific enough to avoid false positives
- Be general enough to catch variations
- Use capture groups () to extract entity names
- Target the entity types: person, project, tool, concept, document, event, org

Note text:
{text}

Extracted entities (by LLM):
{entities}

Propose up to 3 regex rules as JSON:
{{
  "rules": [
    {{
      "pattern": "regex pattern with capture groups",
      "entity_type": "type",
      "description": "what this catches",
      "confidence": 0.8
    }}
  ]
}}

Do NOT propose rules for things already caught by these existing rules:
{existing_rules}
"""


def _generate_rules(
    text: str,
    new_entities: List[Dict],
    existing_rules: List[Dict],
    config: ExtractionConfig,
) -> List[Dict]:
    """Ask LLM to generate new extraction rules."""
    if not config.enable_rule_generation or not new_entities:
        return []

    entity_str = "\n".join(
        f"- {e['name']} ({e['type']}) confidence={e.get('confidence', '?')}"
        for e in new_entities[:10]
    )
    rules_str = "\n".join(
        f"- pattern: {r['pattern']} → {r.get('entity_type', '?')}"
        for r in existing_rules[:20]
    ) or "(none)"

    prompt = RULE_GEN_PROMPT.format(
        text=text[:3000],
        entities=entity_str,
        existing_rules=rules_str,
    )

    result = call_llm_json(prompt, config.rule_gen_llm)
    if not result:
        return []

    proposed = []
    for r in result.get("rules", []):
        pattern = r.get("pattern", "")
        if not pattern:
            continue
        # Validate regex
        try:
            re.compile(pattern)
        except re.error:
            continue
        proposed.append({
            "pattern": pattern,
            "entity_type": r.get("entity_type"),
            "confidence": float(r.get("confidence", 0.7)),
            "description": r.get("description", ""),
        })

    return proposed


# --- Main Pipeline ---


class ExtractionPipeline:
    """Orchestrates the full extraction pipeline."""

    def __init__(self, graph: GraphStore, config: ExtractionConfig):
        self.graph = graph
        self.config = config

    def extract(
        self,
        text: str,
        note_id: str,
        user_id: str,
        existing_entities: Optional[List[Dict]] = None,
    ) -> Dict:
        """Run the full extraction pipeline on note text.

        Returns dict with {entities, relationships, rules_proposed, logs}.
        """
        t0 = time.time()
        text = (text or "").strip()
        if not text:
            return {"entities": [], "relationships": [], "rules_proposed": [], "logs": []}

        all_entities: List[Dict] = []
        all_relationships: List[Dict] = []
        logs: List[Dict] = []

        # Get existing entities for dedup context
        if existing_entities is None:
            existing_entities = self.graph.find_entities(user_id=user_id, limit=100)

        # --- Stage 1: Rule Engine ---
        if self.config.enable_rule_engine:
            t1 = time.time()
            rules = self.graph.list_rules(enabled_only=True, accepted_only=True)

            # Entity rules
            entity_rules = _compile_rules([r for r in rules if not r.get("relation_type")])
            rule_entities = _apply_entity_rules(text, entity_rules, user_id)

            # Built-in heuristics (always runs, no cost)
            builtin_entities, builtin_relationships = _apply_builtins(text)

            # Merge: rules take precedence over builtins
            rule_names = {e["name"].lower() for e in rule_entities}
            for be in builtin_entities:
                if be["name"].lower() not in rule_names:
                    rule_entities.append(be)

            all_entities.extend(rule_entities)

            # Relationship rules
            entity_names = {e["name"] for e in all_entities}
            rel_rules = _compile_rules([r for r in rules if r.get("relation_type")])
            rule_relationships = _apply_relationship_rules(text, entity_names, rel_rules)
            all_relationships.extend(rule_relationships)
            all_relationships.extend(builtin_relationships)

            # Track rule usage
            used_rule_ids = set()
            for e in rule_entities:
                if e.get("rule_id"):
                    used_rule_ids.add(e["rule_id"])
            for r in rule_relationships:
                if r.get("rule_id"):
                    used_rule_ids.add(r["rule_id"])
            for rid in used_rule_ids:
                self.graph.increment_rule_usage(rid)

            duration = (time.time() - t1) * 1000
            logs.append({
                "stage": "rule_engine",
                "entities_found": len(rule_entities) + len(builtin_entities),
                "relationships_found": len(rule_relationships) + len(builtin_relationships),
                "duration_ms": duration,
            })

        # --- Stage 2: LLM Extraction ---
        if self.config.enable_llm_extraction:
            t2 = time.time()
            try:
                llm_entities, llm_relationships = _llm_extract(
                    text, existing_entities, self.config
                )

                # Merge LLM results (LLM takes precedence for same names)
                existing_names = {e["name"].lower() for e in all_entities}
                for e in llm_entities:
                    if e["name"].lower() not in existing_names:
                        all_entities.append(e)

                existing_rel_pairs = {
                    (r["source_name"].lower(), r["target_name"].lower())
                    for r in all_relationships
                }
                for r in llm_relationships:
                    pair = (r["source_name"].lower(), r["target_name"].lower())
                    if pair not in existing_rel_pairs:
                        all_relationships.append(r)

                duration = (time.time() - t2) * 1000
                logs.append({
                    "stage": "llm_extraction",
                    "entities_found": len(llm_entities),
                    "relationships_found": len(llm_relationships),
                    "provider": self.config.extraction_llm.provider,
                    "model": self.config.extraction_llm.model,
                    "duration_ms": duration,
                })
            except Exception as e:
                logs.append({
                    "stage": "llm_extraction",
                    "error": str(e),
                    "duration_ms": (time.time() - t2) * 1000,
                })

        # --- Stage 3: Deduplication & Storage ---
        t3 = time.time()
        stored_entities = []
        stored_relationships = []

        # Deduplicate and store entities
        for e in all_entities:
            match = _fuzzy_match(e["name"], existing_entities, self.config.fuzzy_threshold)
            if match:
                # Update existing entity
                entity = self.graph.upsert_entity(
                    name=match["name"],
                    entity_type=e["type"],
                    user_id=user_id,
                    source_note_id=note_id,
                    aliases=(match.get("aliases") or []) + (e.get("aliases") or []),
                    confidence=max(e.get("confidence", 0.5), match.get("confidence", 0.5)),
                    entity_id=match["entity_id"],
                )
            else:
                entity = self.graph.upsert_entity(
                    name=e["name"],
                    entity_type=e["type"],
                    user_id=user_id,
                    source_note_id=note_id,
                    aliases=e.get("aliases", []),
                    confidence=e.get("confidence", 0.7),
                )
            stored_entities.append(entity)
            # Add to existing for subsequent dedup
            if entity:
                existing_entities.append(entity)

        # Build name → ID map
        name_to_id = {}
        for e in existing_entities:
            eid = e.get("entity_id", "")
            ename = (e.get("name") or "").lower()
            if eid and ename:
                name_to_id[ename] = eid
            for alias in (e.get("aliases") or []):
                if isinstance(alias, str):
                    name_to_id[alias.lower()] = eid

        # Store relationships
        for r in all_relationships:
            src_id = name_to_id.get(r["source_name"].lower())
            tgt_id = name_to_id.get(r["target_name"].lower())
            if not src_id or not tgt_id:
                continue
            rel = self.graph.create_relationship(
                source_entity_id=src_id,
                target_entity_id=tgt_id,
                relation_type=r["relation_type"],
                user_id=user_id,
                source_note_id=note_id,
                confidence=r.get("confidence", 0.7),
            )
            stored_relationships.append(rel)

        duration = (time.time() - t3) * 1000
        logs.append({
            "stage": "dedup_storage",
            "entities_stored": len(stored_entities),
            "relationships_stored": len(stored_relationships),
            "duration_ms": duration,
        })

        # --- Stage 4: Rule Generation ---
        rules_proposed = []
        if self.config.enable_rule_generation and all_entities:
            t4 = time.time()
            try:
                existing_rules = self.graph.list_rules(enabled_only=False, accepted_only=True)
                proposed = _generate_rules(text, all_entities, existing_rules, self.config)
                for p in proposed:
                    rule = self.graph.upsert_rule(
                        pattern=p["pattern"],
                        entity_type=p.get("entity_type"),
                        confidence=p.get("confidence", 0.7),
                        source_llm=f"{self.config.rule_gen_llm.provider}:{self.config.rule_gen_llm.model}",
                        source_note_id=note_id,
                        accepted=False,  # needs review
                    )
                    rules_proposed.append(rule)
                duration = (time.time() - t4) * 1000
                logs.append({
                    "stage": "rule_generation",
                    "rules_proposed": len(rules_proposed),
                    "provider": self.config.rule_gen_llm.provider,
                    "model": self.config.rule_gen_llm.model,
                    "duration_ms": duration,
                })
            except Exception as e:
                logs.append({
                    "stage": "rule_generation",
                    "error": str(e),
                })

        total_ms = (time.time() - t0) * 1000

        # Record extraction state for smart reruns
        rule_hash = self.graph.get_rule_hash()
        llm_fp = f"{self.config.extraction_llm.provider}:{self.config.extraction_llm.model}"
        self.graph.upsert_extraction_state(
            note_id=note_id,
            rule_hash=rule_hash,
            llm_fingerprint=llm_fp,
            entity_count=len(stored_entities),
            relationship_count=len(stored_relationships),
        )

        # Log extraction
        self.graph.log_extraction(
            note_id=note_id,
            stage="full_pipeline",
            input_summary=text[:200],
            output_summary=f"{len(stored_entities)} entities, {len(stored_relationships)} relationships, {len(rules_proposed)} rules",
            llm_provider=self.config.extraction_llm.provider,
            llm_model=self.config.extraction_llm.model,
            duration_ms=total_ms,
            details={"logs": logs, "rule_hash": rule_hash},
        )

        return {
            "entities": stored_entities,
            "relationships": stored_relationships,
            "rules_proposed": rules_proposed,
            "logs": logs,
            "total_duration_ms": total_ms,
            "rule_hash": rule_hash,
        }

    def improve_extraction(
        self,
        note_id: str,
        note_text: str,
        user_id: str,
        llm_provider: Optional[str] = None,
        llm_model: Optional[str] = None,
    ) -> Dict:
        """Re-extract a note with a different/improved LLM, comparing results.

        Useful for: "use a smarter model to review and improve extraction."
        """
        from copy import deepcopy

        # Use a different LLM if specified
        improved_config = deepcopy(self.config)
        if llm_provider:
            improved_config.extraction_llm.provider = llm_provider
        if llm_model:
            improved_config.extraction_llm.model = llm_model
        improved_config.enable_rule_generation = True

        # Get previous extraction log
        prev_logs = self.graph.get_extraction_log(note_id=note_id, limit=1)
        prev_summary = prev_logs[0]["output_summary"] if prev_logs else "none"

        # Run extraction with improved config
        result = ExtractionPipeline(self.graph, improved_config).extract(
            text=note_text,
            note_id=note_id,
            user_id=user_id,
        )

        result["previous_extraction"] = prev_summary
        result["improved_with"] = f"{improved_config.extraction_llm.provider}:{improved_config.extraction_llm.model}"

        return result

    def rerun_all(
        self,
        user_id: str,
        note_texts: List[Tuple[str, str]],  # [(note_id, text), ...]
    ) -> Dict:
        """[DEPRECATED] Re-extract all notes. Use smart_rerun() instead."""
        return self.smart_rerun(user_id=user_id, force_all=True)

    # --- Smart Rerun (scalable) ---

    def smart_rerun(
        self,
        user_id: str,
        force_all: bool = False,
        max_notes: int = 50,
        llm_enabled: Optional[bool] = None,
        background: bool = False,
    ) -> Dict:
        """Intelligently re-extract only notes that need it.

        Strategy (by default):
        1. Compute current rule hash
        2. Find notes where stored hash != current hash (stale)
        3. Also include never-extracted notes
        4. Process only those notes, in creation order
        5. Skip notes that are already up-to-date

        With force_all=True: reprocess all notes (original behavior).
        With llm_enabled=False: rule-engine only, zero LLM cost, instant.

        Args:
            user_id: User ID
            force_all: If True, re-extract ALL notes (ignore hashes)
            max_notes: Maximum notes to process in one batch
            llm_enabled: Override LLM extraction (None = use config default)
            background: If True, don't block — just return stats about what would run

        Returns:
            Dict with stats, processed count, skipped count, etc.
        """
        current_hash = self.graph.get_rule_hash()
        llm_fp = f"{self.config.extraction_llm.provider}:{self.config.extraction_llm.model}"

        # Find notes to process
        if force_all:
            # Get all notes
            import sqlite3
            conn = sqlite3.connect(self.graph.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT note_id, raw_text FROM notes WHERE user_id = ? ORDER BY created_at LIMIT ?",
                (user_id, max_notes),
            ).fetchall()
            conn.close()
            to_process = [(r["note_id"], r["raw_text"]) for r in rows]
            strategy = "force_all"
        else:
            stale_ids = self.graph.get_stale_notes(current_hash, limit=max_notes)
            if not stale_ids:
                return {
                    "strategy": "up_to_date",
                    "rule_hash": current_hash,
                    "processed": 0,
                    "skipped": 0,
                    "message": "All notes are up-to-date with current rules.",
                }

            # Fetch text for stale notes
            import sqlite3
            conn = sqlite3.connect(self.graph.db_path)
            conn.row_factory = sqlite3.Row
            placeholders = ",".join("?" for _ in stale_ids)
            rows = conn.execute(
                f"SELECT note_id, raw_text FROM notes WHERE note_id IN ({placeholders})",
                stale_ids,
            ).fetchall()
            conn.close()
            to_process = [(r["note_id"], r["raw_text"]) for r in rows]
            strategy = "stale_only"

        if not to_process:
            return {
                "strategy": strategy,
                "rule_hash": current_hash,
                "processed": 0,
                "skipped": 0,
                "message": "No notes to process.",
            }

        # Background mode: just report what would happen
        if background:
            # Count total stale
            total_stale = len(self.graph.get_stale_notes(current_hash, limit=10000))
            return {
                "strategy": strategy,
                "rule_hash": current_hash,
                "would_process": len(to_process),
                "total_stale": total_stale,
                "remaining_after_batch": max(0, total_stale - len(to_process)),
                "message": f"Would process {len(to_process)} notes ({total_stale} total stale).",
            }

        # Process notes
        results = []
        total_entities = 0
        total_relationships = 0
        total_rules = 0
        skipped = 0

        # If not forcing, double-check each note's hash (avoid races)
        use_llm = llm_enabled if llm_enabled is not None else self.config.enable_llm_extraction

        for note_id, text in to_process:
            if not force_all:
                state = self.graph.get_extraction_state(note_id)
                if state and state.get("rule_hash") == current_hash:
                    skipped += 1
                    continue

            # For stale notes with LLM disabled: just reapply rules (free)
            if use_llm:
                result = self.extract(
                    text=text, note_id=note_id, user_id=user_id,
                )
            else:
                # Rules-only mode: skip LLM stages
                saved_llm = self.config.enable_llm_extraction
                saved_rule_gen = self.config.enable_rule_generation
                self.config.enable_llm_extraction = False
                self.config.enable_rule_generation = False
                try:
                    result = self.extract(
                        text=text, note_id=note_id, user_id=user_id,
                    )
                finally:
                    self.config.enable_llm_extraction = saved_llm
                    self.config.enable_rule_generation = saved_rule_gen

            results.append({"note_id": note_id, "entities": len(result["entities"]),
                          "relationships": len(result["relationships"])})
            total_entities += len(result["entities"])
            total_relationships += len(result["relationships"])
            total_rules += len(result.get("rules_proposed", []))

        return {
            "strategy": strategy,
            "rule_hash": current_hash,
            "llm_fingerprint": llm_fp,
            "processed": len(to_process),
            "skipped": skipped,
            "total_entities": total_entities,
            "total_relationships": total_relationships,
            "rules_proposed": total_rules,
            "results": results,
        }

    def assess_rule_impact(
        self, rule_id: str, user_id: str
    ) -> Dict:
        """Before accepting a rule, check how many notes it would affect.

        Runs the rule's regex against ALL notes (SQL LIKE pre-filter →
        Python regex) to estimate impact before committing to extraction.
        """
        rule = self.graph.get_rule(rule_id)
        if not rule:
            return {"error": "Rule not found"}

        pattern = rule.get("pattern", "")
        if not pattern:
            return {"error": "Rule has no pattern"}

        affected = self.graph.get_notes_matching_rule(pattern)

        # Also estimate: how many would actually produce NEW entities?
        # For each affected note, check if the pattern matches something
        # not already in the graph
        new_entity_estimate = 0
        existing_names = {
            e["name"].lower()
            for e in self.graph.find_entities(user_id=user_id, limit=1000)
        }

        import re
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return {
                "rule": rule,
                "affected_notes": len(affected),
                "estimated_new_entities": 0,
                "warning": "Invalid regex pattern",
            }

        import sqlite3
        conn = sqlite3.connect(self.graph.db_path)
        conn.row_factory = sqlite3.Row
        for note_id in affected[:50]:  # Sample first 50
            row = conn.execute(
                "SELECT raw_text FROM notes WHERE note_id = ?", (note_id,)
            ).fetchone()
            if row:
                for match in compiled.finditer(row["raw_text"] or ""):
                    name = match.group(1) if match.groups() else match.group(0)
                    if name.strip().lower() not in existing_names:
                        new_entity_estimate += 1
                        break
        conn.close()

        return {
            "rule": rule,
            "affected_notes": len(affected),
            "estimated_new_entities": new_entity_estimate,
            "sample_affected": affected[:10],
            "recommendation": (
                "high_impact" if len(affected) > 20 and new_entity_estimate > 5
                else "medium_impact" if len(affected) > 5
                else "low_impact"
            ),
        }
