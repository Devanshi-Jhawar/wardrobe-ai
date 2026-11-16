from datetime import date, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import Feedback, Preferences, WearLog

settings = get_settings()


async def get_preferences(db: AsyncSession, user_id: str) -> Preferences | None:
    return await db.get(Preferences, user_id)


async def set_preferences(db: AsyncSession, user_id: str, changes: dict) -> Preferences:
    prefs = await db.get(Preferences, user_id)
    if prefs is None:
        prefs = Preferences(user_id=user_id, likes=[], dislikes=[])
        db.add(prefs)
    for key, value in changes.items():
        if key == "home_city":
            # A city name, or blank to clear it.
            prefs.home_city = (value or "").strip() or None
        elif value is not None:
            setattr(prefs, key, value)
    await db.commit()
    await db.refresh(prefs)
    return prefs


def avoid_days(prefs: Preferences | None) -> int:
    if prefs and prefs.avoid_repeat_days is not None:
        return prefs.avoid_repeat_days
    return settings.default_avoid_repeat_days


async def add_worn(db: AsyncSession, user_id: str, **fields) -> WearLog:
    entry = WearLog(user_id=user_id, **fields)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def worn_since(db: AsyncSession, user_id: str, since: date) -> list[WearLog]:
    stmt = (
        select(WearLog)
        .where(WearLog.user_id == user_id, WearLog.worn_on >= since)
        .order_by(WearLog.worn_on.desc(), WearLog.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def history(db: AsyncSession, user_id: str, limit: int, offset: int) -> tuple[int, list[WearLog]]:
    base = select(WearLog).where(WearLog.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(
            base.order_by(WearLog.worn_on.desc(), WearLog.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return total, list(rows)


async def delete_worn(db: AsyncSession, user_id: str, entry_id: str) -> bool:
    result = await db.execute(delete(WearLog).where(WearLog.id == entry_id, WearLog.user_id == user_id))
    await db.commit()
    return result.rowcount > 0


async def add_feedback(db: AsyncSession, user_id: str, **fields) -> Feedback:
    entry = Feedback(user_id=user_id, **fields)
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def item_opinions(db: AsyncSession, user_id: str) -> tuple[list[str], list[str]]:
    """Liked and disliked item ids. A newer opinion on the same item replaces an older one."""
    stmt = select(Feedback).where(Feedback.user_id == user_id).order_by(Feedback.created_at)
    latest: dict[str, bool] = {}
    for fb in (await db.execute(stmt)).scalars():
        for item_id in fb.item_ids:
            latest[item_id] = fb.liked
    liked = [i for i, v in latest.items() if v]
    disliked = [i for i, v in latest.items() if not v]
    return liked, disliked


def recent_item_ids(entries: list[WearLog]) -> list[str]:
    seen: list[str] = []
    for entry in entries:
        for item_id in entry.item_ids:
            if item_id not in seen:
                seen.append(item_id)
    return seen


def since_for(days: int) -> date:
    # avoid_repeat_days=3 on the 10th covers the 7th, 8th and 9th (and today).
    return date.today() - timedelta(days=days)
