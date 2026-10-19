import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class WardrobeItem(Base):
    __tablename__ = "wardrobe_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)

    image_url: Mapped[str] = mapped_column(String)
    thumbnail_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Filled by the VISION service (null until enrichment runs).
    category: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    color: Mapped[list | None] = mapped_column(JSON, nullable=True)
    pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    material: Mapped[str | None] = mapped_column(String, nullable=True)
    style: Mapped[str | None] = mapped_column(String, nullable=True)
    occasion: Mapped[list | None] = mapped_column(JSON, nullable=True)
    season: Mapped[list | None] = mapped_column(JSON, nullable=True)
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Filled by the EMBEDDING service. JSON list for now; migrate to pgvector later.
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # pending  -> uploaded, not yet enriched
    # ready    -> enrichment complete (or enrichment disabled + manual attrs)
    # failed   -> enrichment attempted and errored
    status: Mapped[str] = mapped_column(String, default="pending", index=True)

    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    wear_count: Mapped[int] = mapped_column(Integer, default=0)
    last_worn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
