import os
import json
import logging
import datetime
import asyncio
from typing import Dict, Any
from config import settings

logger = logging.getLogger(__name__)

_SIMULATION_TASKS = set()

# Try to import azure.servicebus
try:
    from azure.servicebus.aio import ServiceBusClient
    from azure.servicebus import ServiceBusMessage
    HAS_SERVICE_BUS = True
except ImportError:
    HAS_SERVICE_BUS = False
    logger.warning("azure-servicebus not installed. Running meeting reminders in simulation fallback mode.")

async def schedule_meeting_reminder(meeting_id: int, user_id: str, title: str, start_time: datetime.datetime, reminder_time: datetime.datetime):
    """
    Schedules a meeting reminder message. If SERVICE_BUS_CONNECTION_STRING is provided,
    schedules the message in Azure Service Bus. Otherwise, runs a local simulation in-memory.
    """
    payload = {
        "meeting_id": meeting_id,
        "user_id": user_id,
        "title": title,
        "start_time": start_time.isoformat(),
        "reminder_time": reminder_time.isoformat()
    }
    
    # If connection string is empty, we fallback to local simulation
    if HAS_SERVICE_BUS and settings.SERVICE_BUS_CONNECTION_STRING:
        try:
            async with ServiceBusClient.from_connection_string(settings.SERVICE_BUS_CONNECTION_STRING) as client:
                async with client.get_queue_sender(settings.SERVICE_BUS_QUEUE_NAME) as sender:
                    message = ServiceBusMessage(json.dumps(payload))
                    # Enqueue at the calculated reminder time (must be in UTC)
                    # Convert reminder_time to UTC timezone-naive
                    reminder_utc = reminder_time.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                    await sender.schedule_messages(message, reminder_utc)
                    logger.info(f"Scheduled Service Bus message for meeting {meeting_id} at {reminder_utc}")
                    return
        except Exception:
            logger.exception("Failed to schedule Service Bus message. Falling back to local simulation.")
    
    # Local Simulation Fallback (in-memory background task)
    task = asyncio.create_task(simulate_local_reminder(meeting_id, reminder_time))
    _SIMULATION_TASKS.add(task)
    task.add_done_callback(_SIMULATION_TASKS.discard)

async def simulate_local_reminder(meeting_id: int, reminder_time: datetime.datetime):
    """
    Simulates a reminder locally by sleeping until the reminder time.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    # Ensure reminder_time is timezone-aware UTC
    if reminder_time.tzinfo is None:
        reminder_time = reminder_time.replace(tzinfo=datetime.timezone.utc)
        
    delay = (reminder_time - now).total_seconds()
    if delay <= 0:
        logger.info(f"Local simulation: reminder time for meeting {meeting_id} has already passed or is now. Triggering immediately.")
        await trigger_local_reminder(meeting_id)
        return
        
    logger.info(f"Local simulation: sleeping for {delay:.1f} seconds to trigger reminder for meeting {meeting_id}")
    await asyncio.sleep(delay)
    await trigger_local_reminder(meeting_id)

async def trigger_local_reminder(meeting_id: int):
    """
    Calls the local /meetings/reminders/{id}/trigger endpoint.
    """
    import httpx
    port = os.getenv("PORT", "8000")
    url = f"http://127.0.0.1:{port}/meetings/reminders/{meeting_id}/trigger"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, timeout=10.0)
            logger.info(f"Local simulation: Triggered reminder for meeting {meeting_id}, status code: {response.status_code}")
        except Exception:
            logger.exception(f"Local simulation: Failed to self-trigger reminder for meeting {meeting_id}")
