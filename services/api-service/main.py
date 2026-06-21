import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
import httpx

from config.settings import settings
from routes.auth import router as auth_router
from routes.emails import router as emails_router
from routes.meetings import router as meetings_router
from routes.tasks import router as tasks_router
from redis_client import redis_manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Azure Monitor OpenTelemetry if connection string is provided
if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING)
        logger.info("Azure Monitor OpenTelemetry configured successfully for api-service.")
    except Exception as e:
        logger.error(f"Failed to configure Azure Monitor OpenTelemetry: {str(e)}")

from database import db as pg_db, initialize_db as pg_initialize_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Redis and PostgreSQL pools
    logger.info("Starting api-service Gateway...")
    await redis_manager.initialize()
    try:
        await pg_initialize_db()
    except Exception as ex:
        logger.error(f"Failed to initialize PostgreSQL database on startup: {str(ex)}")
    yield
    # Shutdown: Close pools
    logger.info("Shutting down api-service Gateway...")
    await redis_manager.close()
    await pg_db.close()

app = FastAPI(
    title="AeroInbox API Gateway",
    description="Central gateway routing requests to auth, emails, and internal services.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS (allow frontend through proxy and dev servers explicitly)
origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost",
    "http://127.0.0.1",
    "https://aeroinbox.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.azurestaticapps\.net",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(emails_router, prefix="/emails", tags=["Emails"])
app.include_router(meetings_router, prefix="/meetings", tags=["Meetings"])
app.include_router(tasks_router, prefix="/tasks", tags=["Tasks"])

@app.post("/ai/process")
async def process_email(payload: dict):
    """
    Gateway endpoint for processing a single email.
    Forwards the request payload to the internal AI microservice and updates DB cache on-demand.
    """
    import json
    email_id = payload.get("email_id")
    email_content = payload.get("email_content")
    user_id = payload.get("user_id") or payload.get("account_email")
    
    # Forward only content to ai-service
    ai_payload = {"email_content": email_content}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.AI_SERVICE_URL}/process",
                json=ai_payload,
                timeout=45.0
            )
            if response.status_code != 200:
                detail_msg = "Error from AI Service"
                try:
                    detail_msg = response.json().get("detail", detail_msg)
                except Exception:
                    pass
                raise HTTPException(
                    status_code=response.status_code,
                    detail=detail_msg
                )
            
            ai_analysis = response.json()
            
            if email_id:
                try:
                    # Calculate Scores:
                    # AI Score: Critical/High=30, Medium=15, Low=0. Boost meeting (+10), deadline (+10)
                    ai_priority = ai_analysis.get("priority", "Low")
                    ai_score = 0
                    if ai_priority == "High" or ai_priority == "Critical":
                        ai_score = 30
                    elif ai_priority == "Medium":
                        ai_score = 15
                        
                    if ai_analysis.get("is_meeting_request"):
                        ai_score += 10
                    if ai_analysis.get("has_deadline"):
                        ai_score += 10
                        
                    # Fetch existing rule score if any
                    from database import db as pg_db
                    existing = await pg_db.fetchrow(
                        "SELECT rule_score, user_id FROM prioritized_emails WHERE email_id = $1", 
                        email_id
                    )
                    rule_score = existing["rule_score"] if existing else 0
                    if not user_id:
                        user_id = existing["user_id"] if existing else "unknown"
                    
                    final_score = ai_score + rule_score
                    if final_score >= 70:
                        final_priority = "Critical"
                    elif final_score >= 45:
                        final_priority = "High"
                    elif final_score >= 20:
                        final_priority = "Medium"
                    else:
                        final_priority = "Low"
                        
                    # Save / update cache
                    query = """
                        INSERT INTO prioritized_emails (
                            email_id, user_id, rule_score, ai_summary, ai_priority, ai_reply,
                            is_spam_false_positive, spam_analysis_reason, is_meeting_request, has_deadline, deadline_date,
                            final_priority, final_score, action_items
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                        ON CONFLICT (email_id) DO UPDATE SET
                            ai_summary = EXCLUDED.ai_summary,
                            ai_priority = EXCLUDED.ai_priority,
                            ai_reply = EXCLUDED.ai_reply,
                            is_spam_false_positive = EXCLUDED.is_spam_false_positive,
                            spam_analysis_reason = EXCLUDED.spam_analysis_reason,
                            is_meeting_request = EXCLUDED.is_meeting_request,
                            has_deadline = EXCLUDED.has_deadline,
                            deadline_date = EXCLUDED.deadline_date,
                            final_priority = EXCLUDED.final_priority,
                            final_score = EXCLUDED.final_score,
                            action_items = EXCLUDED.action_items;
                    """
                    await pg_db.execute(
                        query,
                        email_id,
                        user_id,
                        rule_score,
                        ai_analysis.get("summary"),
                        ai_analysis.get("priority"),
                        ai_analysis.get("reply"),
                        ai_analysis.get("is_spam_false_positive", False),
                        ai_analysis.get("spam_analysis_reason"),
                        ai_analysis.get("is_meeting_request", False),
                        ai_analysis.get("has_deadline", False),
                        ai_analysis.get("deadline_date"),
                        final_priority,
                        final_score,
                        json.dumps(ai_analysis.get("action_items", []))
                    )
                    logger.info(f"Updated cache for email {email_id} on-demand")
                    
                    # Insert tasks
                    action_items = ai_analysis.get("action_items", [])
                    if action_items and user_id != "unknown":
                        for item in action_items:
                            if not item or not item.strip():
                                continue
                            exists = await pg_db.fetchval(
                                "SELECT 1 FROM user_tasks WHERE email_id = $1 AND task_source = $2 AND title = $3",
                                email_id, "email_action_item", item
                            )
                            if not exists:
                                await pg_db.execute(
                                    """
                                    INSERT INTO user_tasks (user_id, task_source, email_id, title, description, status)
                                    VALUES ($1, $2, $3, $4, $5, $6)
                                    """,
                                    user_id, "email_action_item", email_id, item,
                                    "Extracted from email on-demand", "pending"
                                )
                                logger.info(f"Created on-demand AI task: {item}")
                except Exception as db_ex:
                    logger.error(f"Failed to update on-demand cache: {str(db_ex)}")
            
            return ai_analysis
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to communicate with AI Service: {str(e)}")

@app.get("/health")
async def health(response: Response):
    """
    Gateway health check verifying internal routing and Redis connectivity.
    """
    try:
        client = await redis_manager.get_client()
        await client.ping()
        redis_status = "healthy"
    except Exception as e:
        logger.error(f"Health check failed due to Redis connection error: {str(e)}", exc_info=True)
        redis_status = f"unhealthy: {str(e)}"

    if redis_status != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "service": "api-service",
            "redis": redis_status
        }
        
    return {
        "status": "healthy",
        "service": "api-service",
        "redis": redis_status
    }

@app.get("/healthz")
async def healthz():
    """
    Liveness probe endpoint.
    """
    return {
        "status": "healthy",
        "service": "api-service"
    }

@app.get("/ready")
async def ready(response: Response):
    """
    Readiness probe endpoint checking Redis and PostgreSQL connections.
    """
    redis_ok = True
    pg_ok = True
    
    # Check Redis
    try:
        client = await redis_manager.get_client()
        await client.ping()
    except Exception as e:
        logger.error(f"Readiness check failed - Redis connection error: {str(e)}")
        redis_ok = False
        
    # Check PostgreSQL
    try:
        await pg_db.fetchval("SELECT 1")
    except Exception as e:
        logger.error(f"Readiness check failed - PostgreSQL connection error: {str(e)}")
        pg_ok = False
        
    if not redis_ok or not pg_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "service": "api-service",
            "redis": "healthy" if redis_ok else "unhealthy",
            "postgres": "healthy" if pg_ok else "unhealthy"
        }
        
    return {
        "status": "ready",
        "service": "api-service"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
