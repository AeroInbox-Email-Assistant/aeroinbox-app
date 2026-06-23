import httpx
import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from config.settings import settings
from auth_deps import get_session_accounts, AccountPayload
from redis_client import redis_manager

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()

# Pydantic schemas for request/response payloads
class GetEmailsRequest(BaseModel):
    accounts: List[AccountPayload] = []
    include_read: bool = False

class GetEmailsResponse(BaseModel):
    emails: List[dict]
    refreshed_tokens: Dict[str, str]

class MarkSafeRequest(BaseModel):
    sender_email: str

async def trigger_meeting_detection(emails: List[dict]):
    """
    Triggers meeting detection asynchronously on the meeting service in the background.
    """
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{settings.MEETING_SERVICE_URL}/meetings/detect",
                json={"emails": emails},
                timeout=15.0
            )
        except Exception:
            logger.exception("Error triggering background meeting detection")

async def _save_single_email(email: dict):
    from database import db as pg_db
    query = """
        INSERT INTO prioritized_emails (
            email_id, user_id, rule_score, matched_rules, ai_summary, ai_priority, ai_reply,
            is_spam_false_positive, spam_analysis_reason, is_meeting_request, has_deadline, deadline_date,
            final_priority, final_score, action_items
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        ON CONFLICT (email_id) DO UPDATE SET
            rule_score = EXCLUDED.rule_score,
            matched_rules = EXCLUDED.matched_rules,
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
    rule_analysis = email.get("rule_analysis") or {}
    ai_analysis = email.get("ai_analysis") or {}
    
    matched_rules_json = json.dumps(rule_analysis.get("matched_rules", []))
    action_items_json = json.dumps(ai_analysis.get("action_items", []))
    
    try:
        await pg_db.execute(
            query,
            email.get("id"),
            email.get("account_email", "unknown"),
            rule_analysis.get("rule_score", 0),
            matched_rules_json,
            ai_analysis.get("summary") if ai_analysis else None,
            ai_analysis.get("priority") if ai_analysis else None,
            ai_analysis.get("reply") if ai_analysis else None,
            ai_analysis.get("is_spam_false_positive", False) if ai_analysis else False,
            ai_analysis.get("spam_analysis_reason") if ai_analysis else None,
            ai_analysis.get("is_meeting_request", False) if ai_analysis else False,
            ai_analysis.get("has_deadline", False) if ai_analysis else False,
            ai_analysis.get("deadline_date") if ai_analysis else None,
            email.get("final_priority", "Low"),
            email.get("final_score", 0),
            action_items_json
        )
    except Exception:
        logger.exception(f"Failed to cache email {email.get('id')} to database")

async def save_emails_to_cache(emails: List[dict]):
    """
    Saves the processed emails to the prioritized_emails table.
    """
    for email in emails:
        await _save_single_email(email)

async def refresh_google_token(refresh_token: str) -> Optional[str]:
    """
    Exchanges a refresh token for a new access token via Google APIs.
    """
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=data, timeout=10.0)
            if response.status_code == 200:
                return response.json().get("access_token")
            else:
                logger.error(f"Google Token refresh returned status {response.status_code}: {response.text}")
        except Exception:
            logger.exception("Exception refreshing Google token")
    return None

@router.get("/unread")
async def get_unread_emails_legacy(
    background_tasks: BackgroundTasks,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
):
    """
    Legacy GET endpoint for single-account backward compatibility.
    Calls the new multi-account logic under the hood with session accounts.
    """
    payload = GetEmailsRequest(
        accounts=accounts,
        include_read=False
    )
    result = await fetch_and_prioritize_emails(
        payload=payload,
        background_tasks=background_tasks,
        accounts=accounts,
        credentials=credentials
    )
    return result["emails"]

async def _fetch_account_emails(
    accounts: List[AccountPayload],
    include_read: bool,
    refreshed_tokens: dict,
    session_id: Optional[str]
) -> List[dict]:
    all_emails = []
    
    async def process_account(acc: AccountPayload):
        access_token = acc.access_token
        
        async with httpx.AsyncClient() as client:
            try:
                fetch_body = {
                    "accounts": [{"email": acc.email, "access_token": access_token}],
                    "include_read": include_read,
                    "max_results": 15
                }
                response = await client.post(
                    f"{settings.GMAIL_SERVICE_URL}/fetch",
                    json=fetch_body,
                    timeout=30.0
                )
                
                # Check for unauthorized (token expired)
                if response.status_code == 401 and acc.refresh_token:
                    logger.info(f"Access token expired for {acc.email}. Refreshing...")
                    new_token = await refresh_google_token(acc.refresh_token)
                    if new_token:
                        refreshed_tokens[acc.email] = new_token
                        # Update token in active local copy
                        access_token = new_token
                        
                        # Update in Redis session
                        if session_id:
                            try:
                                redis_client = await redis_manager.get_client()
                                session_key = f"session:{session_id}"
                                session_data = await redis_client.get(session_key)
                                if session_data:
                                    sess_accs = json.loads(session_data)
                                    for sa in sess_accs:
                                        if sa.get("email") == acc.email:
                                            sa["access_token"] = new_token
                                    await redis_client.setex(session_key, 3600, json.dumps(sess_accs))
                                    logger.info(f"Refreshed token updated in Redis session for {acc.email}")
                            except Exception:
                                logger.exception("Failed to update session token in Redis")

                        # Retry the request with the new access token
                        fetch_body["accounts"][0]["access_token"] = access_token
                        response = await client.post(
                            f"{settings.GMAIL_SERVICE_URL}/fetch",
                            json=fetch_body,
                            timeout=30.0
                        )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Gmail Service returned {response.status_code} for {acc.email}: {response.text}")
                    return []
            except Exception:
                logger.exception(f"Orchestrator error fetching emails for {acc.email}")
                return []
                  
    tasks = [process_account(acc) for acc in accounts]
    accounts_emails = await asyncio.gather(*tasks)
    
    for emails_list in accounts_emails:
        all_emails.extend(emails_list)
        
    return all_emails


async def _enrich_cached_emails(unread_emails: List[dict]) -> tuple[List[dict], List[dict]]:
    cached_unread_emails = []
    uncached_unread_emails = []
    
    if not unread_emails:
        return cached_unread_emails, uncached_unread_emails

    from database import db as pg_db
    email_ids = [e.get("id") for e in unread_emails]
    try:
        rows = await pg_db.fetch(
            "SELECT * FROM prioritized_emails WHERE email_id = ANY($1::varchar[])",
            email_ids
        )
        cache_map = {row["email_id"]: row for row in rows}
        
        for email in unread_emails:
            email_id = email.get("id")
            if email_id in cache_map:
                db_row = cache_map[email_id]
                matched_rules = db_row["matched_rules"]
                if isinstance(matched_rules, str):
                    try:
                        matched_rules = json.loads(matched_rules)
                    except Exception:
                        matched_rules = []
                        
                email["rule_analysis"] = {
                    "rule_score": db_row["rule_score"],
                    "matched_rules": matched_rules
                }
                
                if db_row["ai_priority"] is not None:
                    action_items = db_row.get("action_items")
                    if isinstance(action_items, str):
                        try:
                            action_items = json.loads(action_items)
                        except Exception:
                            action_items = []
                    elif not isinstance(action_items, list):
                        action_items = []
                    email["ai_analysis"] = {
                        "summary": db_row["ai_summary"],
                        "priority": db_row["ai_priority"],
                        "reply": db_row["ai_reply"],
                        "is_spam_false_positive": db_row["is_spam_false_positive"],
                        "spam_analysis_reason": db_row["spam_analysis_reason"],
                        "is_meeting_request": db_row["is_meeting_request"],
                        "has_deadline": db_row["has_deadline"],
                        "deadline_date": db_row["deadline_date"],
                        "action_items": action_items
                    }
                else:
                    email["ai_analysis"] = None
                    
                email["final_priority"] = db_row["final_priority"]
                email["final_score"] = db_row["final_score"]
                cached_unread_emails.append(email)
            else:
                uncached_unread_emails.append(email)
    except Exception:
        logger.exception("Error checking prioritized_emails database cache")
        uncached_unread_emails = unread_emails
        
    return cached_unread_emails, uncached_unread_emails


def _compute_hybrid_priority(email: dict, r_info: dict, ai_info: Optional[dict]) -> None:
    email["rule_analysis"] = {
        "rule_score": r_info.get("rule_score", 0),
        "matched_rules": r_info.get("matched_rules", [])
    }
    
    if ai_info:
        email["ai_analysis"] = {
            "summary": ai_info.get("summary"),
            "priority": ai_info.get("priority"),
            "reply": ai_info.get("reply"),
            "is_spam_false_positive": ai_info.get("is_spam_false_positive", False),
            "spam_analysis_reason": ai_info.get("spam_analysis_reason", ""),
            "is_meeting_request": ai_info.get("is_meeting_request", False),
            "has_deadline": ai_info.get("has_deadline", False),
            "deadline_date": ai_info.get("deadline_date", ""),
            "action_items": ai_info.get("action_items", [])
        }
    else:
        email["ai_analysis"] = None
        
    # Calculate Scores:
    # AI Score: Critical/High=30, Medium=15, Low=0. Boost meeting (+10), deadline (+10)
    ai_score = 0
    if email["ai_analysis"]:
        ai_priority = email["ai_analysis"].get("priority", "Low")
        if ai_priority == "High" or ai_priority == "Critical":
            ai_score = 30
        elif ai_priority == "Medium":
            ai_score = 15
            
        if email["ai_analysis"].get("is_meeting_request"):
            ai_score += 10
        if email["ai_analysis"].get("has_deadline"):
            ai_score += 10
            
    rule_score = email["rule_analysis"].get("rule_score", 0)
    preference_score = 0
    
    # Spam folder penalty/adjustment
    if email.get("folder") == "SPAM":
        if email["ai_analysis"] and email["ai_analysis"].get("is_spam_false_positive"):
            preference_score += 10
        else:
            ai_score = 0
            rule_score = 0
            
    final_score = ai_score + rule_score + preference_score
    
    if final_score >= 70:
        email["final_priority"] = "Critical"
    elif final_score >= 45:
        email["final_priority"] = "High"
    elif final_score >= 20:
        email["final_priority"] = "Medium"
    else:
        email["final_priority"] = "Low"
        
    email["final_score"] = final_score


@router.post("/unread", response_model=GetEmailsResponse)
async def fetch_and_prioritize_emails(
    payload: GetEmailsRequest,
    background_tasks: BackgroundTasks,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
):
    """
    Primary endpoint that fetches emails for multiple accounts, refreshes expired tokens,
    runs the rules engine & AI on unread messages, calculates hybrid priorities, and returns them.
    """
    session_id = credentials.credentials
    refreshed_tokens = {}
    
    # Overwrite the request accounts with validated credentials from the Redis session
    payload.accounts = accounts

    # 1. Fetch raw emails for each account in parallel
    all_emails = await _fetch_account_emails(payload.accounts, payload.include_read, refreshed_tokens, session_id)
        
    if all_emails:
        background_tasks.add_task(trigger_meeting_detection, all_emails)
        
    if not all_emails:
        return GetEmailsResponse(emails=[], refreshed_tokens=refreshed_tokens)
        
    # 2. Separate unread and read emails
    unread_emails = [e for e in all_emails if e.get("read_status") == "unread"]
    read_emails = [e for e in all_emails if e.get("read_status") == "read"]
    
    # 3. Check database cache for unread emails
    cached_unread_emails, uncached_unread_emails = await _enrich_cached_emails(unread_emails)
    
    # 4. Analyze uncached unread emails (rules engine + AI)
    if uncached_unread_emails:
        async with httpx.AsyncClient() as client:
            rule_task = client.post(
                f"{settings.RULE_ENGINE_SERVICE_URL}/evaluate/bulk",
                json=uncached_unread_emails,
                timeout=15.0
            )
            ai_task = client.post(
                f"{settings.AI_SERVICE_URL}/process/bulk",
                json={"emails": uncached_unread_emails},
                timeout=45.0
            )
            
            try:
                rule_res, ai_res = await asyncio.gather(rule_task, ai_task, return_exceptions=True)
                
                # Parse Rules Engine results
                rule_data = {}
                if isinstance(rule_res, httpx.Response) and rule_res.status_code == 200:
                    rule_data = rule_res.json()
                else:
                    logger.error(f"Rule Engine call failed: {rule_res}")
                    
                # Parse AI Service results
                ai_data = {}
                if isinstance(ai_res, httpx.Response) and ai_res.status_code == 200:
                    ai_data = ai_res.json()
                else:
                    logger.error(f"AI Service call failed: {ai_res}")
                    
                # Compute hybrid priority for each uncached email
                for email in uncached_unread_emails:
                    email_id = email.get("id")
                    r_info = rule_data.get(email_id, {"rule_score": 0, "matched_rules": []})
                    ai_info = ai_data.get(email_id)
                    _compute_hybrid_priority(email, r_info, ai_info)
                
                # Save new evaluations in background only if AI Service call succeeded
                if isinstance(ai_res, httpx.Response) and ai_res.status_code == 200:
                    background_tasks.add_task(save_emails_to_cache, uncached_unread_emails)
                else:
                    logger.warning("Skipping DB cache write for unread emails due to transient AI service failure.")
                
            except Exception:
                logger.exception("Error during orchestrator batch evaluation")
                for email in uncached_unread_emails:
                    email["rule_analysis"] = None
                    email["ai_analysis"] = None
                    email["final_priority"] = "Low"
                    email["final_score"] = 0
                    
    # 5. Process read emails (exclude from active prioritization)
    for email in read_emails:
        email["rule_analysis"] = None
        email["ai_analysis"] = None
        email["final_priority"] = None
        email["final_score"] = 0
        
    priority_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, None: 0}
    unread_emails.sort(key=lambda x: (priority_order.get(x.get("final_priority")), x.get("timestamp", 0)), reverse=True)
    read_emails.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    
    sorted_emails = unread_emails + read_emails
    
    # Auto-generate tasks from unread emails in background
    background_tasks.add_task(generate_email_tasks_in_background, unread_emails, payload.accounts)
    
    return GetEmailsResponse(emails=sorted_emails, refreshed_tokens=refreshed_tokens)

@router.get("/search", response_model=GetEmailsResponse)
async def search_emails(
    q: str = Query(..., description="Gmail search query string"),
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)] = None
):
    """
    Search emails across accounts using Gmail's query parameters.
    Enriches results with prioritized cache metadata if available.
    """
    session_id = credentials.credentials
    refreshed_tokens = {}
    all_emails = []
    
    # 1. Search emails for each account in parallel
    async def process_account_search(acc: AccountPayload):
        access_token = acc.access_token
        
        async with httpx.AsyncClient() as client:
            try:
                search_body = {
                    "accounts": [{"email": acc.email, "access_token": access_token}],
                    "q": q,
                    "max_results": 15
                }
                response = await client.post(
                    f"{settings.GMAIL_SERVICE_URL}/search",
                    json=search_body,
                    timeout=30.0
                )
                
                # Check for unauthorized (token expired)
                if response.status_code == 401 and acc.refresh_token:
                    logger.info(f"Access token expired for {acc.email} during search. Refreshing...")
                    new_token = await refresh_google_token(acc.refresh_token)
                    if new_token:
                        refreshed_tokens[acc.email] = new_token
                        access_token = new_token
                        
                        # Update in Redis session
                        if session_id:
                            try:
                                redis_client = await redis_manager.get_client()
                                session_key = f"session:{session_id}"
                                session_data = await redis_client.get(session_key)
                                if session_data:
                                    sess_accs = json.loads(session_data)
                                    for sa in sess_accs:
                                        if sa.get("email") == acc.email:
                                            sa["access_token"] = new_token
                                    await redis_client.setex(session_key, 3600, json.dumps(sess_accs))
                            except Exception:
                                logger.exception("Failed to update session token in Redis")

                        # Retry the request with the new access token
                        search_body["accounts"][0]["access_token"] = access_token
                        response = await client.post(
                            f"{settings.GMAIL_SERVICE_URL}/search",
                            json=search_body,
                            timeout=30.0
                        )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Gmail Service returned {response.status_code} during search for {acc.email}: {response.text}")
                    return []
            except Exception:
                logger.exception(f"Orchestrator error searching emails for {acc.email}")
                return []
                  
    tasks = [process_account_search(acc) for acc in accounts]
    accounts_emails = await asyncio.gather(*tasks)
    
    # Flatten emails
    for emails_list in accounts_emails:
        all_emails.extend(emails_list)
        
    if not all_emails:
        return GetEmailsResponse(emails=[], refreshed_tokens=refreshed_tokens)
        
    # 2. Enrich search results with cached prioritization metadata from PostgreSQL
    email_ids = [e.get("id") for e in all_emails]
    from database import db as pg_db
    try:
        rows = await pg_db.fetch(
            "SELECT * FROM prioritized_emails WHERE email_id = ANY($1::varchar[])",
            email_ids
        )
        cache_map = {row["email_id"]: row for row in rows}
    except Exception:
        logger.exception("Database error fetching search enrichments")
        cache_map = {}
        
    for email in all_emails:
        email_id = email.get("id")
        if email_id in cache_map:
            db_row = cache_map[email_id]
            matched_rules = db_row["matched_rules"]
            if isinstance(matched_rules, str):
                try:
                    matched_rules = json.loads(matched_rules)
                except Exception:
                    matched_rules = []
                    
            email["rule_analysis"] = {
                "rule_score": db_row["rule_score"],
                "matched_rules": matched_rules
            }
            
            if db_row["ai_priority"] is not None:
                email["ai_analysis"] = {
                    "summary": db_row["ai_summary"],
                    "priority": db_row["ai_priority"],
                    "reply": db_row["ai_reply"],
                    "is_spam_false_positive": db_row["is_spam_false_positive"],
                    "spam_analysis_reason": db_row["spam_analysis_reason"],
                    "is_meeting_request": db_row["is_meeting_request"],
                    "has_deadline": db_row["has_deadline"],
                    "deadline_date": db_row["deadline_date"]
                }
            else:
                email["ai_analysis"] = None
                
            email["final_priority"] = db_row["final_priority"]
            email["final_score"] = db_row["final_score"]
        else:
            email["rule_analysis"] = None
            email["ai_analysis"] = None
            email["final_priority"] = None
            email["final_score"] = 0
            
    priority_order = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, None: 0}
    all_emails.sort(key=lambda x: (priority_order.get(x.get("final_priority")), x.get("timestamp", 0)), reverse=True)
    
    return GetEmailsResponse(emails=all_emails, refreshed_tokens=refreshed_tokens)


async def _create_action_item_tasks(
    pg_db,
    email_id: str,
    user_id: str,
    sender: str,
    subject: str,
    ai_analysis: Optional[dict],
    existing_tasks: set
) -> None:
    if ai_analysis and isinstance(ai_analysis, dict):
        action_items = ai_analysis.get("action_items", [])
        for item in action_items:
            if not item or not item.strip():
                continue
            if (email_id, "email_action_item", item) not in existing_tasks:
                try:
                    await pg_db.execute(
                        """
                        INSERT INTO user_tasks (user_id, task_source, email_id, title, description, status)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        user_id,
                        "email_action_item",
                        email_id,
                        item,
                        f"Extracted from email from {sender} subject: '{subject}'",
                        "pending"
                    )
                    logger.info(f"Created AI action item task for email {email_id}: {item}")
                except Exception:
                    logger.exception("Failed to insert AI task")


async def _create_no_reply_tasks(
    pg_db,
    client: httpx.AsyncClient,
    thread_emails: List[dict],
    accounts: List[AccountPayload],
    existing_tasks: set
) -> None:
    if not thread_emails:
        return

    async def check_reply_task(email: dict, token: str):
        thread_id = email.get("thread_id")
        if not thread_id:
            return False
        try:
            res = await client.get(
                f"{settings.GMAIL_SERVICE_URL}/threads/{thread_id}/has-reply",
                params={"access_token": token},
                timeout=10.0
            )
            if res.status_code == 200:
                return res.json().get("has_reply", False)
        except Exception:
            logger.exception(f"Failed to check reply status for thread {thread_id}")
        return False

    thread_checks = []
    valid_thread_emails = []
    for email in thread_emails:
        user_id = email.get("account_email", "unknown")
        token = next((acc.access_token for acc in accounts if acc.email == user_id), None)
        if token:
            thread_checks.append(check_reply_task(email, token))
            valid_thread_emails.append(email)

    if thread_checks:
        results = await asyncio.gather(*thread_checks)
        for email, has_reply in zip(valid_thread_emails, results):
            if has_reply is False:
                email_id = email.get("id")
                user_id = email.get("account_email", "unknown")
                subject = email.get("subject", "No Subject")
                sender = email.get("sender", "Unknown Sender")
                no_reply_title = f"Reply to: {subject}"
                
                if (email_id, "email_no_reply", no_reply_title) not in existing_tasks:
                    try:
                        await pg_db.execute(
                            """
                            INSERT INTO user_tasks (user_id, task_source, email_id, title, description, status)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            """,
                            user_id,
                            "email_no_reply",
                            email_id,
                            no_reply_title,
                            f"You have not replied to this email thread from {sender}.",
                            "pending"
                        )
                        logger.info(f"Created No-Reply task for email {email_id}: {no_reply_title}")
                    except Exception:
                        logger.exception("Failed to insert No-Reply task")


async def generate_email_tasks_in_background(emails: List[dict], accounts: List[AccountPayload]):
    """
    Scans unread emails for AI action items or no-reply threads, creating tasks in user_tasks.
    """
    if not emails:
        return
        
    from database import db as pg_db
    email_ids = [e.get("id") for e in emails]
    
    try:
        # Fetch existing tasks to prevent duplicates
        rows = await pg_db.fetch(
            "SELECT email_id, task_source, title FROM user_tasks WHERE email_id = ANY($1::varchar[])",
            email_ids
        )
        existing_tasks = {(r["email_id"], r["task_source"], r["title"]) for r in rows}
    except Exception:
        logger.exception("Failed to fetch existing tasks")
        existing_tasks = set()
        
    thread_emails = []
    
    async with httpx.AsyncClient() as client:
        for email in emails:
            email_id = email.get("id")
            user_id = email.get("account_email", "unknown")
            subject = email.get("subject", "No Subject")
            sender = email.get("sender", "Unknown Sender")
            
            # Find account token
            token = next((acc.access_token for acc in accounts if acc.email == user_id), None)
            if not token:
                continue

            # 1. Check AI action items
            ai_analysis = email.get("ai_analysis")
            await _create_action_item_tasks(pg_db, email_id, user_id, sender, subject, ai_analysis, existing_tasks)

            # 2. Check no-reply status (only for emails classified as Critical, High, or Medium priority)
            if email.get("final_priority") in ("Critical", "High", "Medium"):
                thread_emails.append(email)

        await _create_no_reply_tasks(pg_db, client, thread_emails, accounts, existing_tasks)

async def perform_gmail_action(
    id: str,
    action_type: str, # "read", "unread", "move-to-inbox"
    accounts: List[AccountPayload],
    target_email: Optional[str] = None
):
    candidate_accounts = accounts
    if target_email:
        candidate_accounts = [acc for acc in accounts if acc.email == target_email]
        if not candidate_accounts:
            raise HTTPException(status_code=403, detail="Requested email account not in session.")

    last_error = None
    for acc in candidate_accounts:
        async with httpx.AsyncClient() as client:
            try:
                body = {"access_token": acc.access_token}
                if action_type == "read":
                    body["remove_labels"] = ["UNREAD"]
                elif action_type == "unread":
                    body["add_labels"] = ["UNREAD"]
                elif action_type == "move-to-inbox":
                    body["add_labels"] = ["INBOX"]
                    body["remove_labels"] = ["SPAM"]
                
                response = await client.post(
                    f"{settings.GMAIL_SERVICE_URL}/emails/{id}/labels",
                    json=body,
                    timeout=15.0
                )
                if response.status_code == 200:
                    return response.json()
                else:
                    last_error = HTTPException(status_code=response.status_code, detail=response.text)
            except httpx.HTTPError as e:
                last_error = HTTPException(status_code=502, detail=f"Failed to contact Gmail service: {str(e)}")
    
    if last_error:
        raise last_error
    raise HTTPException(status_code=400, detail="No active accounts to perform action.")

# Label Management Endpoints
@router.post("/{id}/read")
async def mark_read(
    id: str,
    email: Optional[str] = None,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """
    Removes the UNREAD label from a message.
    """
    return await perform_gmail_action(id, "read", accounts, email)

@router.post("/{id}/unread")
async def mark_unread(
    id: str,
    email: Optional[str] = None,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """
    Adds the UNREAD label back to a message.
    """
    return await perform_gmail_action(id, "unread", accounts, email)

@router.post("/{id}/move-to-inbox")
async def move_to_inbox(
    id: str,
    email: Optional[str] = None,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """
    Moves an email from Spam back to the Inbox.
    """
    return await perform_gmail_action(id, "move-to-inbox", accounts, email)

@router.post("/{id}/mark-safe")
async def mark_safe(
    id: str,
    payload: MarkSafeRequest,
    email: Optional[str] = None,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """
    Marks the sender of a spam email as safe (adds to VIP rules) and moves the email to Inbox.
    """
    target_emails = [acc.email for acc in accounts]
    if email:
        if email not in target_emails:
            raise HTTPException(status_code=403, detail="Requested email account not in session.")
        target_emails = [email]

    async with httpx.AsyncClient() as client:
        for u_id in target_emails:
            try:
                rules_resp = await client.get(f"{settings.RULE_ENGINE_SERVICE_URL}/rules", params={"user_id": u_id})
                if rules_resp.status_code == 200:
                    rules = rules_resp.json()
                    custom_senders = rules.get("custom_senders", [])
                    if payload.sender_email not in custom_senders:
                        custom_senders.append(payload.sender_email)
                        rules["custom_senders"] = custom_senders
                        await client.post(f"{settings.RULE_ENGINE_SERVICE_URL}/rules", params={"user_id": u_id}, json=rules)
            except Exception:
                logger.exception(f"Safe sender registration failed for {u_id}")
                
    return await perform_gmail_action(id, "move-to-inbox", accounts, email)

# Proxy endpoints for rules configuration
@router.get("/config/rules")
async def get_rules_proxy(
    user_id: Optional[str] = None,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """
    Proxies GET rules request to rule engine.
    """
    if not user_id:
        user_id = accounts[0].email if accounts else "default"
    else:
        if not any(acc.email == user_id for acc in accounts):
            raise HTTPException(status_code=403, detail="Access denied. Account not in session.")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{settings.RULE_ENGINE_SERVICE_URL}/rules", params={"user_id": user_id}, timeout=10.0)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to contact Rule Engine: {str(e)}")

@router.post("/config/rules")
async def update_rules_proxy(
    rules: dict,
    user_id: Optional[str] = None,
    accounts: Annotated[List[AccountPayload], Depends(get_session_accounts)] = None
):
    """
    Proxies POST rules request to rule engine.
    """
    if not user_id:
        user_id = accounts[0].email if accounts else "default"
    else:
        if not any(acc.email == user_id for acc in accounts):
            raise HTTPException(status_code=403, detail="Access denied. Account not in session.")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{settings.RULE_ENGINE_SERVICE_URL}/rules", params={"user_id": user_id}, json=rules, timeout=10.0)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            return response.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Failed to contact Rule Engine: {str(e)}")
