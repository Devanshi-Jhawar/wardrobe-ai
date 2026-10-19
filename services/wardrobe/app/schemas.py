from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- Attributes the vision service produces (also accepted manually) ----
class ItemAttributes(BaseModel):
    category: str | None = None
    color: list[str] | None = None
    pattern: str | None = None
    material: str | None = None
    style: str | None = None
    occasion: list[str] | None = None
    season: list[str] | None = None
    attributes: dict | None = None


class ItemUpdate(ItemAttributes):
    is_favorite: bool | None = None


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    image_url: str
    thumbnail_url: str | None

    category: str | None
    color: list[str] | None
    pattern: str | None
    material: str | None
    style: str | None
    occasion: list[str] | None
    season: list[str] | None
    attributes: dict | None

    status: str
    is_favorite: bool
    wear_count: int
    last_worn_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ItemList(BaseModel):
    total: int
    items: list[ItemOut]


class SearchRequest(BaseModel):
    user_id: str
    embedding: list[float] = Field(..., description="Query vector from the embedding service")
    k: int = 10
    category: str | None = None
    occasion: str | None = None
    season: str | None = None


class SearchHit(BaseModel):
    item: ItemOut
    score: float


class SearchResponse(BaseModel):
    hits: list[SearchHit]
