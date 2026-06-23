import os
import sqlite3
import hashlib
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional
import google.generativeai as genai
from pydantic import BaseModel, Field
from fastapi import HTTPException
from config import settings

db_path = os.getenv("CACHE_DATABASE_PATH", "ai_cache.db")

def init_cache_db():
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_cache (
                content_hash TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meeting_cache (
                content_hash TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.commit()
    except Exception as e:
        print(f"Error initializing cache database: {e}")
    finally:
        conn.close()

# Initialize database at import time
init_cache_db()

def get_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()

def get_cached_email(content_hash: str) -> Optional[str]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT response_json FROM email_cache WHERE content_hash = ?", (content_hash,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()

def set_cached_email(content_hash: str, response_json: str):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO email_cache (content_hash, response_json, created_at) VALUES (?, ?, ?)",
            (content_hash, response_json, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def get_cached_meeting(content_hash: str) -> Optional[str]:
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT response_json FROM meeting_cache WHERE content_hash = ?", (content_hash,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        conn.close()

def set_cached_meeting(content_hash: str, response_json: str):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO meeting_cache (content_hash, response_json, created_at) VALUES (?, ?, ?)",
            (content_hash, response_json, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

class EmailAnalysis(BaseModel):
    summary: str = Field(description="A concise executive summary of the email, highlighting the sender's main request and deadlines. Maximum 2-3 sentences.")
    priority: str = Field(description="Priority classification of the email. Allowed values: 'High', 'Medium', 'Low'.")
    reply: str = Field(description="A professional, polite, and concise reply suggestion written from the executive's perspective. Maximum 2 paragraphs.")
    is_spam_false_positive: bool = Field(description="True if the email was in spam but is actually a legitimate business email, a client inquiry, or meeting invitation (false positive spam).")
    spam_analysis_reason: Optional[str] = Field(default="", description="If the email is a spam false positive, give a brief 1-sentence reason (e.g. 'Legitimate business query from client').")
    is_meeting_request: bool = Field(description="True if this is a calendar invite, meeting request, call scheduler, or request to meet.")
    has_deadline: bool = Field(description="True if a task deadline or urgent date is mentioned in the email.")
    deadline_date: Optional[str] = Field(default="", description="The specific deadline date/time or timeframe (e.g. 'Friday at noon', 'June 10') if present.")
    action_items: list[str] = Field(default_factory=list, description="List of specific tasks or action items requested from the user in this email.")

class EmailAnalysisItem(BaseModel):
    id: str = Field(description="The unique message ID of the email being analyzed.")
    summary: str = Field(description="A concise executive summary of the email, highlighting the sender's main request and deadlines. Maximum 2-3 sentences.")
    priority: str = Field(description="Priority classification of the email. Allowed values: 'High', 'Medium', 'Low'.")
    reply: str = Field(description="A professional, polite, and concise reply suggestion written from the executive's perspective. Maximum 2 paragraphs.")
    is_spam_false_positive: bool = Field(description="True if the email was in spam but is actually a legitimate business email, a client inquiry, or meeting invitation (false positive spam).")
    spam_analysis_reason: Optional[str] = Field(default="", description="If the email is a spam false positive, give a brief 1-sentence reason (e.g. 'Legitimate business query from client').")
    is_meeting_request: bool = Field(description="True if this is a calendar invite, meeting request, call scheduler, or request to meet.")
    has_deadline: bool = Field(description="True if a task deadline or urgent date is mentioned in the email.")
    deadline_date: Optional[str] = Field(default="", description="The specific deadline date/time or timeframe (e.g. 'Friday at noon', 'June 10') if present.")
    action_items: list[str] = Field(default_factory=list, description="List of specific tasks or action items requested from the user in this email.")

class BulkEmailAnalysis(BaseModel):
    analyses: list[EmailAnalysisItem] = Field(description="List of email analyses matching the input email IDs.")

class MeetingParticipantItem(BaseModel):
    email: str = Field(description="Email address of the participant.")
    name: Optional[str] = Field(default="", description="Name or display name of the participant if mentioned, otherwise empty string.")

class MeetingExtractionResponse(BaseModel):
    is_meeting: bool = Field(description="True if the text contains a meeting request/invitation, reschedule/update, or cancellation. Otherwise False.")
    action_type: Optional[str] = Field(default="create", description="Type of action. Allowed values: 'create' (for new meetings), 'update' (for reschedules or timing updates), or 'cancel' (for cancellations).")
    meeting_title: Optional[str] = Field(default="", description="Title of the meeting. E.g. 'Sprint Planning'.")
    meeting_platform: Optional[str] = Field(default="Other", description="Platform for the meeting. Allowed values: 'Google Meet', 'Microsoft Teams', 'Zoom', or 'Other'.")
    meeting_url: Optional[str] = Field(default="", description="URL for joining the meeting if specified, otherwise empty string.")
    organizer: Optional[str] = Field(default="", description="The organizer's email address or name.")
    participants: Optional[list[MeetingParticipantItem]] = Field(default_factory=list, description="List of meeting participants (their email addresses or names if mentioned).")
    start_date: Optional[str] = Field(default="", description="Start date of the meeting in YYYY-MM-DD format. Resolve relative expressions relative to the current reference date context.")
    start_time: Optional[str] = Field(default="", description="Start time of the meeting in HH:MM format (24-hour).")
    end_date: Optional[str] = Field(default="", description="End date of the meeting in YYYY-MM-DD format.")
    end_time: Optional[str] = Field(default="", description="End time of the meeting in HH:MM format (24-hour). If not mentioned, set to 30 minutes after start_time.")

def get_api_key() -> str:
    """
    Resolves the Gemini API Key from environment variables.
    """
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    
    api_key = gemini_key
    if not api_key or api_key.startswith("your_"):
        if openai_key and openai_key.startswith("AIza"):
            api_key = openai_key
            
    if not api_key or api_key.startswith("your_"):
        raise HTTPException(
            status_code=500,
            detail="Gemini API Key (GEMINI_API_KEY) is not configured on the AI microservice."
        )
    return api_key

def extract_json_block(text: str) -> str:
    """
    Extracts the first valid JSON block from LLM output, ignoring conversational text and code fences.
    Uses string operations instead of regex to avoid backtracking vulnerabilities.
    """
    text_clean = text.strip()
    # Strip markdown code fences (```json ... ``` or ``` ... ```) using string search
    if "```" in text_clean:
        fence_start = text_clean.find("```")
        after_fence = text_clean[fence_start + 3:]
        # Skip optional language tag on the same token
        newline_pos = after_fence.find("\n")
        if newline_pos != -1:
            after_fence = after_fence[newline_pos + 1:]
        fence_end = after_fence.rfind("```")
        if fence_end != -1:
            candidate = after_fence[:fence_end].strip()
            first_brace = candidate.find("{")
            last_brace = candidate.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                return candidate[first_brace:last_brace + 1].strip()

    first_brace = text_clean.find("{")
    last_brace = text_clean.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text_clean[first_brace:last_brace + 1].strip()

    return text_clean

def lowercase_keys(data):
    """
    Recursively lowercases all keys in a dictionary or list of dictionaries.
    """
    if isinstance(data, dict):
        return {k.lower(): lowercase_keys(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [lowercase_keys(item) for item in data]
    return data

def call_openai_compatible_api(url: str, headers: dict, payload: dict) -> str:
    """
    Invokes an OpenAI-compatible endpoint using python's built-in urllib.request.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            if "choices" in res_json and len(res_json["choices"]) > 0:
                content = res_json["choices"][0]["message"]["content"]
                if not content:
                    raise RuntimeError("Model returned empty completions content.")
                return content
            else:
                raise RuntimeError(f"Unexpected API response payload: {res_body}")
    except urllib.error.HTTPError as e:
        try:
            error_body = e.read().decode("utf-8")
        except RuntimeError:
            error_body = "(could not read error body)"
        raise RuntimeError(f"HTTP Error {e.code}: {e.reason} - {error_body}")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"LLM request failed: {str(e)}")

CONTENT_TYPE_JSON = "application/json"
CHAT_COMPLETIONS_PATH = "/chat/completions"
_JSON_FORMAT_INSTR = "\nYour output MUST be a raw JSON object conforming strictly to the requested schema. Do not output markdown code fences or conversational text."


def _call_gemini(system_instruction: str, prompt: str, schema_class, gemini_key: str) -> str:
    """Call Google Gemini API."""
    if not gemini_key or gemini_key.startswith("your_"):
        raise HTTPException(status_code=500, detail="Gemini API Key is not configured.")
    genai.configure(api_key=gemini_key)
    try:
        model = genai.GenerativeModel(
            model_name="gemini-flash-latest",
            system_instruction=system_instruction
        )
        generation_config = genai.GenerationConfig(
            response_mime_type=CONTENT_TYPE_JSON
        )
        if schema_class:
            generation_config.response_schema = schema_class
        response = model.generate_content(prompt, generation_config=generation_config)
        if not response.text:
            raise RuntimeError("Gemini returned empty response.")
        return response.text
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Gemini API invocation failed: {str(e)}")


def _call_azure_openai(system_instruction: str, prompt: str, key: str, endpoint: str, deployment: str) -> str:
    """Call Azure OpenAI chat completions endpoint."""
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}{CHAT_COMPLETIONS_PATH}?api-version={api_version}"
    headers = {"api-key": key, "Content-Type": CONTENT_TYPE_JSON}
    payload = {
        "messages": [
            {"role": "system", "content": system_instruction + _JSON_FORMAT_INSTR},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    return call_openai_compatible_api(url, headers, payload)


def _build_foundry_url(base_endpoint: str) -> str:
    """Normalize Azure AI Foundry endpoint to a chat/completions URL."""
    url = base_endpoint
    if CHAT_COMPLETIONS_PATH not in url:
        base_url = url.split("?")[0].rstrip("/")
        query_params = url.split("?")[1] if "?" in url else ""
        if "/models" not in base_url and "/v1" not in base_url:
            base_url = f"{base_url}/models{CHAT_COMPLETIONS_PATH}"
        elif "/models" in base_url:
            base_url = f"{base_url}{CHAT_COMPLETIONS_PATH}"
        elif "/v1" in base_url:
            base_url = f"{base_url}{CHAT_COMPLETIONS_PATH}"
        url = f"{base_url}?{query_params}" if query_params else base_url
    if "api-version=" not in url:
        api_version = os.getenv("AZURE_AI_FOUNDRY_API_VERSION", "2024-05-01-preview")
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}api-version={api_version}"
    return url


def _call_azure_ai_foundry(system_instruction: str, prompt: str, key: str, endpoint: str) -> str:
    """Call Azure AI Foundry chat completions endpoint."""
    url = _build_foundry_url(endpoint)
    model_name = os.getenv("AZURE_AI_FOUNDRY_MODEL", "")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": CONTENT_TYPE_JSON}
    payload = {
        "messages": [
            {"role": "system", "content": system_instruction + _JSON_FORMAT_INSTR},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0
    }
    if model_name:
        payload["model"] = model_name
    return call_openai_compatible_api(url, headers, payload)


def _call_openai(system_instruction: str, prompt: str, key: str) -> str:
    """Call OpenAI chat completions endpoint."""
    api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    url = f"{api_base.rstrip('/')}{CHAT_COMPLETIONS_PATH}"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": CONTENT_TYPE_JSON}
    format_instr = "\nYour output MUST be a raw JSON object conforming strictly to the requested schema."
    payload = {
        "messages": [
            {"role": "system", "content": system_instruction + format_instr},
            {"role": "user", "content": prompt}
        ],
        "model": model_name,
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    return call_openai_compatible_api(url, headers, payload)


def _resolve_provider(provider: str, azure_openai_key: str, azure_openai_endpoint: str,
                      azure_openai_deployment: str, azure_ai_key: str, azure_ai_endpoint: str,
                      openai_key: str, gemini_key: str) -> tuple[str, str]:
    """Resolve AI provider and normalise gemini_key. Returns (provider, gemini_key)."""
    if provider:
        return provider, gemini_key
    if azure_openai_key and azure_openai_endpoint and azure_openai_deployment:
        return "azure_openai", gemini_key
    if azure_ai_key and azure_ai_endpoint:
        return "azure_ai_foundry", gemini_key
    if openai_key and not openai_key.startswith("your_") and not openai_key.startswith("AIza"):
        return "openai", gemini_key
    if gemini_key and not gemini_key.startswith("your_"):
        return "gemini", gemini_key
    if openai_key and openai_key.startswith("AIza"):
        return "gemini", openai_key
    raise HTTPException(
        status_code=500,
        detail="No AI Provider keys are configured. Please set GEMINI_API_KEY, AZURE_OPENAI_API_KEY, AZURE_AI_FOUNDRY_API_KEY, or OPENAI_API_KEY."
    )


def query_llm(system_instruction: str, prompt: str, schema_class=None) -> str:
    """
    Routes query to LLM provider resolved from environment.
    Priority: Azure OpenAI -> Azure AI Foundry -> OpenAI -> Gemini (default)
    """
    raw_provider = os.getenv("AI_PROVIDER", "").lower() or settings.AI_PROVIDER.lower()

    azure_openai_key = settings.AZURE_OPENAI_API_KEY or os.getenv("AZURE_OPENAI_API_KEY", "")
    azure_openai_endpoint = settings.AZURE_OPENAI_ENDPOINT or os.getenv("AZURE_OPENAI_ENDPOINT", "")
    azure_openai_deployment = settings.AZURE_OPENAI_DEPLOYMENT_NAME or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "")
    azure_ai_key = settings.AZURE_AI_FOUNDRY_API_KEY or os.getenv("AZURE_AI_FOUNDRY_API_KEY", "")
    azure_ai_endpoint = settings.AZURE_AI_FOUNDRY_ENDPOINT or os.getenv("AZURE_AI_FOUNDRY_ENDPOINT", "")
    openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
    gemini_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    provider, gemini_key = _resolve_provider(
        raw_provider, azure_openai_key, azure_openai_endpoint, azure_openai_deployment,
        azure_ai_key, azure_ai_endpoint, openai_key, gemini_key
    )

    if provider == "gemini":
        return _call_gemini(system_instruction, prompt, schema_class, gemini_key)
    if provider == "azure_openai":
        return _call_azure_openai(system_instruction, prompt, azure_openai_key, azure_openai_endpoint, azure_openai_deployment)
    if provider == "azure_ai_foundry":
        return _call_azure_ai_foundry(system_instruction, prompt, azure_ai_key, azure_ai_endpoint)
    if provider == "openai":
        return _call_openai(system_instruction, prompt, openai_key)
    raise HTTPException(status_code=500, detail=f"Unsupported AI provider: {provider}")


def analyze_email_content(email_content: str) -> EmailAnalysis:
    """
    Sends the email content to configured LLM.
    Returns a validated EmailAnalysis Pydantic model.
    """
    h = get_hash(email_content)
    cached_val = get_cached_email(h)
    if cached_val:
        try:
            return EmailAnalysis.model_validate_json(cached_val)
        except Exception:
            pass

    system_instruction = (
        "You are an elite, executive-level Chief of Staff AI assistant. "
        "Your goal is to parse incoming emails for CEOs, founders, and busy managers. "
        "Provide: "
        "1. Summary: Action-oriented, highlighting the main request and deadlines. Keep it brief (under 3 sentences).\n"
        "2. Priority:\n"
        "   - 'High': Actions needing immediate executive decisions, high-value client issues, or tight deadlines.\n"
        "   - 'Medium': Routine updates, non-urgent client followups, or scheduling requests.\n"
        "   - 'Low': Informational newsletters, internal FYI messages, or generic promotional emails.\n"
        "3. Reply: A concise, polished draft of a response. It must sound executive-grade (brief, polite, clear, and action-oriented). "
        "Ensure placeholders like [Your Name] are left only where absolutely necessary, but prioritize phrasing it clearly.\n"
        "4. is_spam_false_positive: Set to true if the email is a legitimate business email, a client inquiry, or meeting invitation (false positive spam).\n"
        "5. spam_analysis_reason: If the email is a spam false positive, give a brief 1-sentence reason (e.g. 'Legitimate business query from client').\n"
        "6. is_meeting_request: True if this is a calendar invite, meeting request, call scheduler, or request to meet.\n"
        "7. has_deadline: True if a task deadline or urgent date is mentioned in the email.\n"
        "8. deadline_date: The specific deadline date/time or timeframe (e.g. 'Friday at noon', 'June 10') if present.\n"
        "9. action_items: A list of specific actionable tasks/to-do items requested from the user in this email. If none, return an empty list."
    )

    try:
        raw_res = query_llm(
            system_instruction=system_instruction,
            prompt=f"Analyze the following email content:\n\n{email_content}",
            schema_class=EmailAnalysis
        )
        json_str = extract_json_block(raw_res)
        data = json.loads(json_str)
        data_normalized = lowercase_keys(data)
        parsed_result = EmailAnalysis.model_validate(data_normalized)
        
        try:
            set_cached_email(h, json.dumps(data_normalized))
        except Exception:
            pass
            
        return parsed_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI email analysis failed: {str(e)}")

def analyze_emails_bulk(emails: list[dict]) -> dict[str, EmailAnalysisItem]:
    """
    Sends a bulk list of emails to LLM in a single request for fast, cost-efficient analysis.
    Returns a dict mapping message_id -> EmailAnalysisItem.
    """
    if not emails:
        return {}

    results = {}
    emails_to_analyze = []
    
    for email in emails:
        email_id = email.get("id")
        body_snippet = (email.get("body") or email.get("snippet") or "")[:1200]
        content_str = f"{email.get('sender')}|{email.get('subject')}|{body_snippet}"
        h = get_hash(content_str)
        
        cached_val = get_cached_email(h)
        if cached_val:
            try:
                cached_data = json.loads(cached_val)
                cached_data["id"] = email_id
                results[email_id] = EmailAnalysisItem(**cached_data)
            except Exception:
                emails_to_analyze.append(email)
        else:
            emails_to_analyze.append(email)

    if not emails_to_analyze:
        return results

    email_prompts = []
    for email in emails_to_analyze:
        body_snippet = (email.get("body") or email.get("snippet") or "")[:1200]
        folder_info = f"FOLDER: {email.get('folder', 'INBOX')}\n"
        email_prompts.append(
            f"EMAIL ID: {email.get('id')}\n"
            f"FROM: {email.get('sender')}\n"
            f"SUBJECT: {email.get('subject')}\n"
            f"DATE: {email.get('date')}\n"
            f"{folder_info}"
            f"BODY:\n{body_snippet}\n"
            f"---"
        )
    
    formatted_emails = "\n\n".join(email_prompts)

    system_instruction = (
        "You are an elite, executive-level Chief of Staff AI assistant. "
        "Your task is to analyze a batch of emails and return an analysis for EACH email in the list. "
        "For each email ID, provide:\n"
        "1. Summary: Action-oriented, highlighting the main request and deadlines. Keep it brief (under 3 sentences).\n"
        "2. Priority:\n"
        "   - 'High': Actions needing immediate executive decisions, high-value client issues, or tight deadlines.\n"
        "   - 'Medium': Routine updates, non-urgent client followups, or scheduling requests.\n"
        "   - 'Low': Informational newsletters, internal FYI messages, or generic promotional emails.\n"
        "3. Reply: A concise, polished draft response written from the executive's perspective (max 2 paragraphs). "
        "Keep placeholders to a minimum, and write it in a professional, clear, action-oriented tone.\n"
        "4. is_spam_false_positive: Set to true if the email is located in the SPAM folder but contains a legitimate business query, customer/client communication, or meeting invitation.\n"
        "5. spam_analysis_reason: A brief explanation why the email is legitimate (if it is a false positive in SPAM).\n"
        "6. is_meeting_request: Set to true if the email is a calendar invitation, call scheduling request, or suggestion to meet.\n"
        "7. has_deadline: Set to true if a specific date or timeframe for a task/action is mentioned.\n"
        "8. deadline_date: The specific deadline date/time extracted if present.\n"
        "9. action_items: A list of specific actionable tasks/to-do items requested from the user in this email. If none, return an empty list."
    )

    try:
        raw_res = query_llm(
            system_instruction=system_instruction,
            prompt=f"Analyze the following batch of emails:\n\n{formatted_emails}",
            schema_class=BulkEmailAnalysis
        )
        json_str = extract_json_block(raw_res)
        data = json.loads(json_str)
        data_normalized = lowercase_keys(data)
        
        # Robust normalization for Pydantic BulkEmailAnalysis schema
        if isinstance(data_normalized, list):
            data_normalized = {"analyses": data_normalized}
        elif isinstance(data_normalized, dict) and "analyses" not in data_normalized:
            # If the keys of the dict are email IDs and values are dicts, convert to list
            analyses_list = []
            for k, v in data_normalized.items():
                if isinstance(v, dict):
                    if "id" not in v:
                        v["id"] = k
                    analyses_list.append(v)
            data_normalized = {"analyses": analyses_list}
            
        bulk_data = BulkEmailAnalysis.model_validate(data_normalized)
        
        for item in bulk_data.analyses:
            orig_email = next((e for e in emails_to_analyze if str(e.get("id")).strip().lower() == str(item.id).strip().lower()), None)
            if orig_email:
                body_snippet = (orig_email.get("body") or orig_email.get("snippet") or "")[:1200]
                content_str = f"{orig_email.get('sender')}|{orig_email.get('subject')}|{body_snippet}"
                h = get_hash(content_str)
                try:
                    set_cached_email(h, json.dumps(item.model_dump()))
                except Exception:
                    pass
                results[orig_email.get("id")] = item
            else:
                results[item.id] = item

        # Index-based fallback mapping for any unmapped input emails
        unmapped_emails = [e for e in emails_to_analyze if e.get("id") not in results]
        if unmapped_emails:
            mapped_item_ids = {item.id for item in results.values()}
            unmapped_analyses = [item for item in bulk_data.analyses if item.id not in mapped_item_ids]
            for i, email in enumerate(unmapped_emails):
                if i < len(unmapped_analyses):
                    item = unmapped_analyses[i]
                    item.id = email.get("id")
                    results[email.get("id")] = item
            
        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk AI email analysis failed: {str(e)}")

def extract_meeting_from_text(email_content: str, current_date_context: str) -> MeetingExtractionResponse:
    """
    Analyzes an email to extract structured meeting information, resolve relative dates, and classify action type.
    """
    content_str = f"{email_content}|{current_date_context}"
    h = get_hash(content_str)
    
    cached_val = get_cached_meeting(h)
    if cached_val:
        try:
            return MeetingExtractionResponse.model_validate_json(cached_val)
        except Exception:
            pass

    system_instruction = (
        "You are an expert Chief of Staff AI assistant specializing in calendar scheduling and email parsing. "
        "Your task is to analyze the email content and extract structured meeting details if the email mentions a meeting request, rescheduling, or cancellation. "
        f"The current reference date is {current_date_context}. Use this date to resolve relative date expressions like 'tomorrow', 'next Monday', etc. "
        "Rules:\n"
        "1. Identify if this email refers to a meeting request/invitation, reschedule, or cancellation. If so, set is_meeting=True. If not, set is_meeting=False.\n"
        "2. Determine the action_type: 'create' (for new meetings), 'update' (for reschedules or timing updates), or 'cancel' (for cancellations).\n"
        "3. Extract the meeting title (e.g., 'Sprint Review', 'Catch up'). If not clear, generate a professional title based on the context.\n"
        "4. Identify the platform ('Google Meet', 'Microsoft Teams', 'Zoom', or 'Other').\n"
        "5. Extract the join URL if present in the text.\n"
        "6. Extract the organizer (name and/or email address).\n"
        "7. Extract the list of participants (email and name if available).\n"
        "8. Resolve start_date and end_date in YYYY-MM-DD format. Resolve start_time and end_time in HH:MM format (24-hour). "
        "If the end time is not mentioned, make it 30 or 60 minutes after start_time.\n"
        "9. If is_meeting is False, you MUST still return the JSON structure; populate empty strings, false, or empty lists as appropriate."
    )

    try:
        raw_res = query_llm(
            system_instruction=system_instruction,
            prompt=f"Analyze the following email content and extract meeting details:\n\n{email_content}",
            schema_class=MeetingExtractionResponse
        )
        json_str = extract_json_block(raw_res)
        data = json.loads(json_str)
        data_normalized = lowercase_keys(data)
        parsed_result = MeetingExtractionResponse.model_validate(data_normalized)
        
        try:
            set_cached_meeting(h, json.dumps(data_normalized))
        except Exception:
            pass
            
        return parsed_result

    except Exception as e:
        import traceback
        print(f"ERROR: Meeting extraction failed: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Meeting extraction failed: {str(e)}")

