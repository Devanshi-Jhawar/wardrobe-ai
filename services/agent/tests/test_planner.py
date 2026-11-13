"""Planner: intents, preferences (gap #3), search words and date windows."""
from datetime import date

import pytest

from app.nodes.gather import date_window
from app.nodes.planner import planner


@pytest.mark.parametrize("query, kind, things", [
    ("I don't like frocks", "dislike", ["frocks"]),
    ("I don't like yellow and orange", "dislike", ["yellow", "orange"]),
    ("I hate wearing heels", "dislike", ["heels"]),
    ("I love blue", "like", ["blue"]),
    ("I love wearing ethnic clothes", "like", ["ethnic"]),
    ("I really like pastel colours, linen and cotton", "like", ["pastel", "linen", "cotton"]),
    ("I prefer sneakers", "like", ["sneakers"]),
    ("my favourite colour is green", "like", ["green"]),
])
def test_preferences(query, kind, things):
    out = planner({"query": query})
    assert out["intent"] == "save_preference"
    assert out["preference_kind"] == kind
    assert out["preferences"] == things


@pytest.mark.parametrize("query, intent", [
    ("what should I wear to office tomorrow in Goa?", "recommend"),
    ("packing for a 4-day trip to Shimla", "trip"),
    ("what should I buy for my wardrobe?", "gap"),
    ("I don't like blazers", "save_preference"),
])
def test_intent(query, intent):
    assert planner({"query": query})["intent"] == intent


@pytest.mark.parametrize("query, search", [
    ("what should I wear to office tomorrow in Goa?", None),
    ("What should I wear today?", None),
    ("packing for a 4-day trip to Shimla", None),
    ("I want to wear my red saree", "red saree"),
    ("something with a white t-shirt", "white t-shirt"),
    ("something ethnic for diwali in Delhi", "ethnic"),
    ("navy blazer for a meeting on Monday", "navy blazer"),
])
def test_search_text(query, search):
    assert planner({"query": query}).get("search_text") == search


THU = date(2026, 11, 12)


@pytest.mark.parametrize("rel, start, days", [
    ("tomorrow", date(2026, 11, 13), 1), ("saturday", date(2026, 11, 14), 1),
    ("thursday", THU, 1), ("this weekend", date(2026, 11, 14), 2),
    ("next weekend", date(2026, 11, 21), 2), ("this week", THU, 4),
    ("next week", date(2026, 11, 16), 7), ("today", THU, 1),
])
def test_date_window(rel, start, days):
    assert date_window({"relative": rel}, THU) == (start, days)


def test_date_window_trip_and_sunday():
    assert date_window({"count": 4}, THU) == (THU, 4)
    sun = date(2026, 11, 15)
    assert date_window({"relative": "this weekend"}, sun) == (sun, 1)
    assert date_window({"relative": "next weekend"}, sun) == (date(2026, 11, 21), 2)
