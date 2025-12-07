import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def authenticate_google():
    """Shows basic usage of the Google Calendar API.
    Prints the start and name of the next 10 events on the user's calendar.
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                # Token is invalid/revoked, delete it and re-auth
                if os.path.exists('token.json'):
                    os.remove('token.json')
                creds = None

        if not creds:
            if not os.path.exists('credentials.json'):
                return None # Signal that credentials are missing
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds

def fetch_events(days=30):
    """Fetches events from the primary calendar for the next N days."""
    try:
        creds = authenticate_google()
        if not creds:
            return {"error": "Missing credentials.json"}
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
