from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PreferencesIn(BaseModel):
    likes: list[str] | None = None
    dislikes: list[str] | None = None
    avoid_repeat_days: int | None = Field(None, ge=0, le=60)
    # Empty string clears it.
    home_city: str | None = Field(None, max_length=120)


class PreferencesOut(BaseModel):
    likes: list[str]
    dislikes: list[str]
    avoid_repeat_days: int
    home_city: str | None = None


class WornIn(BaseModel):
    item_ids: list[str] = Field(..., min_length=1, description="Wardrobe item ids worn together")
    worn_on: date | None = Field(None, description="Defaults to today")
    occasion: str | None = None
    city: str | None = None
    note: str | None = None


class WornOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    worn_on: date
    item_ids: list[str]
    occasion: str | None
    city: str | None
    note: str | None
    created_at: datetime


class FeedbackIn(BaseModel):
    item_ids: list[str] = Field(..., min_length=1)
    liked: bool
    reason: str | None = None


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    item_ids: list[str]
    liked: bool
    reason: str | None
    created_at: datetime


class MemoryOut(BaseModel):
    """Everything the agents need in one call."""

    user_id: str
    preferences: PreferencesOut
    # Item ids worn within avoid_repeat_days: the critic shouldn't pick these.
    recently_worn_item_ids: list[str]
    # Ids from thumbs-up / thumbs-down feedback, most recent opinion wins.
    liked_item_ids: list[str]
    disliked_item_ids: list[str]
    recent_outfits: list[WornOut]


class HistoryOut(BaseModel):
    total: int
    outfits: list[WornOut]
