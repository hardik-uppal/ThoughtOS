"""ThoughtOS note intake and task extraction.

This module is intentionally backend-owned. Terminal/Pi/OpenClaw/Obsidian
clients should call into this module/API instead of duplicating note logic.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from logic.llm_engine import ask_gemini_json
except Exception:
    def ask_gemini_json(_prompt: str) -> str:
        return "Error: Gemini unavailable"

from logic.sql_engine import create_note, create_task


ACTION_PATTERNS = [
    r"\bneed to\b",
    r"\bneeds to\b",
    r"\bhave to\b",
    r"\bhas to\b",
    r"\bshould\b",
    r"\bfollow up\b",
    r"\bsend\b",
    r"\bfix\b",
    r"\bcreate\b",
    r"\bbuild\b",
    r"\bupdate\b",
    r"\bcall\b",
    r"\bemail\b",
    r"\btodo\b",
    r"\baction item\b",
]


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^[-*•]\s*", "", line)
    line = re.sub(r"^\[[ xX]\]\s*", "", line)
    line = re.sub(r"^(todo|task|action item)s?\s*[:\-]\s*", "", line, flags=re.I)
    return line.strip()


def _infer_note_type(text: str, requested: Optional[str] = None) -> str:
    if requested and requested != "auto":
        return requested
    lower = text.lower()
    if any(word in lower for word in ["call with", "meeting", "standup", "sync", "1:1", "review"]):
        return "meeting_note"
    if any(word in lower for word in ["todo", "task dump", "things to do"]):
        return "task_dump"
    if any(word in lower for word in ["decided", "decision", "we agreed"]):
        return "decision_note"
    return "quick_note"


def _fallback_title(text: str, note_type: str) -> str:
    first = next((line.strip(" #-\t") for line in text.splitlines() if line.strip()), "Untitled note")
    if len(first) > 80:
        first = first[:77].rstrip() + "..."
    if note_type == "meeting_note" and not first.lower().startswith(("call", "meeting")):
        match = re.search(r"(?:call|meeting|sync|1:1)\s+with\s+([^\n,.]+)", text, re.I)
        if match:
            return f"Call with {match.group(1).strip()}"
    return first or "Untitled note"


def _fallback_people(text: str) -> List[str]:
    people: List[str] = []
    for match in re.finditer(r"(?:call|meeting|sync|1:1)\s+with\s+([^\n,.]+)", text, re.I):
        for part in re.split(r"\s+and\s+|,", match.group(1)):
            name = part.strip()
            if name and len(name) <= 60:
                people.append(name)
    # Preserve order, dedupe case-insensitively.
    seen = set()
    out = []
    for p in people:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _fallback_tasks(text: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for raw in re.split(r"[\n;]+|(?<=[.!?])\s+(?=[A-Z0-9])", text):
        line = _clean_line(raw)
        if not line:
            continue
        lower = line.lower()
        looks_like_checkbox = bool(re.match(r"^\s*[-*•]?\s*\[[ xX]\]", raw))
        if looks_like_checkbox or any(re.search(pattern, lower) for pattern in ACTION_PATTERNS):
            if lower.startswith(("call with", "meeting with")) and len(line.split()) <= 6:
                continue
            
            # Extract inline metadata
            project_match = re.search(r"@(\w+)", line)
            project = project_match.group(1) if project_match else None
            
            priority_match = re.search(r"!(high|medium|low)", lower)
            priority = priority_match.group(1) if priority_match else "medium"
            
            due_match = re.search(r"due:([\w-]+)", lower)
            due_date = due_match.group(1) if due_match else ("tomorrow" if "tomorrow" in lower else "today" if "today" in lower else None)
            
            # Clean title
            title = re.sub(r"^(i|we|he|she|they)\s+(need|needs|have|has)\s+to\s+", "", line, flags=re.I)
            title = re.sub(r"^(need|needs|have|has)\s+to\s+", "", title, flags=re.I)
            title = re.sub(r"^should\s+", "", title, flags=re.I)
            title = re.sub(r"@\w+|!(high|medium|low)|due:[\w-]+", "", title, flags=re.I)
            title = title[:160].strip(" .")
            
            if title:
                tasks.append({
                    "title": title[0].upper() + title[1:],
                    "owner": "me" if lower.startswith("i ") or " me " in lower else None,
                    "due_date": due_date,
                    "priority": priority,
                    "project": project,
                    "status": "open",
                })
    
    seen = set()
    deduped = []
    for task in tasks:
        key = task["title"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(task)
    return deduped


def _fallback_standardize(text: str, note_type: str) -> Dict[str, Any]:
    lines = [_clean_line(line) for line in text.splitlines() if _clean_line(line)]
    title = _fallback_title(text, note_type)
    tasks = _fallback_tasks(text)
    people = _fallback_people(text)
    summary = " ".join(lines[:3])
    if len(summary) > 280:
        summary = summary[:277].rstrip() + "..."
    return {
        "title": title,
        "note_type": note_type,
        "summary": summary or title,
        "people": people,
        "projects": [],
        "tags": [note_type.replace("_note", "").replace("_", "-")],
        "discussion_points": lines,
        "decisions": [],
        "action_items": tasks,
        "open_questions": [line for line in lines if line.endswith("?")],
        "raw_text": text,
    }


def _try_llm_standardize(text: str, note_type: str) -> Optional[Dict[str, Any]]:
    prompt = f"""
You are ThoughtOS note intake. Convert rough notes into structured JSON.
Preserve the user's meaning. Do not invent facts. Extract concrete tasks only.

Requested note_type: {note_type}

Return exactly this JSON shape:
{{
  "title": "short human title",
  "note_type": "quick_note|meeting_note|call_note|daily_note|project_note|decision_note|task_dump|research_note|journal_entry",
  "summary": "2-4 sentence summary",
  "people": ["names"],
  "projects": ["project names"],
  "tags": ["lowercase-tags"],
  "discussion_points": ["bullets"],
  "decisions": ["decisions"],
  "action_items": [
    {{"title":"task", "owner":"me|null|name", "due_date":"YYYY-MM-DD|null|natural language", "priority":"low|medium|high", "status":"open"}}
  ],
  "open_questions": ["questions"],
  "raw_text": "original raw text"
}}

Rough notes:
{text}
""".strip()
    try:
        raw = ask_gemini_json(prompt)
        if not raw or raw.startswith("Error:"):
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        data["raw_text"] = text
        data["note_type"] = data.get("note_type") or note_type
        data["title"] = data.get("title") or _fallback_title(text, note_type)
        data["summary"] = data.get("summary") or data["title"]
        data["action_items"] = data.get("action_items") or []
        return data
    except Exception as exc:
        print(f"Note intake LLM fallback used: {exc}")
        return None


def standardize_note(text: str, note_type: Optional[str] = "auto") -> Dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("Note text is required")
    inferred = _infer_note_type(text, note_type)
    return _try_llm_standardize(text, inferred) or _fallback_standardize(text, inferred)


def intake_note(user_id: str, text: str, source: str = "api", note_type: Optional[str] = "auto", context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    structured = standardize_note(text, note_type)
    now = _now()
    note_id = str(uuid.uuid4())
    structured.setdefault("context", context or {})

    note = create_note(
        note_id=note_id,
        user_id=user_id,
        title=structured["title"],
        note_type=structured.get("note_type") or "quick_note",
        summary=structured.get("summary") or structured["title"],
        raw_text=text,
        structured_payload=structured,
        source=source,
        created_at=now,
    )

    created_tasks = []
    for item in structured.get("action_items") or []:
        if isinstance(item, str):
            task_title = item
            payload = {"title": item, "status": "open"}
        elif isinstance(item, dict):
            task_title = item.get("title") or item.get("text")
            payload = item
        else:
            continue
        task_title = (task_title or "").strip()
        if not task_title:
            continue
        created_tasks.append(create_task(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            source_note_id=note_id,
            title=task_title,
            status=payload.get("status") or "open",
            priority=payload.get("priority"),
            due_date=payload.get("due_date") or payload.get("due"),
            owner=payload.get("owner"),
            project=(payload.get("project") or (structured.get("projects") or [None])[0]),
            payload=payload,
            created_at=now,
        ))

    return {
        "note": note,
        "tasks": created_tasks,
        "structured": structured,
    }
