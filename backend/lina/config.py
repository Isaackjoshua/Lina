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


@lru_cache
def get_settings() -> Settings:
    return Settings()
