import json
import logging
from typing import List
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from redis_client import redis_manager

logger = logging.getLogger(__name__)
security = HTTPBearer()

class AccountPayload(BaseModel):
    email: str
    access_token: str = ""
    refresh_token: str = ""

async def get_session_accounts(credentials: HTTPAuthorizationCredentials = Depends(security)) -> List[AccountPayload]:
    """
    FastAPI dependency to extract and validate session_id from the authorization header.
    Queries Redis to retrieve account credentials and validates session expiration.
    """
    session_id = credentials.credentials
    if not session_id:
        raise HTTPException(status_code=401, detail="Missing session credentials.")

    redis_client = await redis_manager.get_client()
    session_key = f"session:{session_id}"
    
    session_data = await redis_client.get(session_key)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please login again.")

    try:
        accs = json.loads(session_data)
        if not isinstance(accs, list):
            raise HTTPException(status_code=401, detail="Malformed session data.")
        return [AccountPayload(**a) for a in accs]
    except Exception as e:
        logger.error(f"Failed to parse session accounts: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid session data format.")
