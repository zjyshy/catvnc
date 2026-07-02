from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="CATVNC_",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"

    session_secret: str = "change-me"
    database_url: str = "sqlite+aiosqlite:///./catvnc.db"

    upstream_host: str = "127.0.0.1"

    turn_host: str = "39.106.125.238"
    turn_port: int = 3478
    turn_shared_secret: str = "change-me"
    turn_ttl_seconds: int = 300

    stun_urls: str = "stun:stun.l.google.com:19302"


@lru_cache
def get_settings() -> Settings:
    return Settings()
