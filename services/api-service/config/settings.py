import os
import sys
# Ensure the root of the service is in the path so azure_secrets can be found
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from azure_secrets import get_secret

class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str = Field(default_factory=lambda: get_secret("google-client-id"))
    GOOGLE_CLIENT_SECRET: str = Field(default_factory=lambda: get_secret("google-client-secret"))
    GOOGLE_REDIRECT_URI: str = Field(default="http://localhost/auth/callback")
    FRONTEND_URL: str = Field(default="http://localhost")
    GMAIL_SERVICE_URL: str = Field(default="http://gmail-service:8000")
    AI_SERVICE_URL: str = Field(default="http://ai-service:8000")
    RULE_ENGINE_SERVICE_URL: str = Field(default="http://rule-engine-service:8000")
    MEETING_SERVICE_URL: str = Field(default="http://meeting-service:8000")
    
    # Database configuration
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_USER: str = Field(default="postgres")
    DB_NAME: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default_factory=lambda: get_secret("postgres-password"))
    DB_SSL: str = Field(default="true")
    DB_AUTH_METHOD: str = Field(default="password") # "entra" or "password"
    
    # Redis configuration
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_PASSWORD: str = Field(default_factory=lambda: get_secret("redis-password"))
    REDIS_SSL: bool = Field(default=True)
    SESSION_SECRET: str = Field(default_factory=lambda: get_secret("session-secret"))
    
    # Azure Monitor OpenTelemetry config
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = Field(default="")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
