import os.path
import datetime
from googleapiclient.discovery import build
# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def fetch_events(days=30, creds=None):
    """Fetches events from the primary calendar for the next N days."""
    try:
        if not creds:
            return {"error": "Missing credentials"}
        
        service = build('calendar', 'v3', credentials=creds)

        # Call the Calendar API
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        time_max = (datetime.datetime.utcnow() + datetime.timedelta(days=days)).isoformat() + 'Z'
        
        events_result = service.events().list(calendarId='primary', timeMin=now,
                                              timeMax=time_max, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])
        
        parsed_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Simple formatting
            start_dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00')) if 'T' in start else datetime.datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.datetime.fromisoformat(end.replace('Z', '+00:00')) if 'T' in end else datetime.datetime.strptime(end, "%Y-%m-%d")

            parsed_events.append({
                "id": event['id'],
                "summary": event.get('summary', 'No Title'),
                "start": start_dt.strftime("%H:%M" if 'T' in start else "%Y-%m-%d"),
                "end": end_dt.strftime("%H:%M" if 'T' in end else "%Y-%m-%d"),
                "start_iso": start,
                "end_iso": end,
                "type": "meeting" if "meeting" in event.get('summary', '').lower() else "event",
                "recurringEventId": event.get('recurringEventId')
            })
            
        return parsed_events

    except Exception as e:
        return {"error": str(e)}
