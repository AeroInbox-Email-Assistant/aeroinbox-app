import httpx
from fastapi import APIRouter, HTTPException, Query, Depends
from config.settings import settings
from auth_deps import get_session_accounts, AccountPayload
from typing import List, Annotated, Optional
from pydantic import BaseModel

router = APIRouter()

# Constants to avoid duplicating literals
_DENIED_SESSION = "Access denied. Account not in session."
_DENIED_MISMATCH = "Access denied. Meeting owner mismatch."
_ERR_COMMUNICATION = "Failed to communicate with Meeting Service"

_RESPONSES_403_502 = {
    403: {"description": "Access denied due to session or ownership mismatch"},
    502: {"description": "Failed to communicate with backend Meeting Service"}
}

_RESPONSES_502 = {
    502: {"description": "Failed to communicate with backend Meeting Service"}
}

class ManualMeetingRequest(BaseModel):
    user_id: str
    meeting_title: str
    meeting_url: Optional[str] = None
    meeting_platform: Optional[str] = "Other"
    start_datetime: str
    end_datetime: Optional[str] = None
    description: Optional[str] = None
    organizer: Optional[str] = None

@router.get("", responses=_RESPONSES_403_502)
async def get_meetings(
    user_id: Annotated[str, Query(...)],
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    # Security check: verify that user_id matches one of the emails in the session
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail=_DENIED_SESSION)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.MEETING_SERVICE_URL}/meetings",
                params={"user_id": user_id},
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.get("/pending", responses=_RESPONSES_403_502)
async def get_pending_meetings(
    user_id: Annotated[str, Query(...)],
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    # Security check: verify that user_id matches one of the emails in the session
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail=_DENIED_SESSION)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.MEETING_SERVICE_URL}/meetings/pending",
                params={"user_id": user_id},
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.post("/manual", status_code=201, responses=_RESPONSES_403_502)
async def create_manual_meeting(
    payload: ManualMeetingRequest,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """Proxy to create a manually entered meeting in meeting-service."""
    # Security check: user_id must belong to the authenticated session
    if not any(acc.email == payload.user_id for acc in accounts):
        raise HTTPException(status_code=403, detail=_DENIED_SESSION)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.MEETING_SERVICE_URL}/meetings/manual",
                json=payload.dict(),
                timeout=15.0
            )
            if response.status_code not in (200, 201):
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.post("/{id}/confirm", responses=_RESPONSES_403_502)
async def confirm_meeting(
    id: int,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.MEETING_SERVICE_URL}/meetings/{id}/confirm",
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            meeting = response.json()
            # Security check: verify that returned meeting's user_id is in session
            if not any(acc.email == meeting.get("user_id") for acc in accounts):
                raise HTTPException(status_code=403, detail=_DENIED_MISMATCH)
            
            return meeting
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.post("/{id}/dismiss", responses=_RESPONSES_403_502)
async def dismiss_meeting(
    id: int,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.MEETING_SERVICE_URL}/meetings/{id}/dismiss",
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            meeting = response.json()
            # Security check: verify that returned meeting's user_id is in session
            if not any(acc.email == meeting.get("user_id") for acc in accounts):
                raise HTTPException(status_code=403, detail=_DENIED_MISMATCH)
            
            return meeting
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.post("/{id}/accept-update", responses=_RESPONSES_403_502)
async def accept_update(
    id: int,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.MEETING_SERVICE_URL}/meetings/{id}/accept-update",
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            meeting = response.json()
            # Security check: verify that returned meeting's user_id is in session
            if not any(acc.email == meeting.get("user_id") for acc in accounts):
                raise HTTPException(status_code=403, detail=_DENIED_MISMATCH)
            
            return meeting
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.post("/{id}/remove", responses=_RESPONSES_403_502)
async def remove_meeting(
    id: int,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.MEETING_SERVICE_URL}/meetings/{id}/remove",
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            meeting = response.json()
            # Security check: verify that returned meeting's user_id is in session
            if not any(acc.email == meeting.get("user_id") for acc in accounts):
                raise HTTPException(status_code=403, detail=_DENIED_MISMATCH)
            
            return meeting
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.get("/upcoming", responses=_RESPONSES_403_502)
async def get_upcoming_meetings(
    user_id: Annotated[str, Query(...)],
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    # Security check: verify that user_id matches one of the emails in the session
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail=_DENIED_SESSION)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.MEETING_SERVICE_URL}/meetings/upcoming",
                params={"user_id": user_id},
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.get("/dashboard", responses=_RESPONSES_403_502)
async def get_dashboard(
    user_id: Annotated[str, Query(...)],
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    # Security check: verify that user_id matches one of the emails in the session
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail=_DENIED_SESSION)

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.MEETING_SERVICE_URL}/meetings/dashboard",
                params={"user_id": user_id},
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.post("/reminders/{id}/trigger", responses=_RESPONSES_502)
async def trigger_reminder_proxy(id: int):
    """
    Proxies reminder trigger callback to meeting service.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.MEETING_SERVICE_URL}/meetings/reminders/{id}/trigger",
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.get("/reminders/pending", responses=_RESPONSES_403_502)
async def get_pending_reminders_proxy(
    user_id: Annotated[str, Query(...)],
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """
    Proxies GET pending reminders request to meeting service.
    """
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail=_DENIED_SESSION)
        
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{settings.MEETING_SERVICE_URL}/meetings/reminders/pending",
                params={"user_id": user_id},
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")

@router.post("/reminders/{id}/acknowledge", responses=_RESPONSES_502)
async def acknowledge_reminder_proxy(
    id: int,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """
    Proxies reminder acknowledgment request to meeting service.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.MEETING_SERVICE_URL}/meetings/reminders/{id}/acknowledge",
                timeout=15.0
            )
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"{_ERR_COMMUNICATION}: {str(e)}")
