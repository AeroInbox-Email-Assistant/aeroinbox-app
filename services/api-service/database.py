import logging
import datetime
import asyncpg
from azure.identity import DefaultAzureCredential
from config.settings import settings

logger = logging.getLogger(__name__)

_POOL_AUTH_WARN = "Postgres Auth error encountered in api-service, refreshing pool..."

class PostgresPoolManager:
    def __init__(self):
        self.pool = None
        self.token_expiry = None

    def get_password(self) -> str:
        """
        Dynamically fetches an Entra ID access token if DB_AUTH_METHOD is set to "entra".
        Otherwise, returns the password from Key Vault / settings.
        """
        if settings.DB_AUTH_METHOD == "entra":
            try:
                # Fetch a short-lived token for PostgreSQL access
                credential = DefaultAzureCredential()
                token_obj = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
                # Parse expiration date
                self.token_expiry = datetime.datetime.fromtimestamp(token_obj.expires_on, datetime.timezone.utc)
                logger.info(f"Retrieved Entra ID token for api-service, expires at: {self.token_expiry}")
                return token_obj.token
            except Exception as e:
                logger.exception("Failed to fetch Entra ID token in api-service")
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
        logger.info("PostgreSQL connection pool initialized for api-service.")

    async def get_pool(self) -> asyncpg.Pool:
        # Refresh Entra ID token if it is close to expiring (within 5 minutes)
        if settings.DB_AUTH_METHOD == "entra" and self.token_expiry:
            now = datetime.datetime.now(datetime.timezone.utc)
            if (self.token_expiry - now).total_seconds() < 300:
                logger.info("Entra ID token close to expiry in api-service, recreating pool...")
                await self.close()
                await self.initialize_pool()

        if not self.pool:
            await self.initialize_pool()
        return self.pool

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("PostgreSQL connection pool closed in api-service.")

    async def execute(self, query: str, *args):
        pool = await self.get_pool()
        try:
            return await pool.execute(query, *args)
        except asyncpg.exceptions.InvalidAuthorizationSpecificationError:
            logger.warning(_POOL_AUTH_WARN)
            await self.close()
            pool = await self.get_pool()
            return await pool.execute(query, *args)

    async def fetch(self, query: str, *args):
        pool = await self.get_pool()
        try:
            return await pool.fetch(query, *args)
        except asyncpg.exceptions.InvalidAuthorizationSpecificationError:
            logger.warning(_POOL_AUTH_WARN)
            await self.close()
            pool = await self.get_pool()
            return await pool.fetch(query, *args)

    async def fetchrow(self, query: str, *args):
        pool = await self.get_pool()
        try:
            return await pool.fetchrow(query, *args)
        except asyncpg.exceptions.InvalidAuthorizationSpecificationError:
            logger.warning(_POOL_AUTH_WARN)
            await self.close()
            pool = await self.get_pool()
            return await pool.fetchrow(query, *args)

    async def fetchval(self, query: str, *args):
        pool = await self.get_pool()
        try:
            return await pool.fetchval(query, *args)
        except asyncpg.exceptions.InvalidAuthorizationSpecificationError:
            logger.warning(_POOL_AUTH_WARN)
            await self.close()
            pool = await self.get_pool()
            return await pool.fetchval(query, *args)

db = PostgresPoolManager()

async def initialize_db():
    """
    Creates the prioritized_emails cache table and indexes if they do not exist.
    """
    query_table = """
        CREATE TABLE IF NOT EXISTS prioritized_emails (
            email_id VARCHAR(255) PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            rule_score INT NOT NULL,
            matched_rules JSONB DEFAULT '[]'::jsonb,
            ai_summary TEXT,
            ai_priority VARCHAR(50),
            ai_reply TEXT,
            is_spam_false_positive BOOLEAN DEFAULT FALSE,
            spam_analysis_reason TEXT,
            is_meeting_request BOOLEAN DEFAULT FALSE,
            has_deadline BOOLEAN DEFAULT FALSE,
            deadline_date VARCHAR(100),
            final_priority VARCHAR(50) NOT NULL,
            final_score INT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """
    await db.execute(query_table)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_prioritized_emails_user ON prioritized_emails(user_id);")
    await db.execute("ALTER TABLE prioritized_emails ADD COLUMN IF NOT EXISTS action_items JSONB DEFAULT '[]'::jsonb;")

    query_tasks = """
        CREATE TABLE IF NOT EXISTS user_tasks (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            task_source VARCHAR(50) NOT NULL, -- 'manual', 'email_action_item', 'email_no_reply'
            email_id VARCHAR(255),            -- Linked email message ID (if any)
            title TEXT NOT NULL,
            description TEXT,
            due_date TIMESTAMP WITH TIME ZONE,
            status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'completed', 'dismissed'
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """
    await db.execute(query_tasks)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_user ON user_tasks(user_id);")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_email ON user_tasks(email_id);")

    query_settings = """
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id VARCHAR(255) PRIMARY KEY,
            reminder_interval_hours INT DEFAULT 2, -- Default 2 hours
            last_reminder_sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """
    await db.execute(query_settings)

    logger.info("Database prioritized_emails, user_tasks, and user_settings tables and indexes initialized.")
