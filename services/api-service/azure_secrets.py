import os
from functools import lru_cache
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

@lru_cache(maxsize=128)
def get_secret(secret_name: str) -> str:
    """
    Retrieves secret from Azure Key Vault with LRU caching.
    Falls back to environment variables for local development.
    """
    vault_url = os.getenv("AZURE_KEYVAULT_URL") or os.getenv("AZURE_KEY_VAULT_URI")
    if vault_url:
        try:
            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=vault_url, credential=credential)
            secret = client.get_secret(secret_name)
            if secret and secret.value:
                return secret.value
        except Exception:
            pass

    # Try environment variable fallback (e.g. google-client-id -> GOOGLE_CLIENT_ID)
    env_name = secret_name.upper().replace("-", "_")
    env_val = os.getenv(env_name)
    if env_val:
        return env_val

    return ""
