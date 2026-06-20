import redis.asyncio as aioredis
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self):
        self.client = None

    async def initialize(self):
        logger.info(f"Initializing Redis connection to {settings.REDIS_HOST}:{settings.REDIS_PORT}...")
        
        schema = "rediss" if settings.REDIS_SSL else "redis"
        
        if settings.REDIS_PASSWORD:
            url = f"{schema}://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
        else:
            url = f"{schema}://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0"
            
        kwargs = {
            "max_connections": 20,
            "decode_responses": True
        }
        if settings.REDIS_SSL:
            kwargs["ssl_cert_reqs"] = None

        self.client = aioredis.from_url(url, **kwargs)
        logger.info("Redis connection pool initialized.")

    async def get_client(self) -> aioredis.Redis:
        if not self.client:
            await self.initialize()
        return self.client

    async def close(self):
        if self.client:
            try:
                await self.client.aclose()
            except Exception as e:
                logger.error(f"Error closing Redis client: {str(e)}")
            self.client = None
            logger.info("Redis connection pool closed.")

redis_manager = RedisManager()
