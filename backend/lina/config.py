"""Runtime settings, read from environment variables (see /.env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Local runs read the repo-root .env; containers get real env vars from Compose.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str = "postgresql+psycopg://lina:lina@localhost:5433/lina"
    # Shared secret the Next.js server sends to /internal/* routes. Empty = deny all.
    internal_api_token: str = ""
    timezone: str = "Africa/Dar_es_Salaam"
    default_locale: str = "sw"
    log_level: str = "INFO"

    # --- Fetching (SPEC §2 "fetch politely", §6.2) ---
    bot_name: str = "LINA-bot"
    # Public page describing the bot and how to reach us. Fetching refuses to run without it.
    bot_contact_url: str = ""
    fetch_delay_seconds: float = 5.0  # minimum gap between two requests to the same site
    fetch_timeout_seconds: float = 20.0
    max_items_per_run: int = 60
    max_items_per_source: int = 10
    sources_file: str = "sources.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
