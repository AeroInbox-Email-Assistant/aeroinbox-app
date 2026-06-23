import os
import json
import logging
import datetime
import re
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field
# pyrefly: ignore [missing-import]
import asyncpg
# pyrefly: ignore [missing-import]
from prometheus_fastapi_instrumentator import Instrumentator
from azure.identity import DefaultAzureCredential

from config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Duplicated rule insertion SQL constant
_INSERT_RULE_QUERY = "INSERT INTO user_rules (user_id, rule_type, rule_value, score) VALUES ($1, $2, $3, $4)"

# Configure Azure Monitor OpenTelemetry if connection string is provided
if settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
        configure_azure_monitor(connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING)
        logger.info("Azure Monitor OpenTelemetry configured successfully for rule-engine-service.")
    except Exception:
        logger.exception("Failed to configure Azure Monitor OpenTelemetry")

# Database Pool Manager
class PostgresPoolManager:
    def __init__(self):
        self.pool = None
        self.token_expiry = None

    def get_password(self) -> str:
        if settings.DB_AUTH_METHOD == "entra":
            try:
                credential = DefaultAzureCredential()
                token_obj = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
                self.token_expiry = datetime.datetime.fromtimestamp(token_obj.expires_on, datetime.timezone.utc)
                logger.info("Retrieved Entra ID token, expires at: %s", self.token_expiry)
                return token_obj.token
            except Exception:
                logger.exception("Failed to fetch Entra ID token")
                return settings.DB_PASSWORD
        else:
            return settings.DB_PASSWORD

    async def initialize_pool(self):
        password = self.get_password()
        ssl_arg = "require" if settings.DB_SSL.lower() in ("true", "1", "yes") else None
        
        self.pool = await asyncpg.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            database=settings.DB_NAME,
            password=password,
            ssl=ssl_arg,
            min_size=2,
            max_size=10,
            max_inactive_connection_lifetime=1800.0, # Recycle idle connections every 30 mins
        )
        logger.info("PostgreSQL connection pool initialized for rule-engine-service.")

    async def get_pool(self):
        if settings.DB_AUTH_METHOD == "entra" and self.token_expiry:
            now = datetime.datetime.now(datetime.timezone.utc)
            if (self.token_expiry - now).total_seconds() < 300:
                logger.info("Entra ID token close to expiry, recreating pool...")
                await self.close()
                await self.initialize_pool()

        if not self.pool:
            await self.initialize_pool()
        return self.pool

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PostgreSQL connection pool closed.")

    async def execute(self, query: str, *args):
        pool = await self.get_pool()
        try:
            return await pool.execute(query, *args)
        except asyncpg.exceptions.InvalidAuthorizationSpecificationError:
            logger.warning("Auth error encountered, refreshing pool...")
            await self.close()
            pool = await self.get_pool()
            return await pool.execute(query, *args)

    async def fetch(self, query: str, *args):
        pool = await self.get_pool()
        try:
            return await pool.fetch(query, *args)
        except asyncpg.exceptions.InvalidAuthorizationSpecificationError:
            logger.warning("Auth error encountered, refreshing pool...")
            await self.close()
            pool = await self.get_pool()
            return await pool.fetch(query, *args)

db = PostgresPoolManager()

async def initialize_db():
    query_table = """
        CREATE TABLE IF NOT EXISTS user_rules (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            rule_type VARCHAR(50) NOT NULL,
            rule_value VARCHAR(255) NOT NULL,
            score INT NOT NULL DEFAULT 0,
            priority VARCHAR(50),
            active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """
    await db.execute(query_table)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_user_rules_user ON user_rules(user_id);")
    logger.info("Database user_rules table initialized.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize connection pool and create table
    await initialize_db()
    yield
    # Close pool on shutdown
    await db.close()

app = FastAPI(
    title="AeroInbox Rule Engine Service",
    description="Internal microservice to manage rules and evaluate rule-based email prioritization scores.",
    version="1.0.0",
    lifespan=lifespan
)
Instrumentator().instrument(app).expose(app)

class PreferenceBoosts(BaseModel):
    inbox_boost: int = 0
    spam_boost: int = 0

class RulesConfig(BaseModel):
    vip_senders: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    custom_senders: List[str] = Field(default_factory=list)
    custom_keywords: List[str] = Field(default_factory=list)
    custom_categories: Dict[str, Any] = Field(default_factory=dict)
    preference_boosts: PreferenceBoosts = Field(default_factory=PreferenceBoosts)

class EmailModel(BaseModel):
    id: str
    sender: str
    subject: str
    snippet: str
    body: str
    folder: str
    account_email: Optional[str] = None

class EmailEvaluationResult(BaseModel):
    rule_score: int
    matched_rules: List[str]

async def seed_default_rules(user_id: str):
    # Sanitize user controlled logging values to prevent log injection (CWE-117)
    safe_user_id = user_id.replace('\r', '').replace('\n', '')
    logger.info("Seeding default rules for user: %s", safe_user_id)
    defaults = [
        # vip_senders
        ("vip_sender", "ceo", 30),
        ("vip_sender", "founder", 30),
        ("vip_sender", "manager", 30),
        ("vip_sender", "board", 30),
        ("vip_sender", "director", 30),
        ("vip_sender", "vice president", 30),
        # domains
        ("domain", "client.com", 20),
        ("domain", "partner.com", 20),
        ("domain", "customer.com", 20),
        # keywords
        ("keyword", "urgent", 10),
        ("keyword", "action required", 10),
        ("keyword", "escalation", 10),
        ("keyword", "payment", 10),
        ("keyword", "invoice", 10),
        ("keyword", "compliance", 10),
        ("keyword", "immediately", 10),
        ("keyword", "asap", 10),
        ("keyword", "deadline", 10),
        # boosts
        ("preference_boost", "inbox_boost", 0),
        ("preference_boost", "spam_boost", 0)
    ]
    for rtype, rval, score in defaults:
        await db.execute(_INSERT_RULE_QUERY, user_id, rtype, rval, score)

def _populate_rules_config(rows) -> tuple:
    vip_senders = []
    domains = []
    keywords = []
    custom_senders = []
    custom_keywords = []
    custom_categories = {}
    preference_boosts = PreferenceBoosts(inbox_boost=0, spam_boost=0)

    for r in rows:
        rtype = r["rule_type"]
        rval = r["rule_value"]
        score = r["score"]

        if rtype == "vip_sender":
            vip_senders.append(rval)
        elif rtype == "domain":
            domains.append(rval)
        elif rtype == "keyword":
            keywords.append(rval)
        elif rtype == "custom_sender":
            custom_senders.append(rval)
        elif rtype == "custom_keyword":
            custom_keywords.append(rval)
        elif rtype == "custom_categories":
            try:
                custom_categories = json.loads(rval)
            except Exception:
                custom_categories = {}
        elif rtype == "preference_boost":
            if rval == "inbox_boost":
                preference_boosts.inbox_boost = score
            elif rval == "spam_boost":
                preference_boosts.spam_boost = score

    return vip_senders, domains, keywords, custom_senders, custom_keywords, custom_categories, preference_boosts

async def get_rules_for_user(user_id: str) -> RulesConfig:
    rows = await db.fetch("SELECT rule_type, rule_value, score FROM user_rules WHERE user_id = $1 AND active = TRUE", user_id)
    if not rows:
        await seed_default_rules(user_id)
        rows = await db.fetch("SELECT rule_type, rule_value, score FROM user_rules WHERE user_id = $1 AND active = TRUE", user_id)

    vip_senders, domains, keywords, custom_senders, custom_keywords, custom_categories, preference_boosts = _populate_rules_config(rows)

    return RulesConfig(
        vip_senders=vip_senders,
        domains=domains,
        keywords=keywords,
        custom_senders=custom_senders,
        custom_keywords=custom_keywords,
        custom_categories=custom_categories,
        preference_boosts=preference_boosts
    )

async def save_rules_for_user(user_id: str, config: RulesConfig):
    await db.execute("DELETE FROM user_rules WHERE user_id = $1", user_id)
    
    # Insert new configuration
    for val in config.vip_senders:
        await db.execute(_INSERT_RULE_QUERY, user_id, "vip_sender", val, 30)
    for val in config.domains:
        await db.execute(_INSERT_RULE_QUERY, user_id, "domain", val, 20)
    for val in config.keywords:
        await db.execute(_INSERT_RULE_QUERY, user_id, "keyword", val, 10)
    for val in config.custom_senders:
        await db.execute(_INSERT_RULE_QUERY, user_id, "custom_sender", val, 35)
    for val in config.custom_keywords:
        await db.execute(_INSERT_RULE_QUERY, user_id, "custom_keyword", val, 15)
    if config.custom_categories:
        await db.execute(_INSERT_RULE_QUERY, user_id, "custom_categories", json.dumps(config.custom_categories), 0)
    await db.execute(_INSERT_RULE_QUERY, user_id, "preference_boost", "inbox_boost", config.preference_boosts.inbox_boost)
    await db.execute(_INSERT_RULE_QUERY, user_id, "preference_boost", "spam_boost", config.preference_boosts.spam_boost)

@app.get("/rules", response_model=RulesConfig)
async def get_rules(user_id: str = "default"):
    """
    Returns the currently configured rules database.
    """
    return await get_rules_for_user(user_id)

@app.post("/rules", response_model=RulesConfig)
async def update_rules(config: RulesConfig, user_id: str = "default"):
    """
    Overwrites the rules database with a new configuration.
    """
    await save_rules_for_user(user_id, config)
    return config

def _evaluate_single_email(email: EmailModel, rules: RulesConfig) -> EmailEvaluationResult:
    vip_senders = [v.lower() for v in rules.vip_senders]
    domains = [d.lower().strip("@") for d in rules.domains]
    keywords = [k.lower() for k in rules.keywords]
    custom_senders = [cs.lower() for cs in rules.custom_senders]
    custom_keywords = [ck.lower() for ck in rules.custom_keywords]
    inbox_boost = rules.preference_boosts.inbox_boost
    spam_boost = rules.preference_boosts.spam_boost

    rule_score = 0
    matched_rules = []
    sender_lower = email.sender.lower()
    subject_lower = email.subject.lower()
    snippet_lower = email.snippet.lower()
    body_lower = email.body.lower()

    # 1. VIP Senders
    vip_matched = False
    for vip in vip_senders:
        if vip in sender_lower:
            rule_score += 30
            matched_rules.append(f"VIP Sender Title: {vip}")
            vip_matched = True
            break

    # 2. Custom User Senders
    if not vip_matched:
        for cs in custom_senders:
            if cs in sender_lower:
                rule_score += 35
                matched_rules.append(f"Custom VIP Sender: {cs}")
                break

    # 3. Domain Rules
    email_match = re.search(r'[\w\.-]+@([\w\.-]+)', sender_lower)
    if email_match:
        sender_domain = email_match.group(1)
        for d in domains:
            if d in sender_domain:
                rule_score += 20
                matched_rules.append(f"Important Domain: @{d}")
                break

    # 4. Standard Keywords
    kw_matched_count = 0
    for kw in keywords:
        if kw in subject_lower or kw in snippet_lower:
            rule_score += 10
            matched_rules.append(f"Urgent Keyword: {kw}")
            kw_matched_count += 1
            if kw_matched_count >= 3:
                break

    # 5. Custom User Keywords
    custom_kw_matched_count = 0
    for ck in custom_keywords:
        if ck in subject_lower or ck in body_lower:
            rule_score += 15
            matched_rules.append(f"Custom Keyword Match: {ck}")
            custom_kw_matched_count += 1
            if custom_kw_matched_count >= 2:
                break

    # 6. Folder boosts
    if email.folder.upper() == "INBOX" and inbox_boost != 0:
        rule_score += inbox_boost
        matched_rules.append(f"Folder Preference Boost: Inbox ({inbox_boost})")
    elif email.folder.upper() == "SPAM" and spam_boost != 0:
        rule_score += spam_boost
        matched_rules.append(f"Folder Preference Boost: Spam ({spam_boost})")

    return EmailEvaluationResult(
        rule_score=rule_score,
        matched_rules=matched_rules
    )

@app.post("/evaluate/bulk", response_model=Dict[str, EmailEvaluationResult])
async def evaluate_emails_bulk(emails: List[EmailModel]):
    """
    Runs rule matching logic over a list of emails and returns rule scores and match reasons.
    """
    user_rules_cache = {}
    results = {}

    for email in emails:
        user_id = email.account_email or "default"
        if user_id not in user_rules_cache:
            user_rules_cache[user_id] = await get_rules_for_user(user_id)

        rules = user_rules_cache[user_id]
        results[email.id] = _evaluate_single_email(email, rules)

    return results

@app.get("/health")
async def health(response: Response):
    try:
        pool = await db.get_pool()
        await pool.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    if db_status != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "service": "rule-engine-service",
            "database": db_status
        }
    return {
        "status": "healthy",
        "service": "rule-engine-service",
        "database": db_status
    }

@app.get("/healthz")
async def healthz():
    """
    Liveness probe endpoint.
    """
    return {
        "status": "healthy",
        "service": "rule-engine"
    }

@app.get("/ready")
async def ready(response: Response):
    """
    Readiness probe endpoint checking PostgreSQL connection.
    """
    try:
        pool = await db.get_pool()
        await pool.execute("SELECT 1")
        return {
            "status": "ready",
            "service": "rule-engine"
        }
    except Exception:
        logger.exception("Readiness check failed - PostgreSQL connection error")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not ready",
            "service": "rule-engine"
        }

if __name__ == "__main__":
    import uvicorn
    # Local dev binds exclusively to 127.0.0.1 loopback for network separation
    uvicorn.run("main:app", host="127.0.0.1", port=8000)
