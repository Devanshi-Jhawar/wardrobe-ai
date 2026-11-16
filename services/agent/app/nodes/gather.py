"""Node 2: gather — collect everything the agent needs to decide.

This is the node that actually *uses the other services*. It reads the
structured request the planner produced and fills the State with:
  - wardrobe_items : the user's clothes                     (wardrobe service)
  - search_scores  : how well each item matches the request (embedding + wardrobe search)
  - weather        : forecast + clothing needs for the days (weather service)
  - prefs          : likes, dislikes, feedback, recent wears (memory service)

It makes no decisions — it only fetches. If a service is down, its field
comes back empty and the downstream nodes cope.
"""
from datetime import date, timedelta

from .. import clients, prefs as prefs_mod
from ..state import OutfitState

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MAX_FORECAST_DAYS = 16   # the weather service (Open-Meteo) only looks this far ahead


def date_window(dates: dict, today: date | None = None) -> tuple[date, int]:
    """(first day, number of days) the request is about.

    {"count": 4}             -> today, 4 days (a trip starting now)
    {"relative": "tomorrow"} -> tomorrow, 1 day
    {"relative": "saturday"} -> the next Saturday (today if it is Saturday), 1 day
    "this weekend"           -> the coming Sat+Sun (just Sunday if today is Sunday)
    "next weekend"           -> the weekend after that
    "this week"              -> today through Sunday
    "next week"              -> next Monday through Sunday
    anything else            -> today, 1 day

    A count can combine with a start: {"count": 4, "relative": "saturday"} or
    {"count": 4, "start": "2026-12-20"} is 4 days from that day.
    """
    today = today or date.today()
    if not dates:
        return today, 1
    if "count" in dates:
        count = max(1, int(dates["count"]))
        rest = {k: v for k, v in dates.items() if k != "count"}
        return (date_window(rest, today)[0] if rest else today), count
    if dates.get("start"):
        try:
            return max(date.fromisoformat(dates["start"]), today), 1
        except ValueError:
            return today, 1

    rel = dates.get("relative")
    if rel == "tomorrow":
        return today + timedelta(days=1), 1
    if rel in WEEKDAYS:
        ahead = (WEEKDAYS.index(rel) - today.weekday()) % 7
        return today + timedelta(days=ahead), 1
    if rel in ("this weekend", "next weekend"):
        if today.weekday() == 6:                      # Sunday: this weekend is today
            start, days = today, 1
        else:
            start, days = today + timedelta(days=(5 - today.weekday()) % 7), 2
        if rel == "next weekend":
            start = (start if days == 2 else today - timedelta(days=1)) + timedelta(days=7)
            days = 2
        return start, days
    if rel == "this week":
        return today, 7 - today.weekday()
    if rel == "next week":
        return today + timedelta(days=7 - today.weekday()), 7
    return today, 1                                   # today / tonight / unknown


def _clip_to_forecast(start: date, days: int, today: date) -> tuple[date, int]:
    """Keep the window inside what the weather service can forecast."""
    last = today + timedelta(days=MAX_FORECAST_DAYS - 1)
    if start > last:
        return start, 0                               # too far ahead: no forecast
    end = min(start + timedelta(days=days - 1), last)
    return start, (end - start).days + 1


def gather(state: OutfitState) -> dict:
    user_id = state.get("user_id") or "demo"
    search_text = state.get("search_text")
    city = state.get("city")

    today = date.today()
    start, days = _clip_to_forecast(*date_window(state.get("dates") or {}, today), today)

    # Wardrobe: always the full list, so every slot has candidates.
    items = clients.fetch_wardrobe(user_id)

    # Semantic search ranks those items against what the user said about the
    # clothes ("red saree"; the planner strips occasion/city/date/filler words,
    # so a generic question doesn't search at all). It only boosts scores — it
    # never hides items. Needs the CLIP backend; with the default color
    # backend embed_text() is None and we skip it.
    search_scores: dict[str, float] = {}
    if search_text and items:
        vec = clients.embed_text(search_text)
        if vec:
            search_scores = clients.search_wardrobe(user_id, vec, k=len(items))

    prefs = prefs_mod.from_memory(clients.fetch_memory(user_id))

    # Weather needs a place: the one asked about, else the user's home city.
    # With neither, skip it rather than let the weather service fall back to
    # its built-in default location and report a stranger's temperature.
    weather_source = "asked" if city else "home" if prefs.get("home_city") else None
    city = city or prefs.get("home_city")
    weather = clients.fetch_weather(city, days=days, start_date=start) if days and city else None

    return {
        "wardrobe_items": items,
        "search_scores": search_scores,
        "weather": weather,
        "weather_source": weather_source,
        "prefs": prefs,
    }
