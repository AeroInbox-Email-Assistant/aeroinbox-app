import logging
import datetime
from typing import List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from database import db as pg_db
from auth_deps import get_session_accounts, AccountPayload

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

# Shared response descriptions to document HTTP exceptions and avoid duplicates
_RESPONSES_500 = {
    500: {"description": "Internal server error"}
}
_RESPONSES_400_404_500 = {
    400: {"description": "Invalid parameter or status value"},
    404: {"description": "Task not found"},
    500: {"description": "Internal server error"}
}
_RESPONSES_404_500 = {
    404: {"description": "Task not found"},
    500: {"description": "Internal server error"}
}

class TaskCreate(BaseModel):
    user_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime.datetime] = None

class TaskUpdate(BaseModel):
    status: str # 'pending', 'completed', 'dismissed'

class SettingsUpdate(BaseModel):
    user_id: str
    reminder_interval_hours: int # e.g. 1, 2, 4, or 0/ -1 for disabled

@router.get("", responses=_RESPONSES_500)
async def get_tasks(
    user_id: Annotated[str, Query(..., description="The user's email address to filter tasks")]
):
    try:
        rows = await pg_db.fetch(
            "SELECT * FROM user_tasks WHERE user_id = $1 ORDER BY created_at DESC",
            user_id
        )
        return [dict(row) for row in rows]
    except Exception:
        logger.exception("Failed to fetch tasks for user %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to fetch tasks")

@router.post("", responses=_RESPONSES_500)
async def create_task(payload: TaskCreate):
    try:
        row = await pg_db.fetchrow(
            """
            INSERT INTO user_tasks (user_id, task_source, title, description, due_date, status)
            VALUES ($1, $2, $3, $4, $5, 'pending')
            RETURNING *
            """,
            payload.user_id,
            "manual",
            payload.title,
            payload.description,
            payload.due_date
        )
        return dict(row)
    except Exception:
        logger.exception("Failed to create manual task for user %s", payload.user_id)
        raise HTTPException(status_code=500, detail="Failed to create task")

@router.put("/{task_id}", responses=_RESPONSES_400_404_500)
async def update_task(task_id: int, payload: TaskUpdate):
    if payload.status not in ("pending", "completed", "dismissed"):
        raise HTTPException(status_code=400, detail="Invalid status value")
    try:
        row = await pg_db.fetchrow(
            """
            UPDATE user_tasks
            SET status = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
            RETURNING *
            """,
            payload.status,
            task_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to update task %s", task_id)
        raise HTTPException(status_code=500, detail="Failed to update task")

@router.delete("/{task_id}", responses=_RESPONSES_404_500)
async def delete_task(task_id: int):
    try:
        result = await pg_db.execute("DELETE FROM user_tasks WHERE id = $1", task_id)
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "message": f"Task {task_id} deleted"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete task %s", task_id)
        raise HTTPException(status_code=500, detail="Failed to delete task")

@router.get("/settings", responses=_RESPONSES_500)
async def get_settings(
    user_id: Annotated[str, Query(..., description="The user's email address")]
):
    try:
        row = await pg_db.fetchrow("SELECT * FROM user_settings WHERE user_id = $1", user_id)
        if not row:
            # Create default row
            row = await pg_db.fetchrow(
                """
                INSERT INTO user_settings (user_id, reminder_interval_hours, last_reminder_sent_at)
                VALUES ($1, 2, CURRENT_TIMESTAMP)
                RETURNING *
                """,
                user_id
            )
        return dict(row)
    except Exception:
        logger.exception("Failed to fetch settings for user %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to fetch settings")

@router.post("/settings", responses=_RESPONSES_500)
async def save_settings(payload: SettingsUpdate):
    try:
        row = await pg_db.fetchrow(
            """
            INSERT INTO user_settings (user_id, reminder_interval_hours, updated_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
                reminder_interval_hours = EXCLUDED.reminder_interval_hours,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            payload.user_id,
            payload.reminder_interval_hours
        )
        return dict(row)
    except Exception:
        logger.exception("Failed to save settings for user %s", payload.user_id)
        raise HTTPException(status_code=500, detail="Failed to save settings")

@router.get("/reminders/pending", responses=_RESPONSES_500)
async def get_pending_reminders(
    user_id: Annotated[str, Query(..., description="The user's email address")]
):
    try:
        # Get settings
        row = await pg_db.fetchrow("SELECT * FROM user_settings WHERE user_id = $1", user_id)
        if not row:
            row = await pg_db.fetchrow(
                """
                INSERT INTO user_settings (user_id, reminder_interval_hours, last_reminder_sent_at)
                VALUES ($1, 2, CURRENT_TIMESTAMP)
                RETURNING *
                """,
                user_id
            )
            
        interval = row["reminder_interval_hours"]
        # If interval is disabled (<= 0), return empty
        if interval <= 0:
            return []
            
        last_sent = row["last_reminder_sent_at"]
        now = datetime.datetime.now(datetime.timezone.utc)
        
        # Calculate time elapsed
        elapsed = (now - last_sent).total_seconds()
        # Convert interval in hours to seconds
        required_seconds = interval * 3600
        
        if elapsed >= required_seconds:
            # Fetch pending tasks
            pending_tasks = await pg_db.fetch(
                "SELECT * FROM user_tasks WHERE user_id = $1 AND status = 'pending' ORDER BY created_at DESC",
                user_id
            )
            if pending_tasks:
                # Update last reminder timestamp
                await pg_db.execute(
                    "UPDATE user_settings SET last_reminder_sent_at = $1 WHERE user_id = $2",
                    now,
                    user_id
                )
                return [dict(t) for t in pending_tasks]
                
        return []
    except Exception:
        logger.exception("Failed to check pending reminders for user %s", user_id)
        raise HTTPException(status_code=500, detail="Failed to check reminders")

