import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Security, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from typing import List, Optional
import asyncio
from services.gmail_service import fetch_emails, modify_message_labels, search_emails
from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Azure Monitor OpenTelemetry if connection string is provided
if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING)
        logger.info("Azure Monitor OpenTelemetry configured successfully for gmail-service.")
    except Exception as e:
        logger.error(f"Failed to configure Azure Monitor OpenTelemetry: {str(e)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting gmail-service...")
    yield
    logger.info("Shutting down gmail-service...")

app = FastAPI(
    title="AeroInbox Gmail Microservice",
    description="Internal microservice for fetching and parsing emails from the Gmail API.",
    version="1.0.0",
    lifespan=lifespan
)
Instrumentator().instrument(app).expose(app)

security = HTTPBearer()

class AccountCredential(BaseModel):
    email: str
    access_token: str

class FetchEmailsRequest(BaseModel):
    accounts: List[AccountCredential]
    include_read: bool = False
    max_results: int = 15

class ModifyLabelsRequest(BaseModel):
    access_token: str
    add_labels: List[str] = []
    remove_labels: List[str] = []

@app.get("/unread")
async def get_unread(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Exposes a backward-compatible endpoint to fetch unread emails for a single token.
    """
    token = credentials.credentials
    emails = await fetch_emails(access_token=token, include_read=False)
    return emails

@app.post("/fetch")
async def fetch_multi_account_emails(payload: FetchEmailsRequest):
    """
    Fetches emails from multiple Gmail accounts in parallel.
    """
    async def fetch_one(acc: AccountCredential):
        try:
            emails = await fetch_emails(
                access_token=acc.access_token,
                include_read=payload.include_read,
                max_results=payload.max_results
            )
            for email in emails:
                email["account_email"] = acc.email
            return emails
        except Exception as e:
            logger.error(f"Error fetching emails for {acc.email}: {str(e)}")
            return []

    tasks = [fetch_one(acc) for acc in payload.accounts]
    results = await asyncio.gather(*tasks)
    
    # Flatten the list of lists
    flat_list = [email for sublist in results for email in sublist]
    
    # Sort by timestamp descending (newest first)
    flat_list.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return flat_list

class SearchEmailsRequest(BaseModel):
    accounts: List[AccountCredential]
    q: str
    max_results: int = 15

@app.post("/search")
async def search_multi_account_emails(payload: SearchEmailsRequest):
    """
    Searches emails from multiple Gmail accounts in parallel using a search query.
    """
    async def search_one(acc: AccountCredential):
        try:
            emails = await search_emails(
                access_token=acc.access_token,
                q=payload.q,
                max_results=payload.max_results
            )
            for email in emails:
                email["account_email"] = acc.email
            return emails
        except Exception as e:
            logger.error(f"Error searching emails for {acc.email}: {str(e)}")
            return []

    tasks = [search_one(acc) for acc in payload.accounts]
    results = await asyncio.gather(*tasks)
    
    # Flatten the list of lists
    flat_list = [email for sublist in results for email in sublist]
    
    # Sort by timestamp descending (newest first)
    flat_list.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return flat_list

@app.post("/emails/{id}/labels")
async def modify_labels(id: str, payload: ModifyLabelsRequest):
    """
    Modifies label IDs (read/unread, move to inbox/spam) for a specific email message.
    """
    return modify_message_labels(
        access_token=payload.access_token,
        msg_id=id,
        add_labels=payload.add_labels,
        remove_labels=payload.remove_labels
    )

@app.get("/threads/{thread_id}/has-reply")
async def check_reply(thread_id: str, access_token: str):
    """
    Checks if a thread has any reply sent by the user.
    """
    from services.gmail_service import check_thread_has_reply
    has_reply = await check_thread_has_reply(access_token, thread_id)
    return {"thread_id": thread_id, "has_reply": has_reply}

@app.get("/health")
async def health():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy", "service": "gmail-service"}

@app.get("/healthz")
async def healthz():
    """
    Liveness probe endpoint.
    """
    return {
        "status": "healthy",
        "service": "gmail-service"
    }

@app.get("/ready")
async def ready(response: Response):
    """
    Readiness probe endpoint checking Key Vault connection.
    """
    import os
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient
    
    vault_url = os.getenv("AZURE_KEYVAULT_URL")
    if not vault_url:
        logger.error("AZURE_KEYVAULT_URL environment variable is missing or empty")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not ready",
            "service": "gmail-service",
            "error": "AZURE_KEYVAULT_URL environment variable is missing or empty"
        }
        
    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
        # Test connection by listing properties and fetching the first element
        props = client.list_properties_of_secrets()
        try:
            next(iter(props))
        except StopIteration:
            pass
        return {
            "status": "ready",
            "service": "gmail-service"
        }
    except Exception as e:
        logger.error(f"Readiness check failed - Key Vault connection error: {str(e)}")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not ready",
            "service": "gmail-service",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
