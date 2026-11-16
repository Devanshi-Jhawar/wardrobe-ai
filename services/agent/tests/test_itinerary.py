"""Trips with a plan per day: "day 1 beach, day 2 wedding"."""
from datetime import date, timedelta

import pytest

from app import prefs as P
from app.nodes.composer import composer
from app.nodes.critic import critic
from app.nodes.gather import date_window
from app.nodes.planner import planner
from conftest import item, weather_day, weather_reply


def plan(q):
    return planner({"query": q})


@pytest.mark.parametrize("query, expected", [
    ("4 day trip to Goa: day 1 beach, day 2 wedding, day 3 sightseeing, day 4 flight home",
     [(1, "beach"), (2, "wedding"), (3, "sightseeing"), (4, "travel")]),
    ("trip to Jaipur. First day office meeting, second day festival with family",
     [(1, "office"), (2, "festival")]),
    ("3-day Shimla trip, day 1 trekking, last day party", [(1, "hiking"), (3, "party")]),
    ("weekend in Goa - 1st day beach and 2nd day a date", [(1, "beach"), (2, "date")]),
])
def test_itinerary_days_and_occasions(query, expected):
    out = plan(query)
    assert out["intent"] == "trip"
    assert [(d["day"], d["occasion"]) for d in out["itinerary"]] == expected
    assert out["dates"]["count"] >= expected[-1][0]


def test_itinerary_sets_length_and_keeps_city():
    out = plan("Goa trip: day 1 beach, day 2 wedding, day 3 beach")
    assert out["city"] == "Goa" and out["dates"]["count"] == 3
    assert out["occasion"] is None                     # every day has its own
    assert out["search_text"] is None                  # plans aren't clothes


def test_activity_text_kept():
    out = plan("day 1 sangeet night, day 2 wedding ceremony")
    assert "sangeet" in out["itinerary"][0]["activity"]


def test_no_itinerary_for_plain_trip():
    out = plan("packing for a 4-day trip to Shimla")
    assert "itinerary" not in out and out["dates"] == {"count": 4}


def test_trip_with_start_day():
    out = plan("4 day trip to Goa starting saturday")
    assert out["dates"] == {"count": 4, "relative": "saturday"}
    start, n = date_window(out["dates"], date(2026, 11, 16))       # a Monday
    assert start == date(2026, 11, 21) and n == 4


def test_explicit_start_date_window():
    today = date.today()
    start = (today + timedelta(days=5)).isoformat()
    assert date_window({"count": 3, "start": start}, today) == (today + timedelta(days=5), 3)
    assert date_window({"start": start}, today) == (today + timedelta(days=5), 1)


# --- composer dresses each day for its own occasion ---

@pytest.fixture
def trip_wardrobe(wardrobe):
    return wardrobe + [
        item("shorts", "Shorts", color=["khaki"], occasion=["trip", "casual"], season=["summer"]),
        item("linen", "Shirt", color=["white"], occasion=["trip", "casual"], season=["summer"]),
        item("lehenga", "Lehenga", color=["maroon"], occasion=["wedding"]),
    ]


def test_each_day_gets_its_occasion(trip_wardrobe, today):
    days = [weather_day(31, on=today + timedelta(days=i)) for i in range(3)]
    draft = composer({
        "intent": "trip", "wardrobe_items": trip_wardrobe, "weather": weather_reply(*days),
        "attempts": 0, "prefs": P.empty_prefs(True), "dates": {"count": 3},
        "itinerary": [{"day": 1, "occasion": "beach", "activity": "beach"},
                      {"day": 2, "occasion": "wedding", "activity": "wedding"},
                      {"day": 3, "occasion": "office", "activity": "client meeting"}],
    })["draft_outfit"]
    by_day = {d["day"]: d for d in draft["days"]}
    assert by_day[2]["occasion"] == "wedding"
    assert {i["category"] for i in by_day[2]["items"]} & {"Lehenga", "Saree"}
    assert by_day[3]["occasion"] == "office"
    assert "Shirt" in {i["category"] for i in by_day[3]["items"]}
    assert by_day[1]["activity"] == "beach"
    # The critic is happy: every day has something that suits it.
    verdict = critic({"draft_outfit": draft, "wardrobe_items": trip_wardrobe, "attempts": 0})
    assert verdict["critic_passed"], verdict["critic_notes"]


def test_plan_longer_than_forecast_gets_blank_days(trip_wardrobe, today):
    draft = composer({
        "intent": "trip", "wardrobe_items": trip_wardrobe,
        "weather": weather_reply(weather_day(30, on=today)), "attempts": 0,
        "prefs": P.empty_prefs(True), "dates": {"count": 3},
        "itinerary": [{"day": 3, "occasion": "wedding", "activity": None}],
    })["draft_outfit"]
    assert len(draft["days"]) == 3 and draft["days"][2]["occasion"] == "wedding"


def test_critic_flags_a_day_that_misses_its_occasion(trip_wardrobe):
    tee = next(i for i in trip_wardrobe if i["id"] == "tee")
    draft = {"days": [{"day": 1, "occasion": "wedding", "items": [tee]}],
             "items": [tee], "missing_slots": []}
    out = critic({"draft_outfit": draft, "wardrobe_items": trip_wardrobe, "attempts": 0})
    assert not out["critic_passed"] and "day 1" in out["critic_notes"]
