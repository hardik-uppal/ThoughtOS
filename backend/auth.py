import os
from google.oauth2 import id_token
from google.auth.transport import requests
from typing import Optional
from fastapi import HTTPException, Header, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Ensure GOOGLE_CLIENT_ID is set in .env
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

security = HTTPBearer()

def verify_google_token(token: str) -> dict:
    try:
        if not GOOGLE_CLIENT_ID:
            # DEV MODE: If no client ID, allow a mock token for testing?
            # Better to just fail or warn. For now, let's fail.
            print("WARNING: GOOGLE_CLIENT_ID not set.")
            
        idinfo = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)

        # ID token is valid. Get the user's Google Account ID from the decoded token.
        return idinfo
    except ValueError as e:
        # Invalid token
        raise HTTPException(status_code=401, detail=f"Invalid authentication credentials: {e}")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    """
    Dependency to get the current user from the Bearer token.
    Returns a dict with 'user_id' (email) and 'name'.
    """
    token = credentials.credentials
    user_info = verify_google_token(token)
    
    # We use email as the user_id for simplicity in this system
    return {
        "user_id": user_info['email'],
        "email": user_info['email'],
        "name": user_info.get('name', 'Unknown')
    }

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from logic.sql_engine import store_user_token, get_user_token
import json
import datetime

# Ensure CLIENT_SECRET is set (User needs to add this from their json file)
# For now, we might need to assume it's passed or loaded from a file
# Ideally, we should use the client_secrets.json file downloaded from Google Console
CLIENT_SECRETS_FILE = os.getenv("CLIENT_SECRETS_FILE", "client_secret.json")

def exchange_auth_code(auth_code: str):
    """
    Exchanges authorization code for tokens and stores them.
    Returns user info dict if success, None otherwise.
    """
    try:
        # Create flow instance to exchange code
        # Note: Scopes must match what was requested on frontend
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=[
                "https://www.googleapis.com/auth/userinfo.email", 
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/calendar.readonly", # Critical for sync
                "openid"
            ],
            redirect_uri='postmessage' # Important for React integration
        )
        
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        
        # Extract User Info from ID Token if available
        # google-auth-oauthlib flow usually fetches id_token if 'openid' scope is present
        id_token_jwt = None
        if creds.id_token:
            id_token_jwt = creds.id_token
        elif 'id_token' in flow.oauth2session.token:
            id_token_jwt = flow.oauth2session.token['id_token']
            
        user_info = {}
        if id_token_jwt:
            # Verify/Decode
            # We can use the same verifies logic
            user_info = verify_google_token(id_token_jwt)
            
        user_id = user_info.get('email')
        if not user_id:
            raise Exception("No email found in token response")

        # Store in DB
        store_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
            'expiry': creds.expiry.isoformat() if creds.expiry else None
        }
        
        store_user_token(user_id, store_data)
        
        # Return the credential (ID Token) for the frontend to use as session
        return {
            "credential": id_token_jwt,
            "user_id": user_id,
            "email": user_id,
            "name": user_info.get('name')
        }
    except Exception as e:
        print(f"Auth exchange failed: {e}")
        return None
    except Exception as e:
        print(f"Auth exchange failed: {e}")
        return False

def get_user_credentials(user_id: str) -> Optional[Credentials]:
    """
    Loads user credentials from DB and refreshes if necessary.
    """
    token_data = get_user_token(user_id)
    if not token_data:
        return None
        
    creds = Credentials(
        token=token_data['access_token'],
        refresh_token=token_data['refresh_token'],
        token_uri=token_data['token_uri'],
        client_id=token_data['client_id'],
        client_secret=token_data['client_secret'],
        scopes=token_data['scopes']
    )
    
    # Auto-refresh check could happen here or when used
    # If using requests, it auto-refreshes if we use authorized session
    return creds
