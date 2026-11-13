"""Thin HTTP wrappers around the four Phase-1 services.

These are the "tools" the gather node uses. Every call is defensive: if a
service is down or slow, the wrapper returns an empty/None result instead of
raising, so the agent still produces an answer (just a thinner one). That's
what lets you demo the agent with only some services running.
"""
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


def search_wardrobe(user_id: str, query: str, top_k: int = 20) -> list[dict]:
    """Semantic search over the wardrobe (used when we have a text query)."""
    try:
        r = httpx.post(
            f"{config.WARDROBE_URL}/wardrobe/search",
            json={"user_id": user_id, "query": query, "top_k": top_k},
            timeout=config.HTTP_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("results", data.get("items", [])) if isinstance(data, dict) else data
    except (httpx.HTTPError, ValueError):
        return []


def fetch_weather(city: str | None, days: int = 1) -> dict | None:
    """Forecast + rule-based clothing needs for a city (None if unavailable)."""
    params: dict = {"days": max(1, min(days, 16))}
    if city:
        params["city"] = city
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


def ping(url: str) -> bool:
    """Is a service's /health reachable? (for the agent's own /health report)."""
    try:
        r = httpx.get(f"{url}/health", timeout=3)
        return r.status_code == 200
    except httpx.HTTPError:
        return False
