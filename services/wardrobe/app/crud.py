from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import WardrobeItem


async def create_item(db: AsyncSession, **fields) -> WardrobeItem:
    item = WardrobeItem(**fields)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def get_item(db: AsyncSession, item_id: str, user_id: str) -> WardrobeItem | None:
    stmt = select(WardrobeItem).where(
        WardrobeItem.id == item_id,
        WardrobeItem.user_id == user_id,
        WardrobeItem.deleted_at.is_(None),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_items(
    db: AsyncSession,
    user_id: str,
    *,
    category: str | None = None,
    occasion: str | None = None,
    season: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[int, list[WardrobeItem]]:
    conds = [WardrobeItem.user_id == user_id, WardrobeItem.deleted_at.is_(None)]
    if category:
        conds.append(WardrobeItem.category == category)

    base = select(WardrobeItem).where(*conds)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    rows = (
        await db.execute(base.order_by(WardrobeItem.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()

    # occasion/season are JSON lists -> filter in Python (portable across SQLite/PG).
    if occasion:
        rows = [r for r in rows if r.occasion and occasion in r.occasion]
    if season:
        rows = [r for r in rows if r.season and season in r.season]

    return total, list(rows)


async def update_item(db: AsyncSession, item: WardrobeItem, changes: dict) -> WardrobeItem:
    for key, value in changes.items():
        if value is not None:
            setattr(item, key, value)
    await db.commit()
    await db.refresh(item)
    return item


async def soft_delete(db: AsyncSession, item: WardrobeItem) -> None:
    item.deleted_at = datetime.now(timezone.utc)
    await db.commit()


async def mark_worn(db: AsyncSession, item: WardrobeItem) -> WardrobeItem:
    item.wear_count += 1
    item.last_worn_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(item)
    return item


async def items_with_embeddings(db: AsyncSession, user_id: str) -> list[WardrobeItem]:
    stmt = select(WardrobeItem).where(
        WardrobeItem.user_id == user_id,
        WardrobeItem.deleted_at.is_(None),
        WardrobeItem.embedding.is_not(None),
    )
    return list((await db.execute(stmt)).scalars().all())
