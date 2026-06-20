import uuid
import json
import urllib.parse
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import httpx

from config.settings import settings
from redis_client import redis_manager

logger = logging.getLogger(__name__)
router = APIRouter()

class TokenRefreshRequest(BaseModel):
    refresh_token: Optional[str] = None
    email: Optional[str] = None
    session_id: Optional[str] = None

@router.get("/login")
def login(session_id: Optional[str] = None):
    """
    Redirects the user to the Google OAuth2 consent screen.
    Propagates session_id in OAuth state parameter to allow multi-account association.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth credentials (GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET) are not configured."
        )

    # Propagate session_id if linking a new account to an existing session
    state = session_id if session_id else "new"

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile https://www.googleapis.com/auth/gmail.modify",
        "access_type": "offline",
        "prompt": "select_account consent",
        "state": state
    }
    
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return RedirectResponse(url)

@router.get("/callback")
async def callback(code: str = None, error: str = None, state: str = None):
    """
    Handles the redirect callback from Google OAuth.
    Exchanges the authorization code for tokens, saves credentials in Redis,
    and redirects to the frontend with the session_id.
    """
    if error:
        return RedirectResponse(f"{settings.FRONTEND_URL}/oauth-callback?error={urllib.parse.quote(error)}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Exchange authorization code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient() as client:
        try:
            token_response = await client.post(token_url, data=data)
            token_data = token_response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to connect to Google OAuth server: {str(e)}")

    if token_response.status_code != 200:
        error_description = token_data.get("error_description", "OAuth authorization code exchange failed.")
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/oauth-callback?error={urllib.parse.quote(error_description)}"
        )

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token", "")
    
    # Retrieve user profile using the access token
    email = ""
    async with httpx.AsyncClient() as client:
        try:
            userinfo_response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_response.status_code == 200:
                user_info = userinfo_response.json()
                email = user_info.get("email", "")
        except Exception as e:
            logger.error(f"Error fetching user info: {str(e)}")

    if not email:
        return RedirectResponse(
            f"{settings.FRONTEND_URL}/oauth-callback?error={urllib.parse.quote('Could not retrieve user email from Google.')}"
        )

    # Determine or generate session ID
    session_id = state if (state and state != "new" and len(state) >= 10) else uuid.uuid4().hex

    # Read existing accounts from Redis session if it exists
    redis_client = await redis_manager.get_client()
    session_key = f"session:{session_id}"
    
    existing_accounts = []
    session_data = await redis_client.get(session_key)
    if session_data:
        try:
            existing_accounts = json.loads(session_data)
        except Exception:
            existing_accounts = []

    # Filter/update accounts list
    updated_accounts = []
    account_added = False
    for acc in existing_accounts:
        if acc.get("email") == email:
            acc["access_token"] = access_token
            if refresh_token:
                acc["refresh_token"] = refresh_token
            updated_accounts.append(acc)
            account_added = True
        else:
            updated_accounts.append(acc)

    if not account_added:
        updated_accounts.append({
            "email": email,
            "access_token": access_token,
            "refresh_token": refresh_token
        })

    # Write back session details to Redis (1 hour TTL)
    await redis_client.setex(session_key, 3600, json.dumps(updated_accounts))

    # Save the refresh token in Redis under refresh:{email} persistently if returned
    if refresh_token:
        await redis_client.setex(f"refresh:{email}", 2592000, refresh_token) # 30 days TTL
    else:
        # Check if we already have it stored
        stored_refresh = await redis_client.get(f"refresh:{email}")
        if stored_refresh:
            # Re-propagate to session accounts if empty
            for acc in updated_accounts:
                if acc.get("email") == email and not acc.get("refresh_token"):
                    acc["refresh_token"] = stored_refresh
            await redis_client.setex(session_key, 3600, json.dumps(updated_accounts))

    # Redirect user to frontend. Mask the actual tokens inside the session ID.
    redirect_url = (
        f"{settings.FRONTEND_URL}/oauth-callback?"
        f"access_token={session_id}&"
        f"refresh_token=SESSION_MANAGED&"
        f"email={email}"
    )
    return RedirectResponse(redirect_url)

@router.post("/refresh")
async def refresh_session(payload: TokenRefreshRequest):
    """
    Refreshes session access tokens utilizing stored refresh tokens in Redis.
    """
    redis_client = await redis_manager.get_client()
    
    email = payload.email
    session_id = payload.session_id

    # Fallback/extract from session if not provided directly
    if not email and session_id:
        session_key = f"session:{session_id}"
        session_data = await redis_client.get(session_key)
        if session_data:
            try:
                accs = json.loads(session_data)
                if accs:
                    email = accs[0].get("email")
            except Exception:
                pass

    if not email:
        raise HTTPException(status_code=400, detail="Missing email or session details to perform refresh")

    # Fetch refresh token from Redis
    refresh_token = await redis_client.get(f"refresh:{email}")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token found. User must re-login.")

    # Call Google API to refresh access token
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=data)
            response_data = response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to connect to Google token server: {str(e)}")

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail=response_data.get("error_description", "Failed to refresh Google token")
        )

    new_access_token = response_data.get("access_token")

    # Update access token in session accounts list
    if session_id:
        session_key = f"session:{session_id}"
        session_data = await redis_client.get(session_key)
        existing_accounts = []
        if session_data:
            try:
                existing_accounts = json.loads(session_data)
            except Exception:
                pass

        updated = False
        for acc in existing_accounts:
            if acc.get("email") == email:
                acc["access_token"] = new_access_token
                updated = True
                break

        if not updated:
            existing_accounts.append({
                "email": email,
                "access_token": new_access_token,
                "refresh_token": refresh_token
            })

        # Save/renew session TTL
        await redis_client.setex(session_key, 3600, json.dumps(existing_accounts))
    else:
        # Generate new session if none was provided
        session_id = uuid.uuid4().hex
        session_key = f"session:{session_id}"
        accounts = [{
            "email": email,
            "access_token": new_access_token,
            "refresh_token": refresh_token
        }]
        await redis_client.setex(session_key, 3600, json.dumps(accounts))

    return {
        "session_id": session_id,
        "access_token": session_id,
        "expires_in": 3600
    }
