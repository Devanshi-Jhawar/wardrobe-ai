import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Preferences(Base):
    """What a user likes and dislikes. One row per user."""

    __tablename__ = "preferences"

    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # Plain words matched against item fields (category, color, style, pattern, material),
    # e.g. likes=["blue", "Kurti", "ethnic"], dislikes=["yellow", "Blazer"].
    likes: Mapped[list] = mapped_column(JSON, default=list)
    dislikes: Mapped[list] = mapped_column(JSON, default=list)
    avoid_repeat_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class WearLog(Base):
    """One outfit worn on one day."""

    __tablename__ = "wear_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    worn_on: Mapped[date] = mapped_column(Date, index=True)
    item_ids: Mapped[list] = mapped_column(JSON)  # wardrobe item ids
    occasion: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Feedback(Base):
    """A thumbs up/down on an outfit (or single item) the agents suggested."""

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    item_ids: Mapped[list] = mapped_column(JSON)
    liked: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "too warm"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
