"""Thin HTTP wrappers around the Phase-1 services (wardrobe, weather, memory).

These are the "tools" the gather node uses. Every call is defensive: if a
service is down or slow, the wrapper returns an empty/None result instead of
raising, so the agent still produces an answer (just a thinner one). That's
what lets you demo the agent with only some services running.
"""
from datetime import date

import httpx

from . import config


def fetch_wardrobe(user_id: str, limit: int = 200) -> list[dict]:
    """All of a user's ready wardrobe items (category, color, occasion, ...)."""
    try:
        r = httpx.get(
            f"{config.WARDROBE_URL}/wardrobe/items",
            params={"user_id": user_id, "limit": limit},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        # Accept either a bare list or {"items": [...]}.
        return data.get("items", data) if isinstance(data, dict) else data
    except (httpx.HTTPError, ValueError):
        return []


def embed_text(text: str) -> list[float] | None:
    """Text -> vector via the embedding service, in the same space as item photos.

    Only the `clip` backend can embed text; the default `color` backend answers
    501, and then (or if the service is down) this returns None and the agent
    simply ranks without search.
    """
    if not text.strip():
        return None
    try:
        r = httpx.post(f"{config.EMBED_URL}/embed/text", json={"text": text},
                       timeout=config.EMBED_TIMEOUT)
        r.raise_for_status()
        vec = r.json().get("embedding")
        return vec if isinstance(vec, list) and vec else None
    except (httpx.HTTPError, ValueError):
        return None


def search_wardrobe(user_id: str, embedding: list[float], k: int = 200) -> dict[str, float]:
    """Nearest-neighbour search over the user's item photos.

    Returns {item_id: cosine score}. Only items that have a stored embedding
    appear. Empty dict if the wardrobe is down or nothing matches.
    """
    try:
        r = httpx.post(
            f"{config.WARDROBE_URL}/wardrobe/search",
            json={"user_id": user_id, "embedding": embedding, "k": k},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        hits = r.json().get("hits") or []
        return {h["item"]["id"]: float(h["score"]) for h in hits
                if isinstance(h, dict) and (h.get("item") or {}).get("id")}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {}


def fetch_weather(city: str | None, days: int = 1, start_date: date | None = None) -> dict | None:
    """Forecast + rule-based clothing needs for a city (None if unavailable).

    `start_date` is the first day asked about (e.g. tomorrow); default today.
    """
    params: dict = {"days": max(1, min(days, 16))}
    if city:
        params["city"] = city
    if start_date:
        params["start_date"] = start_date.isoformat()
    try:
        r = httpx.get(
            f"{config.WEATHER_URL}/weather",
            params=params,
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def fetch_memory(user_id: str) -> dict | None:
    """Everything the memory service knows about a user (None if it's down)."""
    try:
        r = httpx.get(f"{config.MEMORY_URL}/memory/{user_id}", timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def add_dislike(user_id: str, thing: str) -> dict | None:
    """Append a dislike word to the user's preferences in the memory service.

    Returns the saved preferences, or None if the memory service is down.
    Idempotent: a word already remembered isn't added twice.
    """
    thing = (thing or "").strip().lower()
    try:
        r = httpx.get(f"{config.MEMORY_URL}/memory/{user_id}/preferences",
                      timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        dislikes = [d.lower() for d in r.json().get("dislikes") or []]
        if thing and thing not in dislikes:
            dislikes.append(thing)
        r = httpx.put(f"{config.MEMORY_URL}/memory/{user_id}/preferences",
                      json={"dislikes": dislikes}, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def ping(url: str) -> bool:
    """Is a service's /health reachable? (for the agent's own /health report)."""
    try:
        r = httpx.get(f"{url}/health", timeout=3)
        return r.status_code == 200
    except httpx.HTTPError:
        return False
