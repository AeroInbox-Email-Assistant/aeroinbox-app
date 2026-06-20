import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from azure_secrets import get_secret

class Settings(BaseSettings):
    GOOGLE_CLIENT_ID: str = Field(default_factory=lambda: get_secret("google-client-id"))
    GOOGLE_CLIENT_SECRET: str = Field(default_factory=lambda: get_secret("google-client-secret"))
    
    # Azure Monitor OpenTelemetry config
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = Field(default="")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
