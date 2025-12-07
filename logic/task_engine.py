from datetime import datetime, timedelta

def calculate_daily_energy(events):
    """
    Calculates the user's 'Energy Level' based on the density of today's calendar.
    
    Rules:
    - > 4 hours of meetings: LOW Energy
    - 2-4 hours of meetings: MEDIUM Energy
    - < 2 hours of meetings: HIGH Energy
    """
    if not events:
        return "HIGH"
        
    total_minutes = 0
    for event in events:
        # Parse ISO format (e.g., 2025-11-21T14:00:00Z)
        # Simplified parsing for now, assuming standard Google Calendar ISO
        try:
            start = event.get('start_iso') or event.get('start')
            end = event.get('end_iso') or event.get('end')
            
            if start and end:
                # Handle potential 'date' only events (all day)
                if 'T' in start:
                    s_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                    e_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                    duration = (e_dt - s_dt).total_seconds() / 60
                    total_minutes += duration
                else:
                    # All day event - assume 0 'meeting' minutes or treat differently?
                    # For now, ignore all-day events for energy calculation
                    pass
        except Exception as e:
            print(f"Error parsing event for energy: {e}")
            
    hours = total_minutes / 60
    
    if hours > 4:
        return "LOW"
    elif hours > 2:
        return "MEDIUM"
    else:
        return "HIGH"

def rank_tasks(tasks, energy_level):
    """
    Sorts tasks based on the User's Energy Level.
    
    Logic:
    - HIGH Energy: Prioritize 'High Effort' / 'Deep Work'
    - LOW Energy: Prioritize 'Low Effort' / 'Admin'
    """
    # Define effort mapping (Mock logic for now, or use LLM tags later)
    # Assuming tasks have a 'priority' or we infer effort from title
    
    def get_effort_score(task):
        # Lower score = Lower Effort
        title = task.get('content_text', '').lower()
        if any(x in title for x in ['call', 'email', 'check', 'schedule', 'pay']):
            return 1 # Low Effort
        if any(x in title for x in ['write', 'design', 'code', 'plan', 'build']):
            return 3 # High Effort
        return 2 # Medium
        
    # Sort
    if energy_level == "LOW":
        # Ascending effort (1 -> 3)
        return sorted(tasks, key=lambda x: get_effort_score(x))
    elif energy_level == "HIGH":
        # Descending effort (3 -> 1)
        return sorted(tasks, key=lambda x: get_effort_score(x), reverse=True)
    else:
        # Default: Sort by creation or ID (descending)
        return sorted(tasks, key=lambda x: x.get('entry_id', 0), reverse=True)
