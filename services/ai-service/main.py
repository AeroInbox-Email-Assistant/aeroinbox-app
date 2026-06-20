import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.openai_service import (
    analyze_email_content,
    analyze_emails_bulk,
    EmailAnalysis,
    EmailAnalysisItem,
    extract_meeting_from_text,
    MeetingExtractionResponse
)
from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Azure Monitor OpenTelemetry if connection string is provided
if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING)
        logger.info("Azure Monitor OpenTelemetry configured successfully for ai-service.")
    except Exception as e:
        logger.error(f"Failed to configure Azure Monitor OpenTelemetry: {str(e)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ai-service...")
    yield
    logger.info("Shutting down ai-service...")

app = FastAPI(
    title="AeroInbox AI Microservice",
    description="Internal microservice for analyzing emails and generating draft responses via Google Gemini / OpenAI / Azure OpenAI.",
    version="1.0.0",
    lifespan=lifespan
)

class EmailProcessRequest(BaseModel):
    email_content: str

class MeetingProcessRequest(BaseModel):
    email_content: str
    current_date: str

class BulkEmailProcessRequest(BaseModel):
    emails: list[dict]

@app.post("/process", response_model=EmailAnalysis)
def process_email(payload: EmailProcessRequest):
    """
    Processes a single email content and returns executive summary, priority, and reply suggestion.
    """
    try:
        analysis = analyze_email_content(payload.email_content)
        return analysis
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("Error during email processing")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process/bulk")
def process_emails_bulk(payload: BulkEmailProcessRequest):
    """
    Processes a batch of emails in a single Gemini request and returns analyses dictionary.
    """
    try:
        analyses = analyze_emails_bulk(payload.emails)
        return analyses
    except Exception as e:
        logger.exception("Error during bulk email processing")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process/meeting", response_model=MeetingExtractionResponse)
def process_meeting(payload: MeetingProcessRequest):
    """
    Analyzes email content and extracts structured meeting details using Gemini.
    """
    try:
        meeting_details = extract_meeting_from_text(payload.email_content, payload.current_date)
        return meeting_details
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.exception("Error during meeting processing")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy", "service": "ai-service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
