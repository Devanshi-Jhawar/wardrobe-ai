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


def save_preferences(user_id: str, things: list[str], kind: str = "dislike") -> dict | None:
    """Add like / dislike words to the user's preferences in the memory service.

    Liking something removes it from dislikes and vice versa, so the latest
    statement wins ("I don't like blue" ... later "I love blue").
    Returns the saved preferences, or None if the memory service is down.
    Idempotent: a word already remembered isn't added twice.
    """
    things = [t.strip().lower() for t in things if t and t.strip()]
    add_to, remove_from = ("likes", "dislikes") if kind == "like" else ("dislikes", "likes")
    try:
        r = httpx.get(f"{config.MEMORY_URL}/memory/{user_id}/preferences",
                      timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        current = r.json()
        target = [x.lower() for x in current.get(add_to) or []]
        other = [x.lower() for x in current.get(remove_from) or []]
        for t in things:
            if t not in target:
                target.append(t)
        other = [x for x in other if x not in things]
        r = httpx.put(f"{config.MEMORY_URL}/memory/{user_id}/preferences",
                      json={add_to: target, remove_from: other}, timeout=config.HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except (httpx.HTTPError, ValueError):
        return None


def add_dislike(user_id: str, thing: str) -> dict | None:
    """Remember one dislike word (kept for callers that only dislike)."""
    return save_preferences(user_id, [thing], "dislike")


def record_worn(user_id: str, item_ids: list[str], worn_on: date | None = None,
                occasion: str | None = None, city: str | None = None,
                note: str | None = None) -> dict | None:
    """Log an outfit as worn in the memory service (feeds "don't repeat").

    Returns the saved entry, None if memory is down, or raises ValueError with
    the service's message if it refused the entry (e.g. a future date).
    """
    body = {"item_ids": item_ids, "occasion": occasion, "city": city, "note": note}
    if worn_on:
        body["worn_on"] = worn_on.isoformat()
    try:
        r = httpx.post(f"{config.MEMORY_URL}/memory/{user_id}/worn", json=body,
                       timeout=config.HTTP_TIMEOUT)
    except httpx.HTTPError:
        return None
    if 400 <= r.status_code < 500:
        raise ValueError(r.json().get("detail", "rejected by memory service"))
    if r.status_code >= 500:
        return None
    return r.json()


def rate_items(user_id: str, item_ids: list[str], liked: bool,
               reason: str | None = None) -> dict | None:
    """Thumbs up / down on items or a whole outfit (memory's /feedback)."""
    try:
        r = httpx.post(f"{config.MEMORY_URL}/memory/{user_id}/feedback",
                       json={"item_ids": item_ids, "liked": liked, "reason": reason},
                       timeout=config.HTTP_TIMEOUT)
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
