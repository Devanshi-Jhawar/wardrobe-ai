"""Node 2: gather — collect everything the agent needs to decide.

This is the node that actually *uses the other services*. It reads the
structured request the planner produced and fills the State with:
  - wardrobe_items : the user's clothes            (wardrobe service)
  - weather        : forecast + clothing needs     (weather service)
  - prefs          : remembered dislikes/notes      (local memory store)

It makes no decisions — it only fetches. If a service is down, its field
comes back empty and the downstream nodes cope.
"""
from .. import clients
from .. import memory_store
from ..state import OutfitState


def _days_from_dates(dates: dict) -> int:
    if not dates:
        return 1
    if "count" in dates:
        return int(dates["count"])
    # A single relative day ("tomorrow", "saturday") is a one-day horizon.
    return 1


def gather(state: OutfitState) -> dict:
    user_id = state.get("user_id") or "demo"
    query = state.get("query") or ""
    city = state.get("city")
    days = _days_from_dates(state.get("dates") or {})

    # Wardrobe: prefer semantic search when there's a descriptive query,
    # otherwise just list everything the user owns.
    items = clients.search_wardrobe(user_id, query) if query else []
    if not items:
        items = clients.fetch_wardrobe(user_id)

    weather = clients.fetch_weather(city, days=days)
    prefs = memory_store.get_prefs(user_id)

    return {
        "wardrobe_items": items,
        "weather": weather,
        "prefs": prefs,
    }
