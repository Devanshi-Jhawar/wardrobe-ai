from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./wardrobe.db"
    storage_dir: Path = Path("./storage")

    # Enrichment (vision + embedding). Off until those services exist.
    enable_enrichment: bool = False
    vision_service_url: str = "http://localhost:8002"
    embedding_service_url: str = "http://localhost:8003"

    # Upload guards
    max_image_bytes: int = 10 * 1024 * 1024  # 10 MB
    thumbnail_size: int = 256


@lru_cache
def get_settings() -> Settings:
    return Settings()
