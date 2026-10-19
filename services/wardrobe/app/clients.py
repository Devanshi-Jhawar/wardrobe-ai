"""HTTP clients for the vision + embedding services.

These are the seams for phase-1 enrichment. Until ENABLE_ENRICHMENT=true and the
services exist, upload simply skips them and stores the item as `pending`.
"""
import httpx

from .config import get_settings

settings = get_settings()


async def analyze_image(raw: bytes, filename: str = "item.png") -> dict:
    """Call the vision service → garment attributes."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.vision_service_url}/analyze",
            files={"file": (filename, raw, "image/png")},
        )
        resp.raise_for_status()
        return resp.json()  # {category, color, pattern, material, style, occasion, season, ...}


async def embed_image(raw: bytes, filename: str = "item.png") -> list[float]:
    """Call the embedding service → vector."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.embedding_service_url}/embed",
            files={"file": (filename, raw, "image/png")},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]
