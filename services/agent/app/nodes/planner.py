"""Node 1: planner — understands the request.

Turns a free-form sentence into structured fields (intent, occasion, city,
dates) the rest of the agent can act on. It only *interprets* — it fetches
nothing and recommends nothing.

This is the "rules" implementation: fast, no API key, handles the common
phrasings. The harder, messier cases are what an LLM mode will cover later;
the function signature stays the same so swapping it in changes nothing
downstream.
"""
import re

from ..state import OutfitState

# Occasion -> the words that hint at it (checked in this order).
OCCASION_KEYWORDS = {
    "office":   ["office", "work", "meeting", "interview", "client"],
    "wedding":  ["wedding", "shaadi", "reception", "sangeet"],
    "festival": ["festival", "festive", "diwali", "pooja", "puja", "eid", "navratri"],
    "party":    ["party", "club", "night out", "cocktail"],
    "gym":      ["gym", "workout", "exercise", "running"],
    "date":     ["date night", "date"],
    "casual":   ["casual", "hangout", "chill", "brunch", "outing", "day out"],
}

# Phrases that flip the whole request into a different intent.
PREF_TRIGGERS = ["don't like", "dont like", "do not like", "dislike", "hate",
                 "not a fan of", "i avoid", "never wear", "don't wear", "dont wear"]
TRIP_TRIGGERS = ["trip", "travel", "traveling", "travelling", "vacation",
                 "holiday", "visiting", "packing", "pack for"]
GAP_TRIGGERS = ["should i buy", "what to buy", "need to buy", "shopping",
                "what am i missing", "missing", "buy for", "add to my wardrobe"]

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _detect_intent(q: str) -> str:
    if any(t in q for t in PREF_TRIGGERS):
        return "save_preference"
    if any(t in q for t in GAP_TRIGGERS):
        return "gap"
    if any(t in q for t in TRIP_TRIGGERS) or re.search(r"\b\d+\s*-?\s*day", q):
        return "trip"
    return "recommend"


def _detect_occasion(q: str) -> str | None:
    for occasion, words in OCCASION_KEYWORDS.items():
        if any(w in q for w in words):
            return occasion
    return None


def _detect_dates(q: str) -> dict:
    m = re.search(r"(\d+)\s*-?\s*day", q)       # "4-day", "4 day", "4 days"
    if m:
        return {"count": int(m.group(1))}
    for rel in ["today", "tonight", "tomorrow", "this weekend", "next weekend",
                "this week", "next week"]:
        if rel in q:
            return {"relative": rel}
    for day in WEEKDAYS:
        if day in q:
            return {"relative": day}
    return {}


def _detect_city(q_raw: str) -> str | None:
    # Heuristic: a capitalised word after a travel preposition, or "<City> trip".
    patterns = [
        r"\b(?:in|to|at|for|visiting|visit)\s+([A-Z][a-zA-Z]+)",
        r"\b([A-Z][a-zA-Z]+)\s+trip\b",
        r"\btrip\s+to\s+([A-Z][a-zA-Z]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, q_raw)
        if m:
            cand = m.group(1).strip()
            if cand.lower() not in WEEKDAYS + ["i", "what", "office", "work"]:
                return cand
    return None


def _extract_preference(q_raw: str, q: str) -> str | None:
    for t in PREF_TRIGGERS:
        idx = q.find(t)
        if idx != -1:
            tail = q_raw[idx + len(t):].strip(" .!?,")
            return tail or None
    return None


def planner(state: OutfitState) -> dict:
    """Read state['query'], return the fields this node fills in."""
    q_raw = (state.get("query") or "").strip()
    q = q_raw.lower()

    intent = _detect_intent(q)
    updates: dict = {"intent": intent}

    # A preference statement ("I don't like frocks") isn't an outfit request;
    # capture what to remember and let the graph route it to memory.
    if intent == "save_preference":
        updates["preference"] = _extract_preference(q_raw, q)
        return updates

    updates["occasion"] = _detect_occasion(q)
    updates["city"] = _detect_city(q_raw)
    updates["dates"] = _detect_dates(q)
    return updates
