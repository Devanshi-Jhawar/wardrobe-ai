from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import init_db
from .routers import items, search

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Wardrobe Service", version="0.1.0", lifespan=lifespan)
app.include_router(items.router)
app.include_router(search.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "enrichment": settings.enable_enrichment}
