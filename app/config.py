from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Comma-separated accepted API keys. Empty means auth is disabled (dev mode).
    api_keys: str = ""

    # Upstream fetch timeout in seconds; spec says 503 after 90s.
    request_timeout: float = 90.0

    # Base URL used when building html_url / json_url in search_metadata.
    public_base_url: str = "http://localhost:8000"

    # Max recent searches kept in memory for /searches/{id} replay.
    search_store_size: int = 100

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
