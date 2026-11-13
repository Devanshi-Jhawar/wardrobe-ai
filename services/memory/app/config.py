from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./memory.db"

    # Items worn within this many days count as "recently worn" (agents avoid them).
    default_avoid_repeat_days: int = 3

    # Mirror each worn outfit into the wardrobe's wear count. Off so memory runs on its own.
    sync_wardrobe_wear: bool = False
    wardrobe_service_url: str = "http://localhost:8001"


@lru_cache
def get_settings() -> Settings:
    return Settings()
