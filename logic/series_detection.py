from collections import defaultdict
import difflib

def detect_series(events):
    """
    Groups events into series based on:
    1. recurringEventId (Explicit Google Calendar link)
    2. Fuzzy string matching on summary (Implicit series)
    """
    series_map = defaultdict(list)
    
    # 1. Explicit Grouping
    for event in events:
        if event.get('recurringEventId'):
            series_map[event['recurringEventId']].append(event)
        else:
            # Placeholders for implicit detection
            pass

    # 2. Implicit Grouping (Fuzzy Match)
    # This is a naive O(N^2) approach for v1, acceptable for <100 active events
    processed_ids = set()
    for key, group in series_map.items():
        for e in group:
            processed_ids.add(e['id'])
            
    non_recurring = [e for e in events if e['id'] not in processed_ids]
    
    # Group by exact summary match for now (simpler than fuzzy for v1)
    for event in non_recurring:
        summary = event['summary'].strip()
        found_group = False
        for key in list(series_map.keys()):
            # If key looks like a summary (not an ID)
            if " " in key and difflib.SequenceMatcher(None, key, summary).ratio() > 0.8:
                series_map[key].append(event)
                found_group = True
                break
        
        if not found_group:
            # Create new group using summary as key
            series_map[summary].append(event)

    # Format Output
    # We return a list of "Series" objects
    series_list = []
    for key, group in series_map.items():
        if len(group) > 1:
            # Sort by time
            group.sort(key=lambda x: x['start'])
            series_list.append({
                "series_id": key,
                "title": group[0]['summary'],
                "event_count": len(group),
                "events": group
            })
            
    return series_list
