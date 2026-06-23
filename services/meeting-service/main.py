import os
import re
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# pyrefly: ignore [missing-import]
from prometheus_fastapi_instrumentator import Instrumentator

from repository import PostgreSQLMeetingRepository, Meeting, Participant
from config import settings
from service_bus import schedule_meeting_reminder

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants to avoid duplicate literal warnings
_MEETING_NOT_FOUND = "Meeting not found"
_REMINDER_NOT_FOUND = "Meeting reminder not found"

# Configure Azure Monitor OpenTelemetry if connection string is provided
if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING)
        logger.info("Azure Monitor OpenTelemetry configured successfully for meeting-service.")
    except Exception:
        logger.exception("Failed to configure Azure Monitor OpenTelemetry")

repo = PostgreSQLMeetingRepository()

async def reminder_polling_loop():
    """
    Background loop that runs inside the container.
    Every 60 seconds, it checks for reminders in the database that are due
    (reminder_time <= now) and have not been sent yet, and triggers them.
    This serves as a robust fallback if the serverless Azure Function App is skipped.
    """
    logger.info("Starting background meeting reminder scheduler loop...")
    import datetime as dt
    while True:
        try:
            await asyncio.sleep(60)
            now = dt.datetime.now(dt.timezone.utc)
            pool = await repo.get_pool()
            rows = await pool.fetch(
                "SELECT meeting_id FROM meeting_reminders WHERE sent = FALSE AND reminder_time <= $1",
                now
            )
            for row in rows:
                m_id = row["meeting_id"]
                logger.info("Background scheduler: reminder due for meeting %s. Triggering...", m_id)
                await repo.trigger_reminder(m_id)
        except Exception:
            logger.exception("Error in background reminder scheduler loop")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize connection pool and create tables
    logger.info("Initializing PostgreSQL database...")
    await repo.initialize_db()
    # Start the background reminder polling task
    polling_task = asyncio.create_task(reminder_polling_loop())
    yield
    # Close pool on shutdown
    logger.info("Closing PostgreSQL database connection pool...")
    polling_task.cancel()
    await repo.close()

app = FastAPI(
    title="AeroInbox Meeting Microservice",
    description="Internal microservice for meeting detection, calendar database operations, and management.",
    version="1.0.0",
    lifespan=lifespan
)
Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AI_SERVICE_URL = settings.AI_SERVICE_URL

# Regex pattern for platforms
MEET_REGEX = re.compile(r"https?://meet\.google\.com/[a-zA-Z0-9\-]+")
ZOOM_REGEX = re.compile(r"https?://(?:[a-zA-Z0-9\-]+\.)?zoom\.us/(?:j|my)/[a-zA-Z0-9\-\?#&=_]+")
TEAMS_REGEX = re.compile(r"https?://teams\.microsoft\.com/[a-zA-Z0-9\-\./\?#&=_%]+")

MEETING_KEYWORDS = [
    "meeting", "invite", "calendar", "schedule", "join", 
    "conference", "webinar", "meet", "call", "discuss", "appointment"
]

class DetectRequest(BaseModel):
    emails: List[dict]

def _unfold_ics_lines(lines: list[str]) -> list[str]:
    unfolded_lines = []
    for line in lines:
        if line.startswith((" ", "\t")) and unfolded_lines:
            unfolded_lines[-1] += line[1:]
        else:
            unfolded_lines.append(line)
    return unfolded_lines

def _parse_ics_properties(unfolded_lines: list[str]) -> tuple[dict, list]:
    data = {}
    participants = []
    for line in unfolded_lines:
        if ":" not in line:
            continue
        parts = line.split(":", 1)
        key_raw = parts[0]
        val = parts[1].strip()
        
        key = key_raw.split(";")[0].upper()
        
        if key == "SUMMARY":
            data["title"] = val
        elif key == "DESCRIPTION":
            data["description"] = val
        elif key == "DTSTART":
            data["dtstart"] = val
        elif key == "DTEND":
            data["dtend"] = val
        elif key == "LOCATION":
            data["location"] = val
        elif key == "ORGANIZER":
            email_match = re.search(r"mailto:([^\s>]+)", val, re.IGNORECASE)
            data["organizer"] = email_match.group(1) if email_match else val
            cn_match = re.search(r"CN=([^;:]+)", key_raw, re.IGNORECASE)
            if cn_match:
                data["organizer_name"] = cn_match.group(1).replace('"', '')
        elif key == "ATTENDEE":
            email_match = re.search(r"mailto:([^\s>]+)", val, re.IGNORECASE)
            email = email_match.group(1) if email_match else None
            if email:
                cn_match = re.search(r"CN=([^;:]+)", key_raw, re.IGNORECASE)
                name = cn_match.group(1).replace('"', '') if cn_match else None
                participants.append({"email": email, "name": name})
        elif key == "UID":
            data["uid"] = val
        elif key == "STATUS":
            data["status"] = val.upper()
        elif key == "METHOD":
            data["method"] = val.upper()
    return data, participants

def parse_ics_content(ics_text: str):
    """
    Searches and extracts VCALENDAR fields from email body.
    """
    match = re.search(r"BEGIN:VCALENDAR.*?END:VCALENDAR", ics_text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    
    block = match.group(0)
    lines = block.splitlines()
    unfolded_lines = _unfold_ics_lines(lines)
    return _parse_ics_properties(unfolded_lines)

def convert_ics_datetime(dt_str: str) -> str:
    """
    Parses ICS format datetime string and returns ISO-8601 string.
    """
    if ";" in dt_str:
        dt_str = dt_str.split(";")[-1]
    if ":" in dt_str:
        dt_str = dt_str.split(":")[-1]
    
    dt_str = dt_str.strip()
    
    if len(dt_str) == 8 and dt_str.isdigit():
        return f"{dt_str[0:4]}-{dt_str[4:6]}-{dt_str[6:8]}T00:00:00"
    
    match = re.match(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z)?", dt_str)
    if match:
        year, month, day, hour, minute, second, tz = match.groups()
        suffix = "Z" if tz else ""
        return f"{year}-{month}-{day}T{hour}:{minute}:{second}{suffix}"
        
    return dt_str

def has_meeting_keywords(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in MEETING_KEYWORDS)

def extract_meeting_url(text: str) -> tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    
    m_meet = MEET_REGEX.search(text)
    if m_meet:
        return m_meet.group(0), "Google Meet"
        
    m_zoom = ZOOM_REGEX.search(text)
    if m_zoom:
        return m_zoom.group(0), "Zoom"
        
    m_teams = TEAMS_REGEX.search(text)
    if m_teams:
        return m_teams.group(0), "Microsoft Teams"
        
    return None, None

async def _process_single_email(client: httpx.AsyncClient, email: dict):
    user_id = email.get("account_email")
    source_email_id = email.get("id")
    subject = email.get("subject", "")
    sender = email.get("sender", "")
    body = email.get("body", "") or email.get("snippet", "") or ""
    
    if not user_id or not source_email_id:
        return
    
    existing_by_email = await repo.get_meeting_by_source_email(user_id, source_email_id)
    if existing_by_email:
        return
    
    # Check for ICS
    ics_data = parse_ics_content(body)
    if ics_data:
        data, parts = ics_data
        
        start_dt = convert_ics_datetime(data.get("dtstart", ""))
        end_dt = convert_ics_datetime(data.get("dtend", "")) if data.get("dtend") else start_dt
        title = data.get("title", subject or "Meeting Invitation")
        
        loc = data.get("location", "")
        desc = data.get("description", "")
        meet_url, platform = extract_meeting_url(loc)
        if not meet_url:
            meet_url, platform = extract_meeting_url(desc)
        if not meet_url:
            platform = "Other"
            meet_url = loc or ""
        
        status = "Confirmed"
        method = data.get("method", "")
        ics_status = data.get("status", "")
        
        if method == "CANCEL" or ics_status == "CANCELLED" or "cancel" in title.lower() or "cancel" in desc.lower():
            status = "Cancelled"
            
        organizer = data.get("organizer", sender)
        participants = [Participant(participant_email=p["email"], participant_name=p["name"]) for p in parts]
        
        await save_or_update_meeting(
            user_id=user_id,
            source_email_id=source_email_id,
            source_platform="ics",
            meeting_platform=platform,
            meeting_url=meet_url,
            meeting_title=title,
            description=desc or data.get("description", ""),
            organizer=organizer,
            start_datetime=start_dt,
            end_datetime=end_dt,
            status=status,
            participants=participants
        )
        return

    # No ICS. Check for regex URL or keyword pre-filtering
    meet_url, platform = extract_meeting_url(body)
    if not meet_url:
        meet_url, platform = extract_meeting_url(subject)
    
    has_keywords = has_meeting_keywords(body) or has_meeting_keywords(subject)
    
    if meet_url or has_keywords:
        current_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = {
            "email_content": f"From: {sender}\nSubject: {subject}\nBody:\n{body}",
            "current_date": current_date_str
        }
        
        response = await client.post(
            f"{AI_SERVICE_URL}/process/meeting",
            json=payload,
            timeout=35.0
        )
        
        ai_res = None
        if response.status_code == 200:
            ai_res = response.json()
        else:
            logger.error("AI service returned non-200 status code %s for email %s: %s", response.status_code, source_email_id, response.text)
        
        is_meeting = False
        if ai_res and ai_res.get("is_meeting"):
            is_meeting = True
            ai_title = ai_res.get("meeting_title", subject or "Meeting")
            ai_platform = ai_res.get("meeting_platform", "Other")
            ai_url = ai_res.get("meeting_url", "")
            ai_organizer = ai_res.get("organizer", sender)
            ai_start_date = ai_res.get("start_date")
            ai_start_time = ai_res.get("start_time")
            ai_end_date = ai_res.get("end_date") or ai_start_date
            ai_end_time = ai_res.get("end_time")
            
            start_dt = f"{ai_start_date}T{ai_start_time}:00"
            end_dt = f"{ai_end_date}T{ai_end_time}:00"
            
            action_type = ai_res.get("action_type", "create")
            status = "Pending"  # Natural language requires user confirmation (Potential)
            
            final_url = meet_url or ai_url
            final_platform = platform or ai_platform
            if final_url:
                status = "Confirmed"  # Explicit meeting URL is classified as Confirmed
                
            if action_type == "cancel" or "cancel" in ai_title.lower():
                status = "Cancelled"
            elif action_type == "update":
                status = "Updated"
                
            ai_parts = ai_res.get("participants", [])
            participants = [Participant(participant_email=p["email"], participant_name=p.get("name")) for p in ai_parts if p.get("email")]
            
            await save_or_update_meeting(
                user_id=user_id,
                source_email_id=source_email_id,
                source_platform="gmail",
                meeting_platform=final_platform,
                meeting_url=final_url,
                meeting_title=ai_title,
                description=body[:500],
                organizer=ai_organizer,
                start_datetime=start_dt,
                end_datetime=end_dt,
                status=status,
                participants=participants
            )
        
        if not is_meeting and meet_url:
            # Fallback if Gemini failed or said no meeting but url matched
            start_dt = datetime.now(timezone.utc).isoformat()
            end_dt = start_dt
            await save_or_update_meeting(
                user_id=user_id,
                source_email_id=source_email_id,
                source_platform="gmail",
                meeting_platform=platform,
                meeting_url=meet_url,
                meeting_title=subject or "Meeting Link",
                description=body[:500],
                organizer=sender,
                start_datetime=start_dt,
                end_datetime=end_dt,
                status="Confirmed",
                participants=[]
            )

async def detect_meetings_from_emails(emails: List[dict]):
    """
    Detects and extracts meetings from emails. Operates in background.
    """
    async with httpx.AsyncClient() as client:
        for email in emails:
            try:
                await _process_single_email(client, email)
            except Exception:
                logger.exception("Error processing meeting detection for email %s", email.get('id'))

async def save_or_update_meeting(
    user_id: str,
    source_email_id: str,
    source_platform: str,
    meeting_platform: str,
    meeting_url: str,
    meeting_title: str,
    description: str,
    organizer: str,
    start_datetime: str,
    end_datetime: str,
    status: str,
    participants: List[Participant]
):
    now_str = datetime.now(timezone.utc).isoformat()
    
    existing = None
    if meeting_url:
        existing = await repo.get_meeting_by_url(user_id, meeting_url)
    if not existing:
        existing = await repo.get_meeting_by_title_and_organizer(user_id, meeting_title, organizer)
        
    if existing:
        if status == "Cancelled":
            existing.status = "Cancelled"
            existing.updated_timestamp = now_str
            await repo.update_meeting(existing)
            return
            
        if existing.start_datetime == start_datetime and existing.end_datetime == end_datetime:
            return
            
        # Reschedule detected
        existing.prev_start_datetime = existing.start_datetime
        existing.prev_end_datetime = existing.end_datetime
        existing.start_datetime = start_datetime
        existing.end_datetime = end_datetime
        existing.status = "Updated"
        existing.updated_timestamp = now_str
        
        # Merge participants
        existing_emails = {p.participant_email for p in existing.participants}
        for p in participants:
            if p.participant_email not in existing_emails:
                existing.participants.append(p)
        await repo.update_meeting(existing)
        if existing.status in ("Confirmed", "Updated"):
            await schedule_reminder_for_meeting(existing)
    else:
        # Create new meeting card
        new_meet = Meeting(
            user_id=user_id,
            source_email_id=source_email_id,
            source_platform=source_platform,
            meeting_platform=meeting_platform,
            meeting_url=meeting_url,
            meeting_title=meeting_title,
            description=description,
            organizer=organizer,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            status=status,
            calendar_added_flag=0,
            created_timestamp=now_str,
            updated_timestamp=now_str,
            participants=participants
        )
        await repo.create_meeting(new_meet)
        if new_meet.status in ("Confirmed", "Updated"):
            await schedule_reminder_for_meeting(new_meet)

async def schedule_reminder_for_meeting(meet: Meeting):
    """
    Parses start time, calculates reminder time (start - 30 minutes),
    saves to repository, and schedules via Service Bus client helper.
    """
    try:
        try:
            start_dt = datetime.fromisoformat(meet.start_datetime)
        except ValueError:
            dt_str = meet.start_datetime.replace("Z", "")
            start_dt = datetime.fromisoformat(dt_str)
            
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
            
        reminder_dt = start_dt - timedelta(minutes=30)
        
        # Save reminder state to DB
        await repo.create_or_update_reminder(
            user_id=meet.user_id,
            meeting_id=meet.id,
            title=meet.meeting_title,
            start_time=start_dt,
            reminder_time=reminder_dt
        )
        
        # Send to Service Bus / local simulation
        await schedule_meeting_reminder(
            meeting_id=meet.id,
            user_id=meet.user_id,
            title=meet.meeting_title,
            start_time=start_dt,
            reminder_time=reminder_dt
        )
        logger.info("Successfully scheduled reminder for meeting %s at %s", meet.id, reminder_dt)
    except Exception:
        logger.exception("Failed to schedule reminder for meeting %s", meet.id)

# API Routes
@app.post("/meetings/detect")
async def detect_meetings(payload: DetectRequest, background_tasks: BackgroundTasks):
    """
    Asynchronously detects meetings from a list of emails without blocking the Gateway.
    """
    background_tasks.add_task(detect_meetings_from_emails, payload.emails)
    return {"status": "queued", "count": len(payload.emails)}

@app.get("/meetings", response_model=List[Meeting])
async def get_meetings(user_id: str):
    """
    Get all confirmed meetings added to the calendar.
    """
    return await repo.list_meetings(user_id, calendar_added_only=True)

@app.get("/meetings/pending", response_model=List[Meeting])
async def get_pending_meetings(user_id: str):
    """
    Get all meetings not yet added to calendar (excluding Dismissed).
    """
    return await repo.list_pending_meetings(user_id)

@app.post("/meetings/{id}/confirm")
async def confirm_meeting(id: int):
    """
    Confirms/adds the meeting to the AeroInbox calendar.
    """
    meet = await repo.get_meeting(id)
    if not meet:
        raise HTTPException(status_code=404, detail=_MEETING_NOT_FOUND)
    meet.calendar_added_flag = 1
    meet.status = "Confirmed"
    meet.updated_timestamp = datetime.now(timezone.utc).isoformat()
    await repo.update_meeting(meet)
    await schedule_reminder_for_meeting(meet)
    return meet

@app.post("/meetings/{id}/dismiss")
async def dismiss_meeting(id: int):
    """
    Marks the meeting as Dismissed (intentionally ignored by the user).
    """
    meet = await repo.get_meeting(id)
    if not meet:
        raise HTTPException(status_code=404, detail=_MEETING_NOT_FOUND)
    meet.calendar_added_flag = 0
    meet.status = "Dismissed"
    meet.updated_timestamp = datetime.now(timezone.utc).isoformat()
    await repo.update_meeting(meet)
    return meet

@app.post("/meetings/{id}/accept-update")
async def accept_meeting_update(id: int):
    """
    Accepts the rescheduled time update, clearing prev_start_datetime.
    """
    meet = await repo.get_meeting(id)
    if not meet:
        raise HTTPException(status_code=404, detail=_MEETING_NOT_FOUND)
    meet.prev_start_datetime = None
    meet.prev_end_datetime = None
    meet.status = "Confirmed"
    meet.updated_timestamp = datetime.now(timezone.utc).isoformat()
    await repo.update_meeting(meet)
    await schedule_reminder_for_meeting(meet)
    return meet

@app.post("/meetings/reminders/{id}/trigger")
async def trigger_meeting_reminder_route(id: int):
    """
    Endpoint triggered by Azure Function (or local simulation) when reminder time is reached.
    Marks sent = True in DB.
    """
    success = await repo.trigger_reminder(id)
    if not success:
        raise HTTPException(status_code=404, detail=_REMINDER_NOT_FOUND)
    return {"status": "success", "message": f"Reminder for meeting {id} triggered"}

@app.get("/meetings/reminders/pending")
async def get_pending_reminders_route(user_id: str):
    """
    Fetches all pending unacknowledged reminders for the user.
    """
    reminders = await repo.get_pending_reminders(user_id)
    return reminders

@app.post("/meetings/reminders/{id}/acknowledge")
async def acknowledge_meeting_reminder_route(id: int):
    """
    Marks a meeting reminder as acknowledged by the user.
    """
    success = await repo.acknowledge_reminder(id)
    if not success:
        raise HTTPException(status_code=404, detail=_REMINDER_NOT_FOUND)
    return {"status": "success", "message": f"Reminder for meeting {id} acknowledged"}

@app.post("/meetings/{id}/remove")
async def remove_meeting(id: int):
    """
    Removes the meeting from the calendar (sets flag to 0 and status to Dismissed).
    """
    meet = await repo.get_meeting(id)
    if not meet:
        raise HTTPException(status_code=404, detail=_MEETING_NOT_FOUND)
    meet.calendar_added_flag = 0
    meet.status = "Dismissed"
    meet.updated_timestamp = datetime.now(timezone.utc).isoformat()
    await repo.update_meeting(meet)
    return meet

@app.get("/meetings/upcoming", response_model=List[Meeting])
async def get_upcoming_meetings(user_id: str):
    """
    Lists upcoming confirmed meetings.
    """
    return await repo.list_upcoming_meetings(user_id)

@app.get("/meetings/dashboard")
async def get_dashboard(user_id: str):
    """
    Groups confirmed meetings into Today, Tomorrow, Upcoming, and Missed.
    """
    all_cal = await repo.list_meetings(user_id, calendar_added_only=True)
    
    now = datetime.now(timezone.utc)
    # Format today's date in UTC
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    today_meetings = []
    tomorrow_meetings = []
    upcoming_meetings = []
    missed_meetings = []
    
    for meet in all_cal:
        try:
            m_date = meet.start_datetime.split("T")[0]
            clean_dt_str = meet.start_datetime
            if clean_dt_str.endswith("Z"):
                clean_dt_str = clean_dt_str[:-1]
            if "+" in clean_dt_str:
                clean_dt_str = clean_dt_str.split("+")[0]
                
            m_dt = datetime.fromisoformat(clean_dt_str)
            if m_dt.tzinfo is None:
                m_dt = m_dt.replace(tzinfo=timezone.utc)
                
            if m_dt < now:
                # Started in the past
                missed_meetings.append(meet)
            elif m_date == today_str:
                today_meetings.append(meet)
            elif m_date == tomorrow_str:
                tomorrow_meetings.append(meet)
            else:
                upcoming_meetings.append(meet)
        except Exception:
            upcoming_meetings.append(meet)
            
    return {
        "today": today_meetings,
        "tomorrow": tomorrow_meetings,
        "upcoming": upcoming_meetings,
        "missed": missed_meetings
    }

@app.get("/health")
async def health(response: Response):
    try:
        pool = await repo.get_pool()
        await pool.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    if db_status != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "service": "meeting-service",
            "database": db_status
        }
    return {
        "status": "healthy",
        "service": "meeting-service",
        "database": db_status
    }

@app.get("/healthz")
async def healthz():
    """
    Liveness probe endpoint.
    """
    return {
        "status": "healthy",
        "service": "meeting-service"
    }

@app.get("/ready")
async def ready(response: Response):
    """
    Readiness probe endpoint checking PostgreSQL and Service Bus connections.
    """
    errors = []
    
    # Check PostgreSQL
    try:
        pool = await repo.get_pool()
        await pool.execute("SELECT 1")
    except Exception as e:
        logger.exception("Readiness check failed - PostgreSQL connection error")
        errors.append(f"PostgreSQL: {str(e)}")
        
    # Check Service Bus
    try:
        import os
        queue_name = os.getenv("SERVICE_BUS_QUEUE_NAME")
        if not queue_name:
            raise ValueError("SERVICE_BUS_QUEUE_NAME environment variable is missing or empty")
            
        from service_bus import HAS_SERVICE_BUS
        if not HAS_SERVICE_BUS:
            raise ValueError("azure-servicebus is not installed")
        if not settings.SERVICE_BUS_CONNECTION_STRING:
            raise ValueError("SERVICE_BUS_CONNECTION_STRING is not configured")
            
        # pyrefly: ignore [missing-import]
        from azure.servicebus.aio import ServiceBusClient
        async with ServiceBusClient.from_connection_string(settings.SERVICE_BUS_CONNECTION_STRING) as client:
            async with client.get_queue_receiver(queue_name=queue_name) as receiver:
                await receiver.peek_messages(max_message_count=1)
    except Exception as e:
        logger.exception("Readiness check failed - Service Bus connection error")
        errors.append(f"Service Bus: {str(e)}")
        
    if errors:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not ready",
            "service": "meeting-service",
            "error": "; ".join(errors)
        }
        
    return {
        "status": "ready",
        "service": "meeting-service"
    }

if __name__ == "__main__":
    import uvicorn
    # Local dev binds exclusively to 127.0.0.1 loopback for network isolation
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
