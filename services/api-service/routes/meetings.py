import httpx
from fastapi import APIRouter, HTTPException, Query, Depends
from config.settings import settings
from auth_deps import get_session_accounts, AccountPayload
from typing import List

router = APIRouter()

@router.get("")
async def get_meetings(
    user_id: str = Query(...),
    accounts: List[AccountPayload] = Depends(get_session_accounts)
):
    # Security check: verify that user_id matches one of the emails in the session
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail="Access denied. Account not in session.")

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
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.get("/pending")
async def get_pending_meetings(
    user_id: str = Query(...),
    accounts: List[AccountPayload] = Depends(get_session_accounts)
):
    # Security check: verify that user_id matches one of the emails in the session
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail="Access denied. Account not in session.")

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
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.post("/{id}/confirm")
async def confirm_meeting(
    id: int,
    accounts: List[AccountPayload] = Depends(get_session_accounts)
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
                raise HTTPException(status_code=403, detail="Access denied. Meeting owner mismatch.")
            
            return meeting
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.post("/{id}/dismiss")
async def dismiss_meeting(
    id: int,
    accounts: List[AccountPayload] = Depends(get_session_accounts)
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
                raise HTTPException(status_code=403, detail="Access denied. Meeting owner mismatch.")
            
            return meeting
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.post("/{id}/accept-update")
async def accept_update(
    id: int,
    accounts: List[AccountPayload] = Depends(get_session_accounts)
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
                raise HTTPException(status_code=403, detail="Access denied. Meeting owner mismatch.")
            
            return meeting
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.post("/{id}/remove")
async def remove_meeting(
    id: int,
    accounts: List[AccountPayload] = Depends(get_session_accounts)
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
                raise HTTPException(status_code=403, detail="Access denied. Meeting owner mismatch.")
            
            return meeting
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.get("/upcoming")
async def get_upcoming_meetings(
    user_id: str = Query(...),
    accounts: List[AccountPayload] = Depends(get_session_accounts)
):
    # Security check: verify that user_id matches one of the emails in the session
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail="Access denied. Account not in session.")

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
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.get("/dashboard")
async def get_dashboard(
    user_id: str = Query(...),
    accounts: List[AccountPayload] = Depends(get_session_accounts)
):
    # Security check: verify that user_id matches one of the emails in the session
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail="Access denied. Account not in session.")

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
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.post("/reminders/{id}/trigger")
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
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.get("/reminders/pending")
async def get_pending_reminders_proxy(
    user_id: str = Query(...),
    accounts: List[AccountPayload] = Depends(get_session_accounts)
):
    """
    Proxies GET pending reminders request to meeting service.
    """
    if not any(acc.email == user_id for acc in accounts):
        raise HTTPException(status_code=403, detail="Access denied. Account not in session.")
        
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
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

@router.post("/reminders/{id}/acknowledge")
async def acknowledge_reminder_proxy(
    id: int,
    accounts: List[AccountPayload] = Depends(get_session_accounts)
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
            raise HTTPException(status_code=502, detail=f"Failed to communicate with Meeting Service: {str(e)}")

