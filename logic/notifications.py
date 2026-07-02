"""
Notification Engine for ThoughtOS

Provides ranked notifications for the header bar:
1. Due today tasks (highest priority)
2. Upcoming events (next 2 hours)
3. Pending enrichment items (transactions needing review)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import json

from logic.sql_engine import get_connection, get_needs_user_review


def get_pending_notifications(user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Returns a ranked list of notifications for the user.
    
    Each notification has:
    - id: Unique identifier
    - type: 'task' | 'event' | 'enrichment'
    - title: Display text
    - action_label: Button text (e.g., "Set Context", "Review")
    - action_type: What happens on click
    - context_data: Data needed to set context
    - priority: 1 (highest) to 3 (lowest)
    """
    notifications = []
    
    # 1. Due today tasks (priority 1)
    tasks = _get_due_today_tasks()
    for task in tasks:
        notifications.append({
            "id": f"task_{task['entry_id']}",
            "type": "task",
            "title": f"📋 Due today: {task['content_text'][:50]}",
            "action_label": "Set Context",
            "action_type": "set_context",
            "context_data": {
                "context_id": task['entry_id'],
                "context_type": "task",
                "summary": task['content_text']
            },
            "priority": 1
        })
    
    # 2. Upcoming events in next 2 hours (priority 2)
    events = _get_upcoming_events()
    for event in events:
        notifications.append({
            "id": f"event_{event['event_id']}",
            "type": "event",
            "title": f"📅 Coming up: {event['summary']}",
            "action_label": "Set Context",
            "action_type": "set_context",
            "context_data": {
                "context_id": event['event_id'],
                "context_type": "event",
                "summary": event['summary']
            },
            "priority": 2
        })
    
    # 3. Pending enrichment items (priority 3)
    enrichment_items = get_needs_user_review(user_id) if user_id else []
    if enrichment_items:
        count = len(enrichment_items)
        notifications.append({
            "id": "enrichment_queue",
            "type": "enrichment",
            "title": f"⚡ {count} transaction{'s' if count > 1 else ''} need review",
            "action_label": "Review",
            "action_type": "set_context",
            "context_data": {
                "context_id": "enrichment_queue",
                "context_type": "enrichment",
                "summary": f"Review {count} transactions"
            },
            "priority": 3
        })
    
    # Sort by priority
    notifications.sort(key=lambda x: x['priority'])
    
    return notifications


def _get_due_today_tasks() -> List[Dict[str, Any]]:
    """Get tasks that are due today."""
    conn = get_connection()
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        cursor = conn.execute("""
            SELECT entry_id, content_text, created_at
            FROM master_thoughts
            WHERE thought_type = 'task' 
            AND status != 'completed'
            AND DATE(created_at) <= ?
            ORDER BY created_at ASC
            LIMIT 5
        """, (today,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[NOTIFICATIONS] Error getting tasks: {e}")
        return []
    finally:
        conn.close()


def _get_upcoming_events() -> List[Dict[str, Any]]:
    """Get events happening in the next 2 hours."""
    conn = get_connection()
    try:
        now = datetime.now()
        two_hours_later = now + timedelta(hours=2)
        
        cursor = conn.execute("""
            SELECT event_id, summary, start_iso, end_iso
            FROM master_events
            WHERE start_iso >= ? AND start_iso <= ?
            ORDER BY start_iso ASC
            LIMIT 3
        """, (now.isoformat(), two_hours_later.isoformat()))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[NOTIFICATIONS] Error getting events: {e}")
        return []
    finally:
        conn.close()


def dismiss_notification(notification_id: str, user_id: Optional[str] = None) -> bool:
    """
    Dismiss a notification (snooze/skip).
    For now, this is a no-op since notifications are derived from data state.
    In the future, we could store dismissed notifications in a table.
    """
    # TODO: Implement persistence of dismissed notifications
    print(f"[NOTIFICATIONS] Dismissed: {notification_id}")
    return True
