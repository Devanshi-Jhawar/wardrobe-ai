import math

from fastapi import APIRouter, Depends
from sqlalchemy import Float, bindparam, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud
from ..config import get_settings
from ..db import get_db
from ..models import WardrobeItem
from ..schemas import SearchHit, SearchRequest, SearchResponse

router = APIRouter(prefix="/wardrobe", tags=["search"])
settings = get_settings()


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return -1.0
    return dot / (na * nb)


def _keep(item: WardrobeItem, req: SearchRequest) -> bool:
    """category / occasion / season filters (occasion and season are lists)."""
    if req.category and item.category != req.category:
        return False
    if req.occasion and not (item.occasion and req.occasion in item.occasion):
        return False
    if req.season and not (item.season and req.season in item.season):
        return False
    return True


async def _search_pgvector(db: AsyncSession, req: SearchRequest) -> list[tuple[WardrobeItem, float]]:
    """Postgres: pgvector's cosine distance operator (<=>), ordered in the database."""
    from pgvector.sqlalchemy import Vector

    if len(req.embedding) != settings.embedding_dim:
        return []
    q = bindparam("q", value=req.embedding, type_=Vector(settings.embedding_dim))
    distance = WardrobeItem.embedding.op("<=>", return_type=Float)(q)
    stmt = (select(WardrobeItem, distance.label("distance"))
            .where(WardrobeItem.user_id == req.user_id,
                   WardrobeItem.deleted_at.is_(None),
                   WardrobeItem.embedding.is_not(None))
            .order_by(distance))
    if req.category:
        stmt = stmt.where(WardrobeItem.category == req.category)
    rows = (await db.execute(stmt)).all()
    # Filters on JSON lists run in Python, then cut to k.
    return [(item, 1.0 - float(d)) for item, d in rows if _keep(item, req)][: req.k]


async def _search_python(db: AsyncSession, req: SearchRequest) -> list[tuple[WardrobeItem, float]]:
    """SQLite: brute-force cosine (fine for a personal wardrobe)."""
    candidates = [c for c in await crud.items_with_embeddings(db, req.user_id) if _keep(c, req)]
    scored = [(c, _cosine(req.embedding, c.embedding or [])) for c in candidates]
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[: req.k]


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Nearest-neighbour search over stored embeddings (score = cosine similarity)."""
    if db.bind.dialect.name == "postgresql":
        scored = await _search_pgvector(db, req)
    else:
        scored = await _search_python(db, req)
    return SearchResponse(hits=[SearchHit(item=c, score=s) for c, s in scored])
