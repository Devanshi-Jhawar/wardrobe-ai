from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from .. import clients, crud
from ..config import get_settings
from ..db import get_db
from ..schemas import (
    FeedbackIn,
    FeedbackOut,
    HistoryOut,
    MemoryOut,
    PreferencesIn,
    PreferencesOut,
    WornIn,
    WornOut,
)

router = APIRouter(prefix="/memory", tags=["memory"])
settings = get_settings()


def _prefs_out(prefs) -> PreferencesOut:
    return PreferencesOut(
        likes=prefs.likes if prefs else [],
        dislikes=prefs.dislikes if prefs else [],
        avoid_repeat_days=crud.avoid_days(prefs),
    )


@router.get("/{user_id}", response_model=MemoryOut)
async def get_memory(
    user_id: str,
    recent_days: int = Query(14, ge=1, le=365, description="How far back recent_outfits goes"),
    db: AsyncSession = Depends(get_db),
):
    """Everything the agents read before choosing an outfit. Unknown users get empty memory."""
    prefs = await crud.get_preferences(db, user_id)
    avoid = crud.avoid_days(prefs)
    recent = await crud.worn_since(db, user_id, crud.since_for(max(recent_days, avoid)))
    cutoff = crud.since_for(avoid)
    liked, disliked = await crud.item_opinions(db, user_id)
    return MemoryOut(
        user_id=user_id,
        preferences=_prefs_out(prefs),
        recently_worn_item_ids=crud.recent_item_ids([e for e in recent if e.worn_on >= cutoff]),
        liked_item_ids=liked,
        disliked_item_ids=disliked,
        recent_outfits=[e for e in recent if e.worn_on >= crud.since_for(recent_days)],
    )


@router.get("/{user_id}/preferences", response_model=PreferencesOut)
async def get_preferences(user_id: str, db: AsyncSession = Depends(get_db)):
    return _prefs_out(await crud.get_preferences(db, user_id))


@router.put("/{user_id}/preferences", response_model=PreferencesOut)
async def set_preferences(user_id: str, payload: PreferencesIn, db: AsyncSession = Depends(get_db)):
    """Set likes / dislikes / avoid_repeat_days. Fields you leave out are kept."""
    prefs = await crud.set_preferences(db, user_id, payload.model_dump(exclude_unset=True))
    return _prefs_out(prefs)


@router.post("/{user_id}/worn", response_model=WornOut, status_code=201)
async def record_worn(user_id: str, payload: WornIn, db: AsyncSession = Depends(get_db)):
    """Record an outfit worn on a day (today if worn_on is left out)."""
    worn_on = payload.worn_on or date.today()
    if worn_on > date.today() + timedelta(days=1):
        raise HTTPException(status_code=400, detail="worn_on can't be in the future")
    entry = await crud.add_worn(
        db,
        user_id,
        worn_on=worn_on,
        item_ids=payload.item_ids,
        occasion=payload.occasion,
        city=payload.city,
        note=payload.note,
    )
    if settings.sync_wardrobe_wear:
        await clients.mark_worn_in_wardrobe(user_id, payload.item_ids)
    return entry


@router.get("/{user_id}/history", response_model=HistoryOut)
async def get_history(
    user_id: str,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    total, rows = await crud.history(db, user_id, limit, offset)
    return HistoryOut(total=total, outfits=rows)


@router.delete("/{user_id}/worn/{entry_id}", status_code=204)
async def delete_worn(user_id: str, entry_id: str, db: AsyncSession = Depends(get_db)):
    """Undo a wrong 'worn' entry."""
    if not await crud.delete_worn(db, user_id, entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")


@router.post("/{user_id}/feedback", response_model=FeedbackOut, status_code=201)
async def add_feedback(user_id: str, payload: FeedbackIn, db: AsyncSession = Depends(get_db)):
    """Thumbs up / down on an outfit or item, optionally with a reason ("too warm")."""
    return await crud.add_feedback(
        db, user_id, item_ids=payload.item_ids, liked=payload.liked, reason=payload.reason
    )
