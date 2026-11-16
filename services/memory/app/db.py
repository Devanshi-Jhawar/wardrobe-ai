from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    # Fine for phase-1 dev. Switch to Alembic migrations before Postgres.
    from . import models  # noqa: F401  (ensure models are registered)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)


def _add_missing_columns(conn) -> None:
    """create_all makes new tables but never alters existing ones; add columns
    introduced after a database was first created (until Alembic is set up)."""
    from sqlalchemy import inspect, text

    have = {c["name"] for c in inspect(conn).get_columns("preferences")}
    if "home_city" not in have:
        conn.execute(text("ALTER TABLE preferences ADD COLUMN home_city VARCHAR(120)"))
