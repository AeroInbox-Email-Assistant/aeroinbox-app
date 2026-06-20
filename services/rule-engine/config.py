import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from azure_secrets import get_secret

class Settings(BaseSettings):
    DB_HOST: str = Field(default="localhost")
    DB_PORT: int = Field(default=5432)
    DB_USER: str = Field(default="postgres")
    DB_NAME: str = Field(default="postgres")
    DB_PASSWORD: str = Field(default_factory=lambda: get_secret("postgres-password"))
    DB_SSL: str = Field(default="true")
    DB_AUTH_METHOD: str = Field(default="password") # "entra" or "password"
    
    # Azure Monitor OpenTelemetry config
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = Field(default="")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
