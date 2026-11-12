from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import get_settings
from .db import init_db
from .routers import memory

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Memory Service", version="0.1.0", lifespan=lifespan)
app.include_router(memory.router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "sync_wardrobe_wear": settings.sync_wardrobe_wear}
