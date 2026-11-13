"""Integration tests against the REAL services (opt-in).

Start wardrobe (8001), weather (8004, needs internet) and memory (8006), then:
    AGENT_LIVE=1 python -m pytest tests/test_live.py -v

They use a fresh random user id for memory, so your own data isn't touched,
but that user's rows stay in memory.db (harmless; delete memory.db to reset).
Wardrobe data is read for `test_user` only. These catch the class of bug the
unit tests can't: the agent and a service disagreeing about an API.
"""
import os
import uuid
from datetime import date, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app import clients, config
from app.main import app

pytestmark = pytest.mark.skipif(os.getenv("AGENT_LIVE") != "1",
                                reason="set AGENT_LIVE=1 with the services running")

USER = f"live-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def api():
    for name, url in (("wardrobe", config.WARDROBE_URL), ("weather", config.WEATHER_URL),
                      ("memory", config.MEMORY_URL)):
        assert clients.ping(url), f"{name} service not running at {url}"
    return TestClient(app)


def test_weather_contract():
    w = clients.fetch_weather("Shimla", days=2, start_date=date.today() + timedelta(days=1))
    assert w and len(w["days"]) == 2
    assert w["days"][0]["date"] == str(date.today() + timedelta(days=1))
    for key in ("label", "max", "rainy", "needs"):
        assert key in w["days"][0]
    assert "trip" in w


def test_wardrobe_contract():
    items = clients.fetch_wardrobe("test_user")
    assert isinstance(items, list)
    # The exact body the agent sends must be accepted (it used to get 422).
    r = httpx.post(f"{config.WARDROBE_URL}/wardrobe/search",
                   json={"user_id": "test_user", "embedding": [0.1] * 512, "k": 5})
    assert r.status_code == 200 and "hits" in r.json()


def test_memory_round_trip(api):
    assert api.post("/feedback", json={"user_id": USER, "like": "blue"}).status_code == 200
    a = api.post("/agent", json={"query": "I don't like yellow and orange", "user_id": USER}).json()
    assert a["answer"]["type"] == "preference_saved"
    prefs = httpx.get(f"{config.MEMORY_URL}/memory/{USER}/preferences").json()
    assert prefs["likes"] == ["blue"] and prefs["dislikes"] == ["yellow", "orange"]

    r = api.post("/wear", json={"user_id": USER, "item_ids": ["a", "b"]})
    assert r.status_code == 201
    mem = httpx.get(f"{config.MEMORY_URL}/memory/{USER}").json()
    assert set(mem["recently_worn_item_ids"]) == {"a", "b"}
    future = str(date.today() + timedelta(days=5))
    assert api.post("/wear", json={"user_id": USER, "item_ids": ["a"], "worn_on": future}).status_code == 400

    assert api.post("/rate", json={"user_id": USER, "item_ids": ["c"], "liked": False}).status_code == 201
    assert httpx.get(f"{config.MEMORY_URL}/memory/{USER}").json()["disliked_item_ids"] == ["c"]


def test_trip_plan_live(api):
    a = api.post("/agent", json={"query": "packing for a 3-day trip to Shimla",
                                 "user_id": "test_user"}).json()["answer"]
    assert a["type"] == "trip_plan" and len(a["days"]) == 3
    assert all(d["date"] and d["label"] for d in a["days"])
