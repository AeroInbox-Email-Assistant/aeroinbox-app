import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from azure_secrets import get_secret

class Settings(BaseSettings):
    AI_PROVIDER: str = Field(default="gemini")
    
    # Gemini
    GEMINI_API_KEY: str = Field(default_factory=lambda: get_secret("gemini-api-key"))
    
    # Azure AI Foundry
    AZURE_AI_FOUNDRY_API_KEY: str = Field(default_factory=lambda: get_secret("azure-ai-foundry-api-key"))
    AZURE_AI_FOUNDRY_ENDPOINT: str = Field(default="")
    AZURE_AI_FOUNDRY_MODEL: str = Field(default="gpt-4.1-mini")
    AZURE_AI_FOUNDRY_API_VERSION: str = Field(default="2024-05-01-preview")
    
    # Azure OpenAI
    AZURE_OPENAI_API_KEY: str = Field(default_factory=lambda: get_secret("azure-openai-key"))
    AZURE_OPENAI_ENDPOINT: str = Field(default="")
    AZURE_OPENAI_DEPLOYMENT_NAME: str = Field(default="gpt-4o-mini")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-02-15-preview")
    
    # OpenAI
    OPENAI_API_KEY: str = Field(default_factory=lambda: get_secret("openai-api-key"))
    OPENAI_API_BASE: str = Field(default="https://api.openai.com/v1")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini")
    
    # Azure Monitor OpenTelemetry config
    APPLICATIONINSIGHTS_CONNECTION_STRING: str = Field(default="")

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(__file__), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
