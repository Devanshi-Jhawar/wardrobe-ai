import math

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .. import crud
from ..db import get_db
from ..schemas import SearchHit, SearchRequest, SearchResponse

router = APIRouter(prefix="/wardrobe", tags=["search"])


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return -1.0
    return dot / (na * nb)


@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Nearest-neighbour search over stored embeddings.

    Phase 1: brute-force cosine in Python (fine for a personal wardrobe).
    Later, on Postgres + pgvector, replace with `ORDER BY embedding <=> :q`.
    """
    candidates = await crud.items_with_embeddings(db, req.user_id)

    if req.category:
        candidates = [c for c in candidates if c.category == req.category]
    if req.occasion:
        candidates = [c for c in candidates if c.occasion and req.occasion in c.occasion]
    if req.season:
        candidates = [c for c in candidates if c.season and req.season in c.season]

    scored = [(c, _cosine(req.embedding, c.embedding or [])) for c in candidates]
    scored.sort(key=lambda t: t[1], reverse=True)

    hits = [SearchHit(item=c, score=s) for c, s in scored[: req.k]]
    return SearchResponse(hits=hits)
